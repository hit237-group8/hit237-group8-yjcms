"""
cases/models.py
Owner: Samir (Research and Backend Lead)

Carried forward from Assessment 2 with Assessment 4 extensions.

Assessment 4 additions:
  - Domain exception classes at top of file (ADR-007)
  - YoungPerson: structured address, email, education_status,
    interpreter_required, is_minor property, full_address property,
    database indexes on name fields for search performance
  - Case: clean() model-level validation for closed_date
  - All Assessment 2 models and relationships preserved unchanged

Django philosophies (ADR-005):
  Fat model: business logic on models not views (age, available_spots, is_minor)
  Explicit: through models for M2M, choices for all CharField options (ADR-001)
  Loose coupling: models never import from views or services
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone


# ── Domain Exceptions (ADR-007) ───────────────────────────────────────────────
# Placed in models.py (not services.py) to avoid circular imports.
# Both services and tests import from models — safe in both directions.

class CaseAlreadyClosedError(Exception):
    """Raised when attempting to modify a case that is not open."""
    pass


class ProgramFullError(Exception):
    """Raised when attempting to enrol in a program at full capacity."""
    pass


class DuplicateEnrolmentError(Exception):
    """Raised when a case is already enrolled in the specified program."""
    pass


class CaseworkerNotFoundError(Exception):
    """Raised when a caseworker lookup by staff_id finds no result."""
    pass


# ── Caseworker ────────────────────────────────────────────────────────────────
class Caseworker(models.Model):
    """
    Extends Django's built-in User via OneToOne profile pattern.
    Auth concerns stay in User; justice-system concerns stay here. (ADR-003)
    Chosen over AbstractUser because it is non-destructive mid-project.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='caseworker_profile'
    )
    staff_id = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.staff_id})"

    def full_name(self):
        return self.user.get_full_name()


# ── YoungPerson ───────────────────────────────────────────────────────────────
class YoungPerson(models.Model):
    """
    Represents a client in the youth justice system.

    Fat-model pattern (ADR-005): all business logic methods live here.

    Assessment 4 additions:
      - Structured address fields replace single TextField:
        enables suburb/state filtering and geographic reporting
      - email, guardian_email: staff contact channels
      - education_status: documented risk factor in youth justice
        (not enrolled in school = statistically higher risk)
      - interpreter_required: affects court hearing logistics
      - is_minor @property: permission boundary at age 18
        (minors require guardian consent for program enrolment)
      - full_address @property: assembles fields for display
      - Database indexes on last_name, first_name:
        search uses icontains on both — index improves query performance
    """
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other / Non-binary'),
        ('N', 'Prefer not to say'),
    ]
    EDUCATION_CHOICES = [
        ('enrolled', 'Enrolled in School'),
        ('not_enrolled', 'Not Enrolled'),
        ('completed', 'Completed Year 12'),
        ('unknown', 'Unknown'),
    ]

    # Identity
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)

    # Structured contact (Assessment 4 — replaces single address TextField)
    street_address = models.CharField(max_length=255, blank=True)
    suburb = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True, default='NT')
    postcode = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # Guardian
    guardian_name = models.CharField(max_length=200, blank=True)
    guardian_phone = models.CharField(max_length=20, blank=True)
    guardian_email = models.EmailField(blank=True)

    # Background
    indigenous_status = models.BooleanField(default=False)
    interpreter_required = models.BooleanField(default=False)
    education_status = models.CharField(
        max_length=20, choices=EDUCATION_CHOICES, default='unknown'
    )

    # System
    assigned_caseworker = models.ForeignKey(
        Caseworker,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='clients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Young Person'
        verbose_name_plural = 'Young Persons'
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['date_of_birth']),
        ]

    def __str__(self):
        return f"{self.last_name}, {self.first_name} (ID: {self.pk})"

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def age(self):
        """
        Calculate current age from date_of_birth.
        The formula subtracts 1 when today is before this year's birthday,
        handling the common off-by-one error in age calculations.
        Fat-model pattern: business logic on the model. (ADR-005)
        """
        today = timezone.now().date()
        dob = self.date_of_birth
        return today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )

    @property
    def is_minor(self):
        """
        True when person is under 18.
        Permission boundary: minors require guardian consent for enrolment.
        Assessment 4 addition — deliberate OO encapsulation of a domain rule.
        """
        return self.age() < 18

    @property
    def full_address(self):
        """
        Assembles structured address fields into one display string.
        Blank fields are excluded — no leading or trailing commas.
        Business logic on the model not in templates. (ADR-005)
        """
        if not any([self.street_address, self.suburb, self.postcode]):
            return ''
        parts = [self.street_address, self.suburb, self.state, self.postcode]
        return ', '.join(p for p in parts if p)

    def active_case_count(self):
        """Count of open cases only — not closed, pending, or referred."""
        return self.cases.filter(status='open').count()


# ── Offence ───────────────────────────────────────────────────────────────────
class Offence(models.Model):
    """Catalogue of offence types. Reusable across many cases."""
    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('serious', 'Serious'),
        ('violent', 'Violent'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    requires_court = models.BooleanField(default=False)

    class Meta:
        ordering = ['severity', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_severity_display()})"


# ── Case ──────────────────────────────────────────────────────────────────────
class Case(models.Model):
    """
    Central aggregate of the domain. Links YoungPerson, Caseworker,
    Offences (via CaseOffence through model), and Programs (via Enrolment).
    Both M2M relationships use explicit through models. (ADR-001)

    Assessment 4: clean() adds model-level validation.
    """
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('pending', 'Pending Court'),
        ('closed', 'Closed'),
        ('referred', 'Referred'),
        ('diverted', 'Diverted'),
    ]
    RISK_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    case_number = models.CharField(max_length=30, unique=True)
    young_person = models.ForeignKey(
        YoungPerson, on_delete=models.CASCADE, related_name='cases'
    )
    caseworker = models.ForeignKey(
        Caseworker,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='cases'
    )
    offences = models.ManyToManyField(
        Offence, through='CaseOffence', related_name='cases', blank=True
    )
    programs = models.ManyToManyField(
        'Program', through='Enrolment', related_name='cases', blank=True
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='open')
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default='low')
    opened_date = models.DateField(auto_now_add=True)
    closed_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-opened_date']

    def __str__(self):
        return f"Case {self.case_number} – {self.young_person}"

    def is_open(self):
        """True when status is open. Used as guard in all service methods."""
        return self.status == 'open'

    def hearing_count(self):
        """Count of hearings for this case."""
        return self.hearings.count()

    def clean(self):
        """
        Model-level validation: closed_date may only be set when status
        is in a terminal state. Explicit domain rule on the model itself,
        not just the service layer. Assessment 4 addition.
        """
        if self.closed_date and self.status not in ('closed', 'referred', 'diverted'):
            raise ValidationError(
                'closed_date may only be set when status is closed, '
                'referred, or diverted.'
            )


# ── CaseOffence (Through Model) ───────────────────────────────────────────────
class CaseOffence(models.Model):
    """
    Explicit join table for Case–Offence M2M. (ADR-001)
    Stores per-occurrence data: date_of_offence and location.
    These belong on the relationship, not on either entity alone.
    unique_together prevents the same offence being recorded twice on a case.
    """
    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name='case_offences'
    )
    offence = models.ForeignKey(
        Offence, on_delete=models.CASCADE, related_name='case_offences'
    )
    date_of_offence = models.DateField()
    location = models.CharField(max_length=200, blank=True)
    details = models.TextField(blank=True)

    class Meta:
        unique_together = ('case', 'offence')
        ordering = ['-date_of_offence']
        verbose_name = 'Case Offence'

    def __str__(self):
        return (
            f"{self.case.case_number} → "
            f"{self.offence.name} on {self.date_of_offence}"
        )


# ── CourtHearing ──────────────────────────────────────────────────────────────
class CourtHearing(models.Model):
    """One case may have many hearings — adjournments, appeals, sentences."""
    OUTCOME_CHOICES = [
        ('pending', 'Pending'),
        ('adjourned', 'Adjourned'),
        ('dismissed', 'Dismissed'),
        ('sentenced', 'Sentenced'),
        ('diverted', 'Diverted'),
        ('acquitted', 'Acquitted'),
    ]

    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name='hearings'
    )
    hearing_date = models.DateTimeField()
    court_name = models.CharField(max_length=200)
    judge = models.CharField(max_length=200, blank=True)
    outcome = models.CharField(
        max_length=20, choices=OUTCOME_CHOICES, default='pending'
    )
    outcome_notes = models.TextField(blank=True)
    next_hearing_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-hearing_date']

    def __str__(self):
        return (
            f"Hearing for {self.case.case_number} "
            f"on {self.hearing_date.date()}"
        )


# ── Program ───────────────────────────────────────────────────────────────────
class Program(models.Model):
    """
    Rehabilitation or diversion program cases can enrol in.
    available_spots() and is_full() implement the capacity rule.
    Only 'enrolled' status counts — completed/withdrawn spots are free.
    Fat-model pattern: capacity logic lives here. (ADR-005)
    """
    PROGRAM_TYPE_CHOICES = [
        ('rehabilitation', 'Rehabilitation'),
        ('diversion', 'Diversion'),
        ('education', 'Education'),
        ('counselling', 'Counselling'),
        ('community_service', 'Community Service'),
    ]

    name = models.CharField(max_length=200)
    program_type = models.CharField(
        max_length=30, choices=PROGRAM_TYPE_CHOICES, default='rehabilitation'
    )
    description = models.TextField()
    duration_weeks = models.PositiveIntegerField()
    capacity = models.PositiveIntegerField(default=20)
    facilitator = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def available_spots(self):
        """
        Remaining capacity. Only 'enrolled' counts toward the limit.
        Completed and withdrawn enrolments do not consume a spot.
        """
        enrolled = self.enrolments.filter(status='enrolled').count()
        return max(0, self.capacity - enrolled)

    def is_full(self):
        """True when no spots remain. Delegates to available_spots()."""
        return self.available_spots() == 0


# ── Enrolment (Through Model) ─────────────────────────────────────────────────
class Enrolment(models.Model):
    """
    Explicit join table for Case–Program M2M. (ADR-001)
    Tracks enrolment lifecycle: status, dates, notes.
    unique_together prevents the same case enrolling in a program twice.
    """
    STATUS_CHOICES = [
        ('enrolled', 'Enrolled'),
        ('completed', 'Completed'),
        ('withdrawn', 'Withdrawn'),
        ('referred', 'Referred'),
    ]

    case = models.ForeignKey(
        Case, on_delete=models.CASCADE, related_name='enrolments'
    )
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name='enrolments'
    )
    enrolment_date = models.DateField(auto_now_add=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='enrolled'
    )
    completion_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('case', 'program')
        ordering = ['-enrolment_date']

    def __str__(self):
        return (
            f"{self.case.young_person} → "
            f"{self.program.name} ({self.get_status_display()})"
        )

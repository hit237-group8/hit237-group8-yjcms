"""
cases/services/case_service.py
Owner: Samir (Research and Backend Lead)

Service layer for the Youth Justice CMS domain. (ADR-007)

Responsibilities:
  - Encapsulate business operations that span multiple models
  - Enforce domain invariants (case must be open, program must have capacity)
  - Raise named domain exceptions for every invariant violation
  - Be fully testable without any HTTP context

What services deliberately do NOT do:
  - Handle HTTP requests or responses — that is views.py
  - Render templates — that is templates/
  - Define data structure — that is models.py

This is the Single Responsibility Principle applied at the architecture level:
  HTTP layer    → views.py
  Domain rules  → case_service.py  (this file)
  Data layer    → models.py
"""

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from cases.models import (
    Case, YoungPerson, Caseworker,
    Offence, CaseOffence, Program, Enrolment, CourtHearing,
    CaseAlreadyClosedError, ProgramFullError,
    DuplicateEnrolmentError, CaseworkerNotFoundError,
)


class CaseService:
    """
    Encapsulates all Case-related business operations.
    All methods are static — CaseService has no instance state.
    Views call service methods; services interact with models directly.
    """

    @staticmethod
    def create_case(
        case_number: str,
        young_person: YoungPerson,
        caseworker: Caseworker = None,
        risk_level: str = 'low',
        notes: str = '',
    ) -> Case:
        """
        Open a new case. Validates case_number uniqueness before creating.

        Raises:
            ValueError: if case_number already exists in the system.
        """
        if Case.objects.filter(case_number=case_number).exists():
            raise ValueError(
                f"Case number '{case_number}' already exists. "
                "Case numbers must be unique across the system."
            )
        return Case.objects.create(
            case_number=case_number,
            young_person=young_person,
            caseworker=caseworker,
            risk_level=risk_level,
            notes=notes,
            status='open',
        )

    @staticmethod
    def close_case(case: Case) -> Case:
        """
        Close an open case and set closed_date to today.

        Raises:
            CaseAlreadyClosedError: if case is not currently open.
        """
        if not case.is_open():
            raise CaseAlreadyClosedError(
                f"Case {case.case_number} cannot be closed — "
                f"current status is '{case.get_status_display()}'."
            )
        case.status = 'closed'
        case.closed_date = timezone.now().date()
        case.save(update_fields=['status', 'closed_date'])
        return case

    @staticmethod
    def assign_caseworker(case: Case, caseworker: Caseworker) -> Case:
        """
        Assign or reassign a caseworker to a case.

        Raises:
            CaseAlreadyClosedError: if case is not open.
        """
        if not case.is_open():
            raise CaseAlreadyClosedError(
                f"Cannot assign caseworker to case {case.case_number} — "
                f"case is {case.get_status_display()}."
            )
        case.caseworker = caseworker
        case.save(update_fields=['caseworker'])
        return case

    @staticmethod
    def update_risk_level(case: Case, risk_level: str) -> Case:
        """
        Update the risk level of an open case.

        Raises:
            CaseAlreadyClosedError: if case is not open.
            ValueError: if risk_level is not a valid choice.
        """
        valid = [c[0] for c in Case.RISK_CHOICES]
        if risk_level not in valid:
            raise ValueError(
                f"'{risk_level}' is not a valid risk level. "
                f"Valid choices: {', '.join(valid)}."
            )
        if not case.is_open():
            raise CaseAlreadyClosedError(
                f"Cannot update risk on closed case {case.case_number}."
            )
        case.risk_level = risk_level
        case.save(update_fields=['risk_level'])
        return case

    @staticmethod
    @transaction.atomic
    def enrol_in_program(
        case: Case,
        program: Program,
        notes: str = '',
    ) -> Enrolment:
        """
        Enrol a case in a rehabilitation or diversion program.

        Enforces three domain invariants in sequence:
          1. Case must be open
          2. Program must have available capacity
          3. Case must not already be enrolled in this program

        @transaction.atomic is a non-trivial choice:
          Without it, if the database write fails after all three checks pass,
          no capacity is consumed but the state is inconsistent.
          With it, the entire operation is rolled back atomically.
          This also prevents a race condition where two simultaneous requests
          both pass the is_full() check before either creates the Enrolment row.

        Raises:
            CaseAlreadyClosedError: case is not open.
            ProgramFullError: program is at capacity.
            DuplicateEnrolmentError: already enrolled.
        """
        if not case.is_open():
            raise CaseAlreadyClosedError(
                f"Cannot enrol closed case {case.case_number} in a program."
            )
        if program.is_full():
            raise ProgramFullError(
                f"Program '{program.name}' is at full capacity "
                f"({program.capacity}/{program.capacity})."
            )
        if Enrolment.objects.filter(case=case, program=program).exists():
            raise DuplicateEnrolmentError(
                f"Case {case.case_number} is already enrolled "
                f"in '{program.name}'."
            )
        return Enrolment.objects.create(
            case=case,
            program=program,
            status='enrolled',
            notes=notes,
        )

    @staticmethod
    def complete_enrolment(enrolment: Enrolment) -> Enrolment:
        """Mark an enrolment as completed with today as completion_date."""
        enrolment.status = 'completed'
        enrolment.completion_date = timezone.now().date()
        enrolment.save(update_fields=['status', 'completion_date'])
        return enrolment

    @staticmethod
    def withdraw_enrolment(enrolment: Enrolment, notes: str = '') -> Enrolment:
        """
        Withdraw a case from a program.
        A withdrawn enrolment frees the spot because available_spots()
        only counts status='enrolled'.
        """
        enrolment.status = 'withdrawn'
        if notes:
            enrolment.notes = notes
        enrolment.save(update_fields=['status', 'notes'])
        return enrolment

    @staticmethod
    def add_offence(
        case: Case,
        offence: Offence,
        date_of_offence,
        location: str = '',
        details: str = '',
    ):
        """
        Record an offence occurrence on a case.

        Raises:
            CaseAlreadyClosedError: if case is not open.

        Returns (CaseOffence, created: bool).
        """
        if not case.is_open():
            raise CaseAlreadyClosedError(
                f"Cannot add offence to closed case {case.case_number}."
            )
        return CaseOffence.objects.get_or_create(
            case=case,
            offence=offence,
            defaults={
                'date_of_offence': date_of_offence,
                'location': location,
                'details': details,
            },
        )

    @staticmethod
    def schedule_hearing(
        case: Case,
        hearing_date,
        court_name: str,
        judge: str = '',
    ) -> CourtHearing:
        """
        Schedule a court hearing for a case.

        Raises:
            CaseAlreadyClosedError: if case is not open.
        """
        if not case.is_open():
            raise CaseAlreadyClosedError(
                f"Cannot schedule hearing for closed case {case.case_number}."
            )
        return CourtHearing.objects.create(
            case=case,
            hearing_date=hearing_date,
            court_name=court_name,
            judge=judge,
            outcome='pending',
        )

    @staticmethod
    def get_cases_for_caseworker(caseworker: Caseworker, status: str = None):
        """
        Return cases for a caseworker, optionally filtered by status.
        select_related prevents N+1 on young_person. (ADR-004)
        """
        qs = (
            Case.objects
            .filter(caseworker=caseworker)
            .select_related('young_person')
            .order_by('-opened_date')
        )
        if status:
            qs = qs.filter(status=status)
        return qs

    @staticmethod
    def get_high_risk_open_cases():
        """
        Return open high-risk cases.
        select_related prevents N+1 on young_person and caseworker__user. (ADR-004)
        """
        return (
            Case.objects
            .filter(status='open', risk_level='high')
            .select_related('young_person', 'caseworker__user')
            .order_by('-opened_date')
        )

    @staticmethod
    def get_dashboard_stats() -> dict:
        """
        Return all dashboard aggregate statistics in one call.
        Keeps views free of counting logic — service is the single source.
        """
        return {
            'total_cases': Case.objects.count(),
            'open_cases': Case.objects.filter(status='open').count(),
            'pending_cases': Case.objects.filter(status='pending').count(),
            'total_clients': YoungPerson.objects.count(),
            'total_programs': Program.objects.filter(is_active=True).count(),
        }


class YoungPersonService:
    """Encapsulates YoungPerson business operations."""

    @staticmethod
    def register_client(
        first_name: str,
        last_name: str,
        date_of_birth,
        gender: str,
        caseworker: Caseworker = None,
        **kwargs,
    ) -> YoungPerson:
        """
        Register a new young person.
        Extra kwargs are passed directly to YoungPerson.objects.create()
        allowing all optional fields to be set in one call.
        """
        return YoungPerson.objects.create(
            first_name=first_name,
            last_name=last_name,
            date_of_birth=date_of_birth,
            gender=gender,
            assigned_caseworker=caseworker,
            **kwargs,
        )

    @staticmethod
    def get_active_clients_for_caseworker(caseworker: Caseworker):
        """
        Clients with at least one open case for a given caseworker.
        annotate(Count) with filter=Q() computes the count in SQL. (ADR-004)
        """
        return (
            YoungPerson.objects
            .filter(assigned_caseworker=caseworker)
            .annotate(
                open_cases=Count(
                    'cases',
                    filter=Q(cases__status='open')
                )
            )
            .filter(open_cases__gt=0)
            .order_by('last_name', 'first_name')
        )

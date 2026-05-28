"""
cases/tests/test_models.py
Owner: Samir (Research and Backend Lead)

Tests for domain model behaviour. (ADR-008)

What IS tested here (meaningful — tests rules WE wrote):
  age():         birthday boundary formula — common off-by-one error
  is_minor:      permission boundary exactly at age 18
  full_address:  blank field handling — no leading/trailing commas
  active_case_count(): filters by 'open' only, not all statuses
  available_spots():   filters by 'enrolled' only — not completed/withdrawn
  is_full():     boundary exactly at capacity
  Case.is_open(): every status value
  Case.clean():  model validation we wrote for closed_date
  unique_together: data integrity constraints we declared

What is NOT tested (trivial — would not earn credit):
  __str__ returning a string (Django guarantee, not our logic)
  Django saving a field to the database (Django's ORM, not our code)
  Admin page rendering (integration concern, brittle)
  Field type validation e.g. EmailField format (Django's validators)
"""

from datetime import date, timedelta
from django.test import TestCase
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User

from cases.models import (
    Caseworker, YoungPerson, Offence,
    Case, CaseOffence, Program, Enrolment,
)


# ── Test helpers ──────────────────────────────────────────────────────────────
def make_user(username='u1'):
    return User.objects.create_user(username=username, password='pass123')

def make_caseworker(username='cw1'):
    return Caseworker.objects.create(
        user=make_user(username), staff_id=f'CW-{username}'
    )

def make_person(first='John', last='Smith', dob=None):
    return YoungPerson.objects.create(
        first_name=first, last_name=last,
        date_of_birth=dob or date(2008, 6, 15),
        gender='M',
    )

def make_case(person, number='C001', status='open'):
    return Case.objects.create(
        case_number=number, young_person=person, status=status
    )

def make_program(name='Prog', capacity=10):
    return Program.objects.create(
        name=name, program_type='diversion',
        description='desc', duration_weeks=8,
        capacity=capacity, facilitator='Jane'
    )


# ── YoungPerson.age() ─────────────────────────────────────────────────────────
class YoungPersonAgeTest(TestCase):
    """
    Verifies the age() birthday boundary formula.
    Meaningful because the formula subtracts 1 when today is before
    this year's birthday — the most common off-by-one error.
    """

    def test_age_on_birthday_counts_full_year(self):
        today = timezone.now().date()
        dob = today.replace(year=today.year - 18)
        p = YoungPerson(first_name='A', last_name='B', date_of_birth=dob, gender='M')
        self.assertEqual(p.age(), 18)

    def test_age_day_before_birthday_is_one_less(self):
        today = timezone.now().date()
        tomorrow = today + timedelta(days=1)
        dob = tomorrow.replace(year=today.year - 16)
        p = YoungPerson(first_name='A', last_name='B', date_of_birth=dob, gender='M')
        self.assertEqual(p.age(), 15)

    def test_age_day_after_birthday_counts_full_year(self):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        dob = yesterday.replace(year=today.year - 17)
        p = YoungPerson(first_name='A', last_name='B', date_of_birth=dob, gender='M')
        self.assertEqual(p.age(), 17)


# ── YoungPerson.is_minor ──────────────────────────────────────────────────────
class YoungPersonIsMinorTest(TestCase):
    """
    Tests permission boundary at age 18.
    Meaningful because is_minor gates guardian consent requirements.
    Failure here means minors could be enrolled without consent.
    """

    def test_person_aged_15_is_minor(self):
        dob = timezone.now().date() - timedelta(days=365 * 15 + 2)
        p = YoungPerson(first_name='A', last_name='B', date_of_birth=dob, gender='M')
        self.assertTrue(p.is_minor)

    def test_person_aged_20_is_not_minor(self):
        dob = timezone.now().date() - timedelta(days=365 * 20 + 2)
        p = YoungPerson(first_name='A', last_name='B', date_of_birth=dob, gender='M')
        self.assertFalse(p.is_minor)

    def test_exactly_18_is_not_minor(self):
        today = timezone.now().date()
        dob = today.replace(year=today.year - 18)
        p = YoungPerson(first_name='A', last_name='B', date_of_birth=dob, gender='M')
        self.assertFalse(p.is_minor)


# ── YoungPerson.full_address ──────────────────────────────────────────────────
class YoungPersonFullAddressTest(TestCase):
    """
    Tests that full_address assembles fields correctly.
    Meaningful because blank fields must not produce leading/trailing commas.
    """

    def test_all_fields_assembles_correctly(self):
        p = YoungPerson(
            first_name='A', last_name='B', date_of_birth=date(2008,1,1), gender='M',
            street_address='12 Main St', suburb='Darwin', state='NT', postcode='0800'
        )
        self.assertEqual(p.full_address, '12 Main St, Darwin, NT, 0800')

    def test_partial_fields_no_extra_commas(self):
        p = YoungPerson(
            first_name='A', last_name='B', date_of_birth=date(2008,1,1), gender='M',
            suburb='Darwin', state='NT'
        )
        self.assertEqual(p.full_address, 'Darwin, NT')

    def test_all_blank_returns_empty_string(self):
        p = YoungPerson(
            first_name='A', last_name='B', date_of_birth=date(2008,1,1), gender='M'
        )
        self.assertEqual(p.full_address, '')


# ── YoungPerson.active_case_count() ──────────────────────────────────────────
class ActiveCaseCountTest(TestCase):
    """
    Verifies active_case_count() counts only 'open' cases.
    Meaningful because it must exclude closed cases to give
    an accurate workload figure for case managers.
    """

    def test_counts_only_open_cases(self):
        p = make_person()
        make_case(p, 'C001', 'open')
        make_case(p, 'C002', 'closed')
        make_case(p, 'C003', 'open')
        self.assertEqual(p.active_case_count(), 2)

    def test_returns_zero_when_no_open_cases(self):
        p = make_person()
        make_case(p, 'C001', 'closed')
        self.assertEqual(p.active_case_count(), 0)


# ── Program.available_spots() and is_full() ───────────────────────────────────
class ProgramCapacityTest(TestCase):
    """
    Key behaviour under test: completed and withdrawn enrolments must NOT
    reduce available spots — only 'enrolled' status consumes capacity.
    This is a non-obvious rule that must be explicitly verified.
    """

    def test_full_capacity_when_empty(self):
        prog = make_program(capacity=5)
        self.assertEqual(prog.available_spots(), 5)

    def test_enrolled_reduces_available_spots(self):
        prog = make_program(capacity=3)
        for i in range(2):
            p = make_person(first=f'P{i}', last=f'L{i}')
            c = make_case(p, f'C{i}')
            Enrolment.objects.create(case=c, program=prog, status='enrolled')
        self.assertEqual(prog.available_spots(), 1)

    def test_completed_does_not_reduce_capacity(self):
        """
        A completed enrolment means the person finished the program.
        Their spot is free — available_spots must not count completed.
        """
        prog = make_program(capacity=2)
        p = make_person()
        c = make_case(p)
        Enrolment.objects.create(case=c, program=prog, status='completed')
        self.assertEqual(prog.available_spots(), 2)

    def test_withdrawn_does_not_reduce_capacity(self):
        """
        A withdrawn enrolment means the person left early.
        Their spot is free — available_spots must not count withdrawn.
        """
        prog = make_program(capacity=2)
        p = make_person()
        c = make_case(p)
        Enrolment.objects.create(case=c, program=prog, status='withdrawn')
        self.assertEqual(prog.available_spots(), 2)

    def test_is_full_true_at_capacity(self):
        prog = make_program(capacity=1)
        p = make_person()
        c = make_case(p)
        Enrolment.objects.create(case=c, program=prog, status='enrolled')
        self.assertTrue(prog.is_full())

    def test_is_full_false_below_capacity(self):
        prog = make_program(capacity=2)
        p = make_person()
        c = make_case(p)
        Enrolment.objects.create(case=c, program=prog, status='enrolled')
        self.assertFalse(prog.is_full())


# ── Case.is_open() ────────────────────────────────────────────────────────────
class CaseIsOpenTest(TestCase):
    """
    Tests is_open() for every status value.
    Meaningful because is_open() is the guard used by every service method.
    A wrong return value here silently bypasses all domain rules.
    """

    def test_open_status_returns_true(self):
        p = make_person()
        c = make_case(p, status='open')
        self.assertTrue(c.is_open())

    def test_closed_returns_false(self):
        p = make_person()
        c = make_case(p, status='closed')
        self.assertFalse(c.is_open())

    def test_pending_returns_false(self):
        p = make_person()
        c = make_case(p, status='pending')
        self.assertFalse(c.is_open())

    def test_diverted_returns_false(self):
        p = make_person()
        c = make_case(p, status='diverted')
        self.assertFalse(c.is_open())

    def test_referred_returns_false(self):
        p = make_person()
        c = make_case(p, status='referred')
        self.assertFalse(c.is_open())


# ── Case.clean() model validation ─────────────────────────────────────────────
class CaseCleanTest(TestCase):
    """
    Tests that clean() enforces the closed_date domain rule.
    Meaningful because without this, a user could set a closed_date
    on an open case — data inconsistency.
    """

    def test_closed_date_on_open_case_raises_validation_error(self):
        p = make_person()
        c = Case(
            case_number='C-V1', young_person=p,
            status='open', closed_date=date(2025, 1, 1)
        )
        with self.assertRaises(ValidationError):
            c.clean()

    def test_closed_date_on_closed_case_is_valid(self):
        p = make_person()
        c = Case(
            case_number='C-V2', young_person=p,
            status='closed', closed_date=date(2025, 1, 1)
        )
        c.clean()  # Must not raise

    def test_closed_date_on_diverted_case_is_valid(self):
        p = make_person()
        c = Case(
            case_number='C-V3', young_person=p,
            status='diverted', closed_date=date(2025, 1, 1)
        )
        c.clean()  # Must not raise


# ── CaseOffence unique_together ───────────────────────────────────────────────
class CaseOffenceConstraintTest(TestCase):
    """
    Tests the unique_together constraint.
    Meaningful because without it the same offence could be recorded twice
    on a case, corrupting any query that aggregates by offence.
    """

    def test_same_offence_on_same_case_raises_integrity_error(self):
        p = make_person()
        c = make_case(p)
        o = Offence.objects.create(name='Theft', severity='minor')
        CaseOffence.objects.create(case=c, offence=o, date_of_offence=date(2024,1,1))
        with self.assertRaises(IntegrityError):
            CaseOffence.objects.create(case=c, offence=o, date_of_offence=date(2024,2,1))

    def test_same_offence_on_different_cases_is_allowed(self):
        p = make_person()
        c1 = make_case(p, 'C001')
        c2 = make_case(p, 'C002')
        o = Offence.objects.create(name='Theft', severity='minor')
        CaseOffence.objects.create(case=c1, offence=o, date_of_offence=date(2024,1,1))
        CaseOffence.objects.create(case=c2, offence=o, date_of_offence=date(2024,3,1))
        self.assertEqual(CaseOffence.objects.filter(offence=o).count(), 2)

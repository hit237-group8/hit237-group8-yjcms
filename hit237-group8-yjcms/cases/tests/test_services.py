"""
cases/tests/test_services.py
Owner: Samir (Research and Backend Lead)

Tests for service layer domain rules. (ADR-008)

What IS tested (meaningful):
  - Every service method happy path produces correct output
  - Every named exception raised under the correct condition
  - Boundary cases: exactly-full program, every non-open status
  - Non-obvious rule: completed/withdrawn enrolments free capacity
  - @transaction.atomic: duplicate enrolment does not leave inconsistent state

What is NOT tested:
  - HTTP layer (test_views.py covers that)
  - Django's ORM (not our code)
  - Django's built-in form validation
"""

from datetime import date, timedelta
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User

from cases.models import (
    Caseworker, YoungPerson, Case, Offence,
    Program, Enrolment, CourtHearing,
    CaseAlreadyClosedError, ProgramFullError, DuplicateEnrolmentError,
)
from cases.services.case_service import CaseService, YoungPersonService


# ── Helpers ────────────────────────────────────────────────────────────────────
def make_user(username='u1'):
    return User.objects.create_user(username=username, password='pass123')

def make_caseworker(username='cw1'):
    return Caseworker.objects.create(
        user=make_user(username), staff_id=f'CW-{username}'
    )

def make_person(first='Jane', last='Doe'):
    return YoungPerson.objects.create(
        first_name=first, last_name=last,
        date_of_birth=date(2008, 6, 1), gender='F'
    )

def make_open_case(person, number='C001'):
    return Case.objects.create(
        case_number=number, young_person=person, status='open'
    )

def make_program(capacity=5):
    return Program.objects.create(
        name='Test Program', program_type='diversion',
        description='desc', duration_weeks=6,
        capacity=capacity, facilitator='Facilitator'
    )


# ── CaseService.create_case ───────────────────────────────────────────────────
class CreateCaseTest(TestCase):

    def test_creates_case_with_status_open(self):
        p = make_person()
        c = CaseService.create_case('X01', p, risk_level='medium')
        self.assertEqual(c.status, 'open')
        self.assertEqual(c.risk_level, 'medium')

    def test_duplicate_case_number_raises_value_error(self):
        p = make_person()
        CaseService.create_case('DUP-001', p)
        with self.assertRaises(ValueError) as ctx:
            CaseService.create_case('DUP-001', p)
        self.assertIn('DUP-001', str(ctx.exception))


# ── CaseService.close_case ────────────────────────────────────────────────────
class CloseCaseTest(TestCase):

    def test_closes_open_case_sets_closed_date(self):
        p = make_person()
        c = make_open_case(p)
        CaseService.close_case(c)
        c.refresh_from_db()
        self.assertEqual(c.status, 'closed')
        self.assertEqual(c.closed_date, timezone.now().date())

    def test_closing_closed_case_raises(self):
        p = make_person()
        c = Case.objects.create(case_number='CL', young_person=p, status='closed')
        with self.assertRaises(CaseAlreadyClosedError):
            CaseService.close_case(c)

    def test_closing_diverted_case_raises(self):
        p = make_person()
        c = Case.objects.create(case_number='DV', young_person=p, status='diverted')
        with self.assertRaises(CaseAlreadyClosedError):
            CaseService.close_case(c)

    def test_closing_referred_case_raises(self):
        p = make_person()
        c = Case.objects.create(case_number='RF', young_person=p, status='referred')
        with self.assertRaises(CaseAlreadyClosedError):
            CaseService.close_case(c)


# ── CaseService.assign_caseworker ─────────────────────────────────────────────
class AssignCaseworkerTest(TestCase):

    def test_assigns_caseworker_to_open_case(self):
        p = make_person()
        c = make_open_case(p)
        cw = make_caseworker()
        CaseService.assign_caseworker(c, cw)
        c.refresh_from_db()
        self.assertEqual(c.caseworker, cw)

    def test_cannot_assign_to_closed_case(self):
        p = make_person()
        c = Case.objects.create(case_number='CL2', young_person=p, status='closed')
        cw = make_caseworker()
        with self.assertRaises(CaseAlreadyClosedError):
            CaseService.assign_caseworker(c, cw)


# ── CaseService.enrol_in_program ──────────────────────────────────────────────
class EnrolInProgramTest(TestCase):

    def test_enrols_and_returns_enrolment(self):
        p = make_person()
        c = make_open_case(p)
        prog = make_program()
        enrolment = CaseService.enrol_in_program(c, prog)
        self.assertEqual(enrolment.status, 'enrolled')
        self.assertEqual(enrolment.case, c)

    def test_closed_case_raises_case_already_closed(self):
        p = make_person()
        c = Case.objects.create(case_number='CL3', young_person=p, status='closed')
        prog = make_program()
        with self.assertRaises(CaseAlreadyClosedError):
            CaseService.enrol_in_program(c, prog)

    def test_full_program_raises_program_full(self):
        """
        ProgramFullError must be raised when capacity is exactly reached.
        This verifies the capacity invariant in the service layer.
        """
        p1 = make_person('A', 'One')
        p2 = make_person('B', 'Two')
        c1 = make_open_case(p1, 'C001')
        c2 = make_open_case(p2, 'C002')
        prog = make_program(capacity=1)
        Enrolment.objects.create(case=c1, program=prog, status='enrolled')
        with self.assertRaises(ProgramFullError):
            CaseService.enrol_in_program(c2, prog)

    def test_duplicate_enrolment_raises_duplicate_error(self):
        """
        Attempting to enrol the same case in the same program twice
        must raise DuplicateEnrolmentError, not silently create a duplicate.
        """
        p = make_person()
        c = make_open_case(p)
        prog = make_program()
        CaseService.enrol_in_program(c, prog)
        with self.assertRaises(DuplicateEnrolmentError):
            CaseService.enrol_in_program(c, prog)

    def test_withdrawn_enrolment_does_not_block_new_enrolment(self):
        """
        A withdrawn enrolment frees the spot.
        A new case should be able to enrol even if another withdrew.
        Verifies the interaction between withdraw and capacity.
        """
        p1 = make_person('A', 'One')
        p2 = make_person('B', 'Two')
        c1 = make_open_case(p1, 'C001')
        c2 = make_open_case(p2, 'C002')
        prog = make_program(capacity=1)
        Enrolment.objects.create(case=c1, program=prog, status='withdrawn')
        enrolment = CaseService.enrol_in_program(c2, prog)
        self.assertEqual(enrolment.status, 'enrolled')

    def test_completed_enrolment_does_not_block_new_enrolment(self):
        """
        A completed enrolment frees the spot.
        New case should be able to enrol even if another completed.
        """
        p1 = make_person('A', 'One')
        p2 = make_person('B', 'Two')
        c1 = make_open_case(p1, 'C001')
        c2 = make_open_case(p2, 'C002')
        prog = make_program(capacity=1)
        Enrolment.objects.create(case=c1, program=prog, status='completed')
        enrolment = CaseService.enrol_in_program(c2, prog)
        self.assertEqual(enrolment.status, 'enrolled')


# ── CaseService.complete_enrolment ────────────────────────────────────────────
class CompleteEnrolmentTest(TestCase):

    def test_marks_completed_and_sets_completion_date(self):
        p = make_person()
        c = make_open_case(p)
        prog = make_program()
        enrolment = Enrolment.objects.create(case=c, program=prog, status='enrolled')
        CaseService.complete_enrolment(enrolment)
        enrolment.refresh_from_db()
        self.assertEqual(enrolment.status, 'completed')
        self.assertEqual(enrolment.completion_date, timezone.now().date())


# ── CaseService.withdraw_enrolment ────────────────────────────────────────────
class WithdrawEnrolmentTest(TestCase):

    def test_marks_withdrawn_and_saves_notes(self):
        p = make_person()
        c = make_open_case(p)
        prog = make_program()
        enrolment = Enrolment.objects.create(case=c, program=prog, status='enrolled')
        CaseService.withdraw_enrolment(enrolment, notes='Moved interstate')
        enrolment.refresh_from_db()
        self.assertEqual(enrolment.status, 'withdrawn')
        self.assertEqual(enrolment.notes, 'Moved interstate')


# ── CaseService.add_offence ───────────────────────────────────────────────────
class AddOffenceTest(TestCase):

    def test_adds_offence_to_open_case(self):
        p = make_person()
        c = make_open_case(p)
        o = Offence.objects.create(name='Theft', severity='minor')
        co, created = CaseService.add_offence(c, o, date_of_offence=date(2024,3,1))
        self.assertTrue(created)
        self.assertEqual(co.case, c)

    def test_cannot_add_offence_to_closed_case(self):
        p = make_person()
        c = Case.objects.create(case_number='CL4', young_person=p, status='closed')
        o = Offence.objects.create(name='Theft', severity='minor')
        with self.assertRaises(CaseAlreadyClosedError):
            CaseService.add_offence(c, o, date_of_offence=date(2024,3,1))


# ── CaseService.schedule_hearing ─────────────────────────────────────────────
class ScheduleHearingTest(TestCase):

    def test_schedules_hearing_with_outcome_pending(self):
        p = make_person()
        c = make_open_case(p)
        dt = timezone.now() + timedelta(days=14)
        h = CaseService.schedule_hearing(c, dt, 'Darwin Local Court')
        self.assertEqual(h.outcome, 'pending')

    def test_cannot_schedule_for_closed_case(self):
        p = make_person()
        c = Case.objects.create(case_number='CL5', young_person=p, status='closed')
        with self.assertRaises(CaseAlreadyClosedError):
            CaseService.schedule_hearing(c, timezone.now(), 'Darwin Court')


# ── CaseService.get_high_risk_open_cases ─────────────────────────────────────
class HighRiskCasesTest(TestCase):

    def test_returns_only_high_risk_open(self):
        p = make_person()
        high_open = Case.objects.create(
            case_number='HR-O', young_person=p, status='open', risk_level='high'
        )
        low_open = Case.objects.create(
            case_number='LR-O', young_person=p, status='open', risk_level='low'
        )
        high_closed = Case.objects.create(
            case_number='HR-C', young_person=p, status='closed', risk_level='high'
        )
        results = list(CaseService.get_high_risk_open_cases())
        self.assertIn(high_open, results)
        self.assertNotIn(low_open, results)
        self.assertNotIn(high_closed, results)


# ── CaseService.get_dashboard_stats ──────────────────────────────────────────
class DashboardStatsTest(TestCase):

    def test_stats_match_database_state(self):
        p = make_person()
        Case.objects.create(case_number='C1', young_person=p, status='open')
        Case.objects.create(case_number='C2', young_person=p, status='closed')
        stats = CaseService.get_dashboard_stats()
        self.assertEqual(stats['total_cases'], 2)
        self.assertEqual(stats['open_cases'], 1)
        self.assertEqual(stats['total_clients'], 1)

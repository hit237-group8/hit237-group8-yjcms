"""
cases/tests/test_views.py
Owner: Rohan (Technical Lead)

Tests for view permission boundaries and HTTP behaviour. (ADR-008)

What IS tested (meaningful):
  - Authentication enforcement: every URL redirects unauthenticated users
    Verifies LoginRequiredMixin is actually applied — not just declared
  - Unauthenticated POST does not create records
    Verifies auth gate intercepts before form processing (security boundary)
  - Authenticated users receive HTTP 200 on all views
  - Create view saves record and redirects (full create cycle)
  - List search returns correct subset (verifies Q-object OR logic)
  - Detail view returns 404 for non-existent pk (get_object_or_404)
  - Status filter returns only matching cases

What is NOT tested:
  - Exact HTML content (fragile, low value)
  - Django's built-in form validation (not our code)
  - Database constraints (test_models.py covers that)
  - Service layer rules (test_services.py covers that)
"""

from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User

from cases.models import Caseworker, YoungPerson, Case, Program


# ── Helpers ────────────────────────────────────────────────────────────────────
def make_user(username='viewer', password='pass123'):
    return User.objects.create_user(username=username, password=password)

def make_young_person(first='Test', last='Client'):
    return YoungPerson.objects.create(
        first_name=first, last_name=last,
        date_of_birth=date(2008, 1, 1), gender='M'
    )

def make_case(person, number='C001', status='open'):
    return Case.objects.create(
        case_number=number, young_person=person, status=status
    )


# ── Unauthenticated GET — authentication boundary ────────────────────────────
class UnauthenticatedGetTest(TestCase):
    """
    Every view must redirect unauthenticated users to login.
    Tests that LoginRequiredMixin is actually applied to every view class.
    A failure here means a URL is publicly accessible — a security bug.
    """

    def setUp(self):
        self.c = Client()

    def _assert_redirects_to_login(self, url):
        response = self.c.get(url)
        self.assertIn(response.status_code, [301, 302])
        self.assertIn('/accounts/login/', response['Location'])

    def test_dashboard_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('dashboard'))

    def test_client_list_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('youngperson-list'))

    def test_case_list_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('case-list'))

    def test_program_list_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('program-list'))

    def test_caseworker_list_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('caseworker-list'))

    def test_client_create_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('youngperson-create'))

    def test_client_export_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('youngperson-export'))

    def test_case_create_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('case-create'))

    def test_case_export_redirects_unauthenticated(self):
        self._assert_redirects_to_login(reverse('case-export'))

    def test_case_close_redirects_unauthenticated(self):
        p = make_young_person()
        case = make_case(p)
        self._assert_redirects_to_login(reverse('case-close', args=[case.pk]))


# ── Unauthenticated POST — security boundary ─────────────────────────────────
class UnauthenticatedPostTest(TestCase):
    """
    An unauthenticated POST must not create any record.
    LoginRequiredMixin must intercept before form processing.
    If it didn't, anyone could create records without logging in.
    """

    def setUp(self):
        self.c = Client()

    def test_unauthenticated_post_does_not_create_record(self):
        self.c.post(reverse('youngperson-create'), {
            'first_name': 'Hacker', 'last_name': 'Test',
            'date_of_birth': '2009-01-01', 'gender': 'M',
        })
        self.assertFalse(
            YoungPerson.objects.filter(first_name='Hacker').exists()
        )

    def test_unauthenticated_post_redirects(self):
        response = self.c.post(reverse('youngperson-create'), {
            'first_name': 'Hacker', 'last_name': 'Test',
            'date_of_birth': '2009-01-01', 'gender': 'M',
        })
        self.assertIn(response.status_code, [301, 302])


# ── Authenticated access ───────────────────────────────────────────────────────
class AuthenticatedDashboardTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.c = Client()
        self.c.login(username='viewer', password='pass123')

    def test_dashboard_returns_200(self):
        response = self.c.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_uses_correct_template(self):
        response = self.c.get(reverse('dashboard'))
        self.assertTemplateUsed(response, 'cases/dashboard.html')

    def test_dashboard_context_has_stats_from_service(self):
        """
        Dashboard context must contain all keys from CaseService.get_dashboard_stats().
        Verifies the view correctly passes service output to template.
        """
        response = self.c.get(reverse('dashboard'))
        for key in ['total_cases', 'open_cases', 'pending_cases', 'total_clients', 'total_programs']:
            self.assertIn(key, response.context)


class AuthenticatedClientViewTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.c = Client()
        self.c.login(username='viewer', password='pass123')

    def test_client_list_returns_200(self):
        response = self.c.get(reverse('youngperson-list'))
        self.assertEqual(response.status_code, 200)

    def test_client_search_returns_correct_subset(self):
        """
        The Q-object OR search must return Alice when searching 'Alice'
        and not return Bob. Verifies Q-object OR logic, not just that
        search accepts a parameter.
        """
        make_young_person('Alice', 'Jones')
        make_young_person('Bob', 'Smith')
        response = self.c.get(reverse('youngperson-list'), {'q': 'Alice'})
        self.assertEqual(response.context['clients'].count(), 1)
        self.assertEqual(response.context['clients'].first().first_name, 'Alice')

    def test_client_detail_returns_200(self):
        p = make_young_person()
        response = self.c.get(reverse('youngperson-detail', args=[p.pk]))
        self.assertEqual(response.status_code, 200)

    def test_client_detail_404_for_nonexistent_pk(self):
        """
        DetailView must return 404 for a non-existent pk.
        Verifies get_object_or_404 is working correctly.
        """
        response = self.c.get(reverse('youngperson-detail', args=[99999]))
        self.assertEqual(response.status_code, 404)

    def test_client_export_returns_csv(self):
        make_young_person('Alice', 'Jones')
        response = self.c.get(reverse('youngperson-export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="youth-justice-clients.csv"', response['Content-Disposition'])
        self.assertIn('Alice', response.content.decode())


class AuthenticatedCaseViewTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.c = Client()
        self.c.login(username='viewer', password='pass123')

    def test_case_list_returns_200(self):
        response = self.c.get(reverse('case-list'))
        self.assertEqual(response.status_code, 200)

    def test_case_list_filter_by_status_correct_subset(self):
        """
        Status filter must return only cases with matching status.
        Verifies filter logic in get_queryset(), not just that the
        filter parameter is accepted.
        """
        p = make_young_person()
        make_case(p, 'C001', 'open')
        make_case(p, 'C002', 'closed')
        response = self.c.get(reverse('case-list'), {'status': 'open'})
        cases = list(response.context['cases'])
        self.assertTrue(all(c.status == 'open' for c in cases))

    def test_case_detail_returns_200(self):
        p = make_young_person()
        c = make_case(p)
        response = self.c.get(reverse('case-detail', args=[c.pk]))
        self.assertEqual(response.status_code, 200)

    def test_case_export_returns_csv(self):
        p = make_young_person()
        make_case(p, 'C-EXPORT', 'open')
        response = self.c.get(reverse('case-export'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="youth-justice-cases.csv"', response['Content-Disposition'])
        self.assertIn('C-EXPORT', response.content.decode())

    def test_close_case_post_closes_open_case(self):
        """
        POSTing to the close endpoint must delegate to CaseService and set
        the terminal status/date. This covers the HTTP-to-service boundary.
        """
        p = make_young_person()
        c = make_case(p, 'C-CLOSE', 'open')
        response = self.c.post(reverse('case-close', args=[c.pk]))
        c.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(c.status, 'closed')
        self.assertIsNotNone(c.closed_date)


class CreateClientViewTest(TestCase):

    def setUp(self):
        self.user = make_user()
        self.c = Client()
        self.c.login(username='viewer', password='pass123')

    def test_create_get_returns_200(self):
        response = self.c.get(reverse('youngperson-create'))
        self.assertEqual(response.status_code, 200)

    def test_create_post_saves_and_redirects(self):
        """
        Valid POST must create the record and redirect.
        Verifies full create cycle: form → save → redirect.
        """
        response = self.c.post(reverse('youngperson-create'), {
            'first_name': 'New', 'last_name': 'Client',
            'date_of_birth': '2009-05-15', 'gender': 'M',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            YoungPerson.objects.filter(first_name='New', last_name='Client').exists()
        )

    def test_create_invalid_data_re_renders_form(self):
        """Missing required fields must re-render the form with HTTP 200."""
        response = self.c.post(reverse('youngperson-create'), {
            'first_name': '', 'last_name': '',
        })
        self.assertEqual(response.status_code, 200)

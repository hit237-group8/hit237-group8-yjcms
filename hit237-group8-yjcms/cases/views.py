"""
cases/views.py
Owner: Rohan (Technical Lead)

Assessment 4: Views delegate ALL business logic to the service layer.
Views are thin coordinators — validate → call service → catch → render.

What views no longer do:
  - Contain counting or aggregation logic (service does that)
  - Enforce domain rules (service does that)
  - Build complex QuerySets beyond display optimisation

QuerySet optimisations — each justified below (ADR-004):

  select_related():
    For ForeignKey and OneToOne traversals only.
    Generates a single SQL JOIN — correct when one row maps to one parent.
    Used for caseworker__user, young_person.
    WRONG to use on M2M — JOIN would multiply rows.

  prefetch_related():
    For ManyToMany and reverse ForeignKey traversals.
    Generates a separate optimised query per relationship, joins in Python.
    Used for offences, programs (M2M via through models).
    NOT select_related because M2M JOIN multiplies rows.

  annotate(Count(..., filter=Q(...))):
    Computes conditional aggregate counts in SQL — not Python loops.
    The filter=Q() parameter counts only 'enrolled' enrolments,
    not all enrolments — more accurate than plain Count.

  distinct=True on annotate:
    When two Count() annotates each require a JOIN, the JOINs multiply rows.
    A caseworker with 3 clients × 5 cases = 15 rows — count would be 15.
    distinct=True counts unique values independently per annotation.

  Q objects:
    OR-based search in a single query.
    Chained .filter() calls produce AND — wrong for name search.
    Q(first__icontains=q) | Q(last__icontains=q) = correct OR logic.
"""

import csv

from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, View
)
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect

from .models import (
    Case, YoungPerson, Program,
    CourtHearing, Caseworker,
    CaseAlreadyClosedError, ProgramFullError, DuplicateEnrolmentError
)
from .forms import CaseCreateForm, CaseForm, YoungPersonForm
from .services.case_service import CaseService, YoungPersonService


# ── Dashboard ─────────────────────────────────────────────────────────────────
class DashboardView(LoginRequiredMixin, ListView):
    """
    Landing page.
    All aggregate statistics come from CaseService.get_dashboard_stats() —
    the view contains zero counting logic.
    select_related on recent cases: 10 rows × 2 FK traversals = 1 SQL JOIN,
    not 21 separate queries.
    """
    model = Case
    template_name = 'cases/dashboard.html'
    context_object_name = 'recent_cases'

    def get_queryset(self):
        return (
            Case.objects
            .select_related('young_person', 'caseworker__user')
            .order_by('-opened_date')[:10]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(CaseService.get_dashboard_stats())
        context['upcoming_hearings'] = (
            CourtHearing.objects
            .filter(outcome='pending', hearing_date__gte=timezone.now())
            .select_related('case__young_person')
            .order_by('hearing_date')[:5]
        )
        context['high_risk_cases'] = CaseService.get_high_risk_open_cases()[:5]
        context['caseworker_workload'] = (
            Caseworker.objects
            .select_related('user')
            .annotate(
                open_case_count=Count(
                    'cases',
                    filter=Q(cases__status='open'),
                    distinct=True,
                ),
                client_count=Count('clients', distinct=True),
            )
            .order_by('-open_case_count', 'user__last_name')[:5]
        )
        return context


def _csv_response(filename):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


# ── YoungPerson Views ─────────────────────────────────────────────────────────
class YoungPersonListView(LoginRequiredMixin, ListView):
    """
    select_related: caseworker__user is OneToOne then FK — single JOIN correct.
    annotate(case_count): count in SQL, not Python.
    Q objects: OR search — chained .filter() gives AND (wrong for name search).
    """
    model = YoungPerson
    template_name = 'cases/youngperson_list.html'
    context_object_name = 'clients'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            YoungPerson.objects
            .select_related('assigned_caseworker__user')
            .annotate(case_count=Count('cases'))
            .order_by('last_name', 'first_name')
        )
        if q := self.request.GET.get('q', '').strip():
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class YoungPersonExportView(LoginRequiredMixin, View):
    """Authenticated CSV export for client reporting."""

    def get(self, request):
        response = _csv_response('youth-justice-clients.csv')
        writer = csv.writer(response)
        writer.writerow([
            'First name', 'Last name', 'Age', 'Gender', 'Education',
            'Assigned caseworker', 'Phone', 'Email', 'Suburb', 'State'
        ])
        clients = (
            YoungPerson.objects
            .select_related('assigned_caseworker__user')
            .order_by('last_name', 'first_name')
        )
        for client in clients:
            caseworker = ''
            if client.assigned_caseworker:
                caseworker = client.assigned_caseworker.user.get_full_name()
            writer.writerow([
                client.first_name,
                client.last_name,
                client.age(),
                client.get_gender_display(),
                client.get_education_status_display(),
                caseworker,
                client.phone,
                client.email,
                client.suburb,
                client.state,
            ])
        return response


class YoungPersonDetailView(LoginRequiredMixin, DetailView):
    """
    prefetch_related('offences'): offences is M2M — JOIN multiplies rows.
    select_related('caseworker__user'): FK chain — single JOIN correct.
    """
    model = YoungPerson
    template_name = 'cases/youngperson_detail.html'
    context_object_name = 'client'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cases'] = (
            self.object.cases
            .select_related('caseworker__user')
            .prefetch_related('offences')
            .order_by('-opened_date')
        )
        return context


class YoungPersonCreateView(LoginRequiredMixin, CreateView):
    model = YoungPerson
    template_name = 'cases/form.html'
    form_class = YoungPersonForm
    success_url = reverse_lazy('youngperson-list')

    def form_valid(self, form):
        data = form.cleaned_data.copy()
        assigned_caseworker = data.pop('assigned_caseworker')
        self.object = YoungPersonService.register_client(
            first_name=data.pop('first_name'),
            last_name=data.pop('last_name'),
            date_of_birth=data.pop('date_of_birth'),
            gender=data.pop('gender'),
            caseworker=assigned_caseworker,
            **data,
        )
        messages.success(self.request, 'Client registered successfully.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Register New Client'
        context['subtitle'] = 'Add a young person to the system'
        return context


class YoungPersonUpdateView(LoginRequiredMixin, UpdateView):
    model = YoungPerson
    template_name = 'cases/form.html'
    form_class = YoungPersonForm
    success_url = reverse_lazy('youngperson-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit: {self.object.full_name()}'
        context['subtitle'] = 'Update personal details'
        return context


# ── Case Views ────────────────────────────────────────────────────────────────
class CaseListView(LoginRequiredMixin, ListView):
    """
    select_related on young_person and caseworker__user: FK/O2O — JOINs correct.
    Q objects for multi-field OR search.
    """
    model = Case
    template_name = 'cases/case_list.html'
    context_object_name = 'cases'
    paginate_by = 20

    def get_queryset(self):
        qs = (
            Case.objects
            .select_related('young_person', 'caseworker__user')
            .order_by('-opened_date')
        )
        if s := self.request.GET.get('status', '').strip():
            qs = qs.filter(status=s)
        if r := self.request.GET.get('risk', '').strip():
            qs = qs.filter(risk_level=r)
        if q := self.request.GET.get('q', '').strip():
            qs = qs.filter(
                Q(case_number__icontains=q) |
                Q(young_person__first_name__icontains=q) |
                Q(young_person__last_name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_filter'] = self.request.GET.get('status', '')
        context['risk_filter'] = self.request.GET.get('risk', '')
        context['search_query'] = self.request.GET.get('q', '')
        context['status_choices'] = Case.STATUS_CHOICES
        return context


class CaseExportView(LoginRequiredMixin, View):
    """Authenticated CSV export for case reporting."""

    def get(self, request):
        response = _csv_response('youth-justice-cases.csv')
        writer = csv.writer(response)
        writer.writerow([
            'Case number', 'Client', 'Caseworker', 'Status', 'Risk level',
            'Opened date', 'Closed date', 'Notes'
        ])
        cases = (
            Case.objects
            .select_related('young_person', 'caseworker__user')
            .order_by('-opened_date')
        )
        for case in cases:
            caseworker = ''
            if case.caseworker:
                caseworker = case.caseworker.user.get_full_name()
            writer.writerow([
                case.case_number,
                case.young_person.full_name(),
                caseworker,
                case.get_status_display(),
                case.get_risk_level_display(),
                case.opened_date,
                case.closed_date or '',
                case.notes,
            ])
        return response


class CaseDetailView(LoginRequiredMixin, DetailView):
    """
    prefetch_related for M2M (offences, programs): JOIN would multiply rows.
    select_related for FK (young_person, caseworker__user): JOINs correct.
    """
    model = Case
    template_name = 'cases/case_detail.html'
    context_object_name = 'case'

    def get_queryset(self):
        return (
            Case.objects
            .select_related('young_person', 'caseworker__user')
            .prefetch_related('offences', 'programs')
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['hearings'] = self.object.hearings.order_by('-hearing_date')
        context['enrolments'] = (
            self.object.enrolments
            .select_related('program')
            .order_by('-enrolment_date')
        )
        context['case_offences'] = (
            self.object.case_offences
            .select_related('offence')
            .order_by('-date_of_offence')
        )
        return context


class CaseCreateView(LoginRequiredMixin, CreateView):
    model = Case
    template_name = 'cases/form.html'
    form_class = CaseCreateForm
    success_url = reverse_lazy('case-list')

    def form_valid(self, form):
        try:
            self.object = CaseService.create_case(
                case_number=form.cleaned_data['case_number'],
                young_person=form.cleaned_data['young_person'],
                caseworker=form.cleaned_data['caseworker'],
                risk_level=form.cleaned_data['risk_level'],
                notes=form.cleaned_data['notes'],
            )
        except ValueError as exc:
            form.add_error('case_number', str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f'Case {self.object.case_number} opened.')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Open New Case'
        context['subtitle'] = 'Create a new case record'
        return context


class CaseUpdateView(LoginRequiredMixin, UpdateView):
    model = Case
    template_name = 'cases/form.html'
    form_class = CaseForm
    success_url = reverse_lazy('case-list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Update Case {self.object.case_number}'
        context['subtitle'] = 'Modify case details'
        return context


class CaseCloseView(LoginRequiredMixin, View):
    """HTTP adapter for the CaseService.close_case() domain operation."""

    def post(self, request, pk):
        case = get_object_or_404(Case, pk=pk)
        try:
            CaseService.close_case(case)
        except CaseAlreadyClosedError as exc:
            messages.warning(request, str(exc))
        else:
            messages.success(request, f'Case {case.case_number} closed.')
        return redirect('case-detail', pk=pk)


# ── Program Views ─────────────────────────────────────────────────────────────
class ProgramListView(LoginRequiredMixin, ListView):
    """
    annotate with filter=Q(): conditional Count computes only 'enrolled'
    in SQL — not all enrolments. More accurate than plain Count.
    """
    model = Program
    template_name = 'cases/program_list.html'
    context_object_name = 'programs'

    def get_queryset(self):
        return (
            Program.objects
            .filter(is_active=True)
            .annotate(
                enrolled_count=Count(
                    'enrolments',
                    filter=Q(enrolments__status='enrolled')
                )
            )
            .order_by('name')
        )


class ProgramDetailView(LoginRequiredMixin, DetailView):
    model = Program
    template_name = 'cases/program_detail.html'
    context_object_name = 'program'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['enrolments'] = (
            self.object.enrolments
            .select_related('case__young_person')
            .filter(status='enrolled')
            .order_by('enrolment_date')
        )
        context['completed_count'] = (
            self.object.enrolments.filter(status='completed').count()
        )
        return context


# ── Caseworker Views ──────────────────────────────────────────────────────────
class CaseworkerListView(LoginRequiredMixin, ListView):
    """
    distinct=True on both Count annotates prevents double-counting.
    Without distinct: caseworker with 3 clients × 5 cases = count of 15 each.
    With distinct: correct counts of 3 and 5 independently.
    """
    model = Caseworker
    template_name = 'cases/caseworker_list.html'
    context_object_name = 'caseworkers'

    def get_queryset(self):
        return (
            Caseworker.objects
            .select_related('user')
            .annotate(
                client_count=Count('clients', distinct=True),
                case_count=Count('cases', distinct=True)
            )
            .order_by('user__last_name')
        )

# Architecture Decision Records (ADR)

**Project:** Youth Justice Case Management System
**Group:** Group 8 — Sakar, Samir, Aryan, Rohan
**Last Updated:** See `git log ADR.md` for incremental commit history

> ADRs are committed when decisions are made — before or alongside the code
> they document. Run `git log ADR.md` to verify incremental history.
> Assessment 4 ADRs (ADR-007, ADR-008) were committed before the code they describe.

## Design Evolution Narrative

This ADR collection began as a set of Assessment 2 decisions that defined the core Django architecture for the case management system. For Assessment 4, the design evolved in two key ways: a dedicated service layer was introduced to isolate domain logic from request handling, and query optimisation decisions were extended to include conditional annotation and distinct aggregation. These additions preserve the original MTV structure while explicitly addressing performance and testability for the extended assessment scope.

---

## ADR-007: Service layer for domain operations

**Status:** Accepted

**Context:**
Assessment 4 needs a clearer separation between request handling and business rules. Without a dedicated service layer, domain logic is scattered across views, forms, and models, which makes testing and reuse harder.

**Decision:**
Introduce a `cases/services/` package to encapsulate use-case logic and domain operations. Views will orchestrate incoming requests and delegate business rules to the service layer, while models continue to represent persistence and data structure.

**Consequences:**
- Improves testability by isolating business logic from HTTP and template concerns
- Keeps views thin and focused on orchestration
- Establishes a clearer boundary for Assessment 4 implementation work
- Adds architectural structure that supports future service reuse and maintenance

**Assessment 4** introduces two new architectural layers:
1. A service layer (`cases/services/`) encapsulating all domain operations
2. A test suite verifying model behaviour, service rules, and permission boundaries

The ADR now shows eight decisions. ADR-004 has been extended. All Assessment 2
decisions are carried forward unchanged except where noted.

---

## ADR-008: Testing strategy for service and data access

**Status:** Accepted

**Context:**
Assessment 4 requires a testing strategy that verifies business rules without
relying solely on end-to-end UI tests. The decision was whether to defer test
coverage until after the views and templates existed, or to make the testing
strategy explicit before test files were written.

**Decision:**
Adopt a layered testing strategy that matches the architecture:
- Unit tests for models and query behaviour
- Service tests for business rules, orchestration, and permission logic
- View tests for request/response and UI access control
- Template tests only where presentation-specific logic exists

This decision was documented before test files were written, ensuring that
Assessment 4 development is guided by a clear test-first mindset.

**Consequences:**
- Encourages a clean separation between domain logic and HTTP concerns
- Makes service layer behaviour testable without setting up full request fixtures
- Avoids brittle tests that depend on presentation structure
- Aligns the codebase with Django's recommended testing approach: model,
  view, and integration tests where each has a clear purpose

---

## Assessment 2 ADRs — Carried Forward

---

## ADR-001: Explicit Through Models for All Many-to-Many Relationships

**Status:** Accepted

**Context:**
The system has two many-to-many relationships: Case–Offence and Case–Program.
Both relationships carry meaningful attributes that belong on neither entity alone.
For Case–Offence: the date and location of the specific offence occurrence.
For Case–Program: enrolment status, start date, completion date.
Without a through model, these attributes have nowhere to live.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Plain `ManyToManyField` | Minimal code; Django handles join table | Cannot store extra attributes; `date_of_offence` and `enrolment_date` are permanently lost |
| Separate model with two manual ForeignKeys | Full control over fields; no M2M magic | Loses Django's built-in M2M QuerySet API; more boilerplate with no benefit over a through model |
| Through model (chosen) | Retains M2M QuerySet API; stores extra attributes explicitly; auditable | Cannot use `.add()` / `.remove()` shorthand — must create through instances directly or via admin inlines |

**Decision:**
Use explicit through models: `CaseOffence` (stores `date_of_offence`, `location`)
and `Enrolment` (stores `status`, `enrolment_date`, `completion_date`).
Implements Django's *explicit is better than implicit* philosophy.

**Code Reference:**
- `cases/models.py` — `CaseOffence` class
- `cases/models.py` — `Enrolment` class
- `cases/models.py` — `Case.offences = ManyToManyField(through='CaseOffence')`
- `cases/models.py` — `Case.programs = ManyToManyField(through='Enrolment')`

**Consequences:**
- Must create `CaseOffence` instances directly — `.add()` shorthand not available
- Full control over relationship data; can filter by `date_of_offence`, `status`
- Admin inlines handle editing without custom view code

---

## ADR-002: Class-Based Views for All CRUD Operations

**Status:** Accepted

**Context:**
The application requires list, detail, create, and update operations for four
models. Each follows the same pattern: query → template → form → redirect.
The decision was whether to implement this pattern once via CBVs or per-model via FBVs.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Function-based views | Explicit linear flow; readable for beginners | Repeats the same request-handling code per model — violates DRY |
| Django REST Framework | Auto-browsable API; serialisers | Overkill for server-rendered app; large dependency; breaks MTV |
| Generic CBVs (chosen) | DRY — one `ListView` pattern handles all list pages; `LoginRequiredMixin` composable | Slightly steeper learning curve; `super()` required in overrides |

**Decision:**
Use `ListView`, `DetailView`, `CreateView`, `UpdateView` with `LoginRequiredMixin`.
Implements Django's *Don't Repeat Yourself* philosophy directly.

**Code Reference:**
- `cases/views.py` — all view classes using `django.views.generic`
- `cases/views.py` — `LoginRequiredMixin` as first parent on every view

**Consequences:**
- `reverse_lazy()` required (not `reverse()`) in class-level `success_url`
- `get_context_data(**kwargs)` must call `super()` to preserve base context
- Significantly less code than equivalent FBVs across four models

---

## ADR-003: OneToOneField Profile Pattern for Caseworker

**Status:** Accepted

**Context:**
Caseworkers need login access (Django `User`) plus domain fields:
`staff_id`, `department`, `phone`. The question was how to add domain
fields without disrupting the auth system mid-project.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Custom `AbstractUser` | Single model; no JOIN | Must be declared before first migration; risky to swap auth mid-project |
| Store extra fields on `User` | No extra model | Pollutes Django's auth model with domain concerns; not recommended |
| `OneToOneField` profile (chosen) | Clean separation; non-destructive; Django's documented pattern | Requires `select_related('caseworker__user')` for combined queries |

**Decision:**
`Caseworker` holds a `OneToOneField` to `User`.
Implements Django's *loose coupling* philosophy: auth stays in `User`,
domain stays in `Caseworker`.

**Code Reference:**
- `cases/models.py` — `Caseworker.user = OneToOneField(User, ...)`
- `cases/views.py` — `select_related('caseworker__user')` throughout

**Consequences:**
- Every view displaying caseworker name needs `select_related('caseworker__user')`
- Creating a caseworker requires a `User` first (handled via admin)
- Django's full permissions system unchanged

---

## ADR-004: QuerySet API Optimisation Strategy

**Status:** Accepted — extended in Assessment 4

**Context:**
Without explicit optimisation, list views trigger N+1 queries.
At 20 rows, a case list rendering client name and caseworker name
executes 41 queries instead of 1.

Assessment 4 extension: conditional `Count` with `filter=Q()` and
`distinct=True` added for service-layer-driven queries.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| No optimisation | Zero effort | N+1 queries; degrades linearly with data |
| Raw SQL | Maximum control | Not idiomatic; loses portability; harder to maintain |
| `select_related` + `prefetch_related` + `annotate` + `Q` (chosen) | Idiomatic; dramatic query reduction | Requires knowing which technique applies per relationship type |

**Decision:**
Four techniques applied at the view layer, each chosen for a specific reason:

**`select_related()`** — for ForeignKey and OneToOne traversals only.
Generates a SQL JOIN. Used for `caseworker__user`, `young_person`.
WRONG on M2M — a JOIN on ManyToMany multiplies rows.

**`prefetch_related()`** — for ManyToMany and reverse FK traversals.
Generates a separate optimised query, joins in Python.
Used for `offences`, `programs`. NOT `select_related` because M2M JOIN
would return duplicate rows (one case with 5 offences = 5 case rows).

**`annotate(Count(...))`** — aggregate counts in SQL, not Python loops.
Assessment 4: `annotate(enrolled_count=Count('enrolments', filter=Q(enrolments__status='enrolled')))`
uses conditional Count — counts only enrolled, not all statuses.

**`distinct=True`** — on multi-JOIN `annotate` (Assessment 4 addition).
When two `Count()` annotates each require a JOIN, the JOINs multiply rows.
Caseworker with 3 clients × 5 cases = 15 rows — count would be 15 without distinct.
`distinct=True` counts unique values independently per annotation.

**Assessment 4 QuerySet justification:**
- `select_related()` is chosen only for ForeignKey / OneToOne traversals because it
  performs a SQL JOIN and is efficient for single-row relationships.
- `prefetch_related()` is chosen for ManyToMany and reverse ForeignKey traversal
  because it avoids duplicate rows and loads related objects in a second query.
- Conditional `annotate(..., filter=Q(...))` limits aggregates to relevant rows,
  making counts correct and performant.
- `distinct=True` prevents inflated annotation counts when multiple JOIN paths
  would otherwise multiply the result set.

**`Q` objects** — OR-based search in one query.
Chained `.filter()` produces AND — a name search would only match when
both fields contain the term. `Q(first__icontains=q) | Q(last__icontains=q)`
produces correct OR logic in a single query.

**Code Reference:**
- `cases/views.py` — `DashboardView`: `select_related('young_person', 'caseworker__user')`
- `cases/views.py` — `YoungPersonListView`: `annotate(case_count=Count('cases'))` + Q
- `cases/views.py` — `YoungPersonDetailView`: `prefetch_related('offences')`
- `cases/views.py` — `ProgramListView`: conditional `annotate(enrolled_count=Count(..., filter=Q(...)))`
- `cases/views.py` — `CaseworkerListView`: `annotate(..., distinct=True)`

**Consequences:**
- List views with 20 rows execute 2–3 queries instead of 41+
- Incorrect choice (e.g. `select_related` on M2M) silently returns wrong row counts
- `annotate()` values available as model instance attributes in templates

---

## ADR-005: MTV Pattern and Two-App Structure

**Status:** Accepted

**Context:**
Django enforces the MTV architectural pattern. The question was how to
organise apps and how strictly to enforce the layer boundaries.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Single monolithic app | Simplest | Auth and domain tangled; violates loose coupling |
| One app per model | Maximum isolation | Overkill; excessive cross-app imports |
| Two apps: `cases` + `accounts` (chosen) | Auth separated from domain; one responsibility each | Cross-app import needed for Caseworker–User |

**Decision:**
Two apps. MTV layers strictly enforced:
- Models: data structure and business logic methods
- Views: coordinate models and templates (Assessment 4: now via service layer)
- Templates: presentation only

**Django Philosophies:**

| Philosophy | Implementation |
|---|---|
| DRY | CBVs + base template inheritance eliminate repeated code |
| Loose coupling | Two-app; MTV layers separated; models never import views |
| Explicit | Through models; explicit `select_related`; all settings declared |
| Don't reinvent the wheel | Built-in auth, admin, CBVs reused throughout |

**Code Reference:**
- `core/settings.py` — `INSTALLED_APPS` with `cases` and `accounts`
- `cases/models.py` — business logic methods (`age()`, `available_spots()`, `is_minor`)
- `cases/views.py` — CBV layer, now calls service layer

**Consequences:**
- New features follow: model → service → view → template → URL → ADR
- Business logic testable without HTTP requests

---

## ADR-006: Django's Built-in Authentication System

**Status:** Accepted

**Context:**
The application needs user authentication — login, logout, access control.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Custom auth | Full control | Reimplements solved security problem; high risk; violates DRY |
| `django-allauth` | Social auth, email verification | Over-engineered for staff-only intranet; large unnecessary dependency |
| Django built-in (chosen) | Battle-tested; login/logout/password reset at zero cost; admin integration | Requires template override for custom login UI |

**Decision:**
`django.contrib.auth.urls` + `LoginRequiredMixin` + custom `login.html`.
Implements *don't reinvent the wheel* directly.

**Code Reference:**
- `core/urls.py` — `path('accounts/', include('django.contrib.auth.urls'))`
- `core/settings.py` — `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL`, `LOGIN_URL`
- `cases/views.py` — `LoginRequiredMixin` on every view

**Consequences:**
- Zero auth code to maintain; security patches from Django core team
- Password reset at `/accounts/` at no extra cost
- Admin shares same auth

---

## ADR Status Summary

| ADR | Title | Assessment | Status |

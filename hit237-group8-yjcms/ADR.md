# Architecture Decision Records (ADR)

**Project:** Youth Justice Case Management System
**Group:** Group 8 — Sakar, Samir, Aryan, Rohan
**Last Updated:** See `git log ADR.md` for incremental commit history

> ADRs are committed when decisions are made — before or alongside the code
> they document. Run `git log ADR.md` to verify incremental history.
> Assessment 4 ADRs (ADR-007, ADR-008) were committed before the code they describe.

**Assessment 4** introduces two new architectural layers:
1. A service layer (`cases/services/`) encapsulating all domain operations
2. A test suite verifying model behaviour, service rules, and permission boundaries

The ADR now shows eight decisions. ADR-004 has been extended. All Assessment 2
decisions are carried forward unchanged except where noted.

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

## Assessment 4 ADRs — New

---

## ADR-007: Service Layer Architecture

**Status:** Accepted

**Context:**
As the application grows with more complex business rules (capacity limits,
case closure restrictions, duplicate prevention), placing logic in views
creates three problems:

1. Views violate Single Responsibility Principle — responsible for both
   HTTP handling and domain rule enforcement simultaneously
2. The same rule cannot be reused without copying code across views
3. Domain rules cannot be tested without spinning up an HTTP request context

In Assessment 2, all cross-model logic sat in views or model methods. There
was no dedicated encapsulation layer. Assessment 4 requires one.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| Logic in views | No extra layer; fewer files | Views become fat and untestable without HTTP; rules duplicated when multiple views need them; violates SRP |
| Logic in fat models | Close to data; no extra layer | Cross-model operations (e.g. checking Program capacity when creating Enrolment) require circular imports between models; models become too large |
| Service layer (chosen) | Single responsibility per layer; domain rules testable without HTTP; views become thin; reusable by views, admin, management commands | One extra module layer; developers must learn layer boundaries |

**Decision:**
Introduce `cases/services/case_service.py` containing `CaseService` and
`YoungPersonService`. Services:
- Accept domain objects (not HTTP request data)
- Raise named domain exceptions (`CaseAlreadyClosedError`, `ProgramFullError`,
  `DuplicateEnrolmentError`) for every invariant violation
- Use `@transaction.atomic` on operations that write multiple records

View pattern after this decision:
```
1. View validates form input
2. View calls service method with domain objects
3. Service enforces domain rules, raises named exception on violation
4. View catches exception, adds message, redirects or re-renders
5. View never contains if/else domain logic
```

The `@transaction.atomic` on `enrol_in_program()` is a deliberate non-trivial
choice. Without it, if the database write fails after all three domain checks
pass, no capacity is consumed but the state is inconsistent. With it, the entire
operation rolls back atomically. It also prevents a race condition where two
simultaneous requests both pass the `is_full()` check before either creates
the `Enrolment` row — without atomicity, both would succeed and exceed capacity.

Domain exceptions are placed in `models.py` (not `services.py`) to avoid
circular imports. Both services and tests import from models — safe in both
directions.

**Code Reference:**
- `cases/services/case_service.py` — `CaseService` (all static methods)
- `cases/services/case_service.py` — `YoungPersonService`
- `cases/models.py` — top of file: `CaseAlreadyClosedError`, `ProgramFullError`,
  `DuplicateEnrolmentError`, `CaseworkerNotFoundError`
- `cases/views.py` — views calling service and catching exceptions

**Consequences:**
- Views are thin: validate → call service → catch exception → redirect or render
- Domain rules defined once; reusable by any caller
- New business rules require only a service method + test; views rarely change
- `@transaction.atomic` prevents race conditions and partial writes on enrolment

---

## ADR-008: Testing Strategy

**Status:** Accepted

**Context:**
Assessment 4 requires a meaningful test suite. The critical design question
is what constitutes meaningful versus trivial. The assessment brief explicitly
warns: "AI-generated test suites that merely assert trivial conditions will not
earn credit." We needed a principled approach to what to test and why.

**Alternatives Considered:**

| Option | Pros | Cons |
|--------|------|------|
| No tests | Fastest | Not permitted; no confidence in correctness |
| 100% code coverage | Exhaustive | Incentivises trivial tests (testing `__str__`, testing Django saving); diminishing returns |
| Behaviour-focused tests at three layers (chosen) | Tests what our code does; skips Django internals; fast; readable as documentation | Requires discipline to avoid testing obvious things |

**Decision:**
Three test files targeting distinct layers of behaviour:

**`test_models.py`** — model business logic we wrote:
- `age()` birthday boundary formula
- `is_minor` at age 18 boundary
- `full_address` blank field handling
- `active_case_count()` filtering by 'open' only
- `available_spots()` filtering by 'enrolled' only (not completed/withdrawn)
- `Case.is_open()` for all status values
- `Case.clean()` validation rule
- `unique_together` constraints

**`test_services.py`** — service layer domain rules:
- Happy path for each service method
- Every named exception raised under the correct condition
- Non-obvious rules: completed/withdrawn enrolments do not block capacity
- `@transaction.atomic`: duplicate does not leave inconsistent state

**`test_views.py`** — permission boundaries and HTTP behaviour:
- Every URL redirects unauthenticated users to login
- Unauthenticated POST does not create records (security boundary)
- Authenticated users receive HTTP 200
- Create view saves and redirects (full cycle)
- Search returns correct subset (verifies Q-object OR logic)
- 404 for non-existent pk

**What is NOT tested (and why):**
- `__str__` returning a string — Django guarantee, not our logic
- Django saving a field to the database — Django's ORM
- Admin page rendering — integration concern, brittle
- Django's form validation — not our validators
- Database connection reliability — infrastructure

**Running the suite:**
```
python manage.py test cases.tests               # all
python manage.py test cases.tests.test_models   # models only
python manage.py test cases.tests.test_services # services only
python manage.py test cases.tests.test_views    # views only
```

**Code Reference:**
- `cases/tests/test_models.py`
- `cases/tests/test_services.py`
- `cases/tests/test_views.py`

**Consequences:**
- Test suite runs fast — no browser, minimal HTTP overhead
- Each test documents a domain rule — readable as specification
- Failures point directly to broken business logic, not Django internals
- New service methods require a corresponding test (team contract)

---

## ADR Status Summary

| ADR | Title | Assessment | Status |
|-----|-------|-----------|--------|
| ADR-001 | Through models for M2M relationships | A2 | ✅ Accepted |
| ADR-002 | Class-Based Views for CRUD | A2 | ✅ Accepted |
| ADR-003 | OneToOneField profile for Caseworker | A2 | ✅ Accepted |
| ADR-004 | QuerySet optimisation strategy | A2, extended A4 | ✅ Accepted |
| ADR-005 | MTV pattern and two-app structure | A2 | ✅ Accepted |
| ADR-006 | Django built-in authentication | A2 | ✅ Accepted |
| ADR-007 | Service layer architecture | A4 | ✅ Accepted |
| ADR-008 | Testing strategy | A4 | ✅ Accepted |

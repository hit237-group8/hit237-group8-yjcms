# Django Philosophies in This Project

## DRY
- `cases/services/case_service.py` centralizes domain actions (`close_case`, `enrol_in_program`, `get_dashboard_stats`) so views reuse one source of business logic.
- `cases/views.py` reuses helper `_csv_response()` for export responses.
- `cases/models.py` keeps domain methods (`age`, `is_minor`, `available_spots`, `is_full`) on models to avoid repeating rules.

## Loose Coupling
- Views call service methods instead of embedding domain rules (`cases/views.py` uses `CaseService` and `YoungPersonService`).
- Services depend on models and exceptions, not on HTTP request/response logic (`cases/services/case_service.py`).
- URL routing is separated in `cases/urls.py` and composed in `core/urls.py`.

## Explicit Is Better Than Implicit
- Model choices are explicit (`Case.STATUS_CHOICES`, `Case.RISK_CHOICES`, `YoungPerson.EDUCATION_CHOICES`).
- Through models are explicit (`CaseOffence`, `Enrolment`) for many-to-many relationships.
- `Case.clean()` explicitly enforces closed-date invariants in the model layer.

## Don’t Reinvent the Wheel
- Django generic class-based views are used for list/detail/create/update flows (`cases/views.py`).
- Django auth routes are included via `django.contrib.auth.urls` in `core/urls.py`.
- Django `ModelForm` classes in `cases/forms.py` use built-in form rendering and validation.
- Django ORM query optimizations (`select_related`, `prefetch_related`, `annotate`) are used instead of manual SQL.

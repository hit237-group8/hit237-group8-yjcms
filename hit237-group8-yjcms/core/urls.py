"""Root URL configuration for the Youth Justice CMS project."""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    # ADR-006: include Django's built-in authentication routes.
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("cases.urls")),
    path("", RedirectView.as_view(pattern_name="login", permanent=False)),
]

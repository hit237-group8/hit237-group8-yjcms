"""Root URL configuration for the Youth Justice CMS project."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # ADR-006: include Django's built-in authentication routes.
    path("accounts/", include("django.contrib.auth.urls")),
    # Cases app: dashboard and all domain URLs.
    path("", include("cases.urls")),
]

from django.urls import path

from .views import (
    CaseCloseView,
    CaseCreateView,
    CaseDetailView,
    CaseExportView,
    CaseListView,
    CaseUpdateView,
    CaseworkerListView,
    DashboardView,
    ProgramDetailView,
    ProgramListView,
    YoungPersonCreateView,
    YoungPersonDetailView,
    YoungPersonExportView,
    YoungPersonListView,
    YoungPersonUpdateView,
)

urlpatterns = [
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("clients/", YoungPersonListView.as_view(), name="youngperson-list"),
    path("clients/export/", YoungPersonExportView.as_view(), name="youngperson-export"),
    path("clients/new/", YoungPersonCreateView.as_view(), name="youngperson-create"),
    path("clients/<int:pk>/", YoungPersonDetailView.as_view(), name="youngperson-detail"),
    path("clients/<int:pk>/edit/", YoungPersonUpdateView.as_view(), name="youngperson-update"),
    path("cases/", CaseListView.as_view(), name="case-list"),
    path("cases/export/", CaseExportView.as_view(), name="case-export"),
    path("cases/new/", CaseCreateView.as_view(), name="case-create"),
    path("cases/<int:pk>/", CaseDetailView.as_view(), name="case-detail"),
    path("cases/<int:pk>/edit/", CaseUpdateView.as_view(), name="case-update"),
    path("cases/<int:pk>/close/", CaseCloseView.as_view(), name="case-close"),
    path("programs/", ProgramListView.as_view(), name="program-list"),
    path("programs/<int:pk>/", ProgramDetailView.as_view(), name="program-detail"),
    path("caseworkers/", CaseworkerListView.as_view(), name="caseworker-list"),
]

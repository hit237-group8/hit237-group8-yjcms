from django.urls import path
from . import views

urlpatterns = [
    path('', views.DashboardView.as_view(), name='dashboard'),
    path('clients/', views.YoungPersonListView.as_view(), name='youngperson-list'),
    path('clients/export.csv', views.YoungPersonExportView.as_view(), name='youngperson-export'),
    path('clients/add/', views.YoungPersonCreateView.as_view(), name='youngperson-create'),
    path('clients/<int:pk>/', views.YoungPersonDetailView.as_view(), name='youngperson-detail'),
    path('clients/<int:pk>/edit/', views.YoungPersonUpdateView.as_view(), name='youngperson-update'),
    path('cases/', views.CaseListView.as_view(), name='case-list'),
    path('cases/export.csv', views.CaseExportView.as_view(), name='case-export'),
    path('cases/new/', views.CaseCreateView.as_view(), name='case-create'),
    path('cases/<int:pk>/', views.CaseDetailView.as_view(), name='case-detail'),
    path('cases/<int:pk>/edit/', views.CaseUpdateView.as_view(), name='case-update'),
    path('cases/<int:pk>/close/', views.CaseCloseView.as_view(), name='case-close'),
    path('programs/', views.ProgramListView.as_view(), name='program-list'),
    path('programs/<int:pk>/', views.ProgramDetailView.as_view(), name='program-detail'),
    path('caseworkers/', views.CaseworkerListView.as_view(), name='caseworker-list'),
]

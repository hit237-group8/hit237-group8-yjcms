from django.contrib import admin
from .models import (
    Caseworker, YoungPerson, Offence,
    Case, CaseOffence, CourtHearing, Program, Enrolment
)

class CaseOffenceInline(admin.TabularInline):
    model = CaseOffence
    extra = 1
    fields = ['offence', 'date_of_offence', 'location', 'details']

class CourtHearingInline(admin.TabularInline):
    model = CourtHearing
    extra = 1
    fields = ['hearing_date', 'court_name', 'judge', 'outcome', 'outcome_notes']

class EnrolmentInline(admin.TabularInline):
    model = Enrolment
    extra = 1
    fields = ['program', 'status', 'completion_date', 'notes']

@admin.register(Caseworker)
class CaseworkerAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'department', 'phone']
    search_fields = ['user__first_name', 'user__last_name', 'staff_id']

@admin.register(YoungPerson)
class YoungPersonAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'date_of_birth', 'gender', 'education_status', 'interpreter_required', 'assigned_caseworker']
    search_fields = ['first_name', 'last_name']
    list_filter = ['gender', 'indigenous_status', 'education_status']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ['case_number', 'young_person', 'caseworker', 'status', 'risk_level', 'opened_date']
    list_filter = ['status', 'risk_level']
    search_fields = ['case_number', 'young_person__first_name', 'young_person__last_name']
    readonly_fields = ['opened_date']
    inlines = [CaseOffenceInline, CourtHearingInline, EnrolmentInline]

@admin.register(Offence)
class OffenceAdmin(admin.ModelAdmin):
    list_display = ['name', 'severity', 'requires_court']
    list_filter = ['severity']

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ['name', 'program_type', 'duration_weeks', 'capacity', 'facilitator', 'is_active']
    list_filter = ['program_type', 'is_active']

@admin.register(CourtHearing)
class CourtHearingAdmin(admin.ModelAdmin):
    list_display = ['case', 'hearing_date', 'court_name', 'outcome']
    list_filter = ['outcome']

@admin.register(Enrolment)
class EnrolmentAdmin(admin.ModelAdmin):
    list_display = ['case', 'program', 'status', 'enrolment_date']
    list_filter = ['status']

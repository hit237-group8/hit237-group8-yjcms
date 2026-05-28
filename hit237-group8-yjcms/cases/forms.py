from django import forms

from .models import Case, YoungPerson


class YoungPersonForm(forms.ModelForm):
    class Meta:
        model = YoungPerson
        fields = [
            "first_name",
            "last_name",
            "date_of_birth",
            "gender",
            "street_address",
            "suburb",
            "state",
            "postcode",
            "phone",
            "email",
            "guardian_name",
            "guardian_phone",
            "guardian_email",
            "indigenous_status",
            "interpreter_required",
            "education_status",
            "assigned_caseworker",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["education_status"].required = False
        self.fields["education_status"].initial = self.fields["education_status"].initial or "unknown"



class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ["status", "risk_level", "notes", "caseworker", "closed_date"]
        widgets = {
            "closed_date": forms.DateInput(attrs={"type": "date"}),
        }


class CaseCreateForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = ["case_number", "young_person", "caseworker", "risk_level", "notes"]

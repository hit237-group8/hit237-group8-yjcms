from django import forms

from .models import Case, YoungPerson


class YoungPersonForm(forms.ModelForm):
    education_status = forms.ChoiceField(
        choices=YoungPerson.EDUCATION_CHOICES,
        required=False,
    )

    class Meta:
        model = YoungPerson
        fields = [
            'first_name',
            'last_name',
            'date_of_birth',
            'gender',
            'street_address',
            'suburb',
            'state',
            'postcode',
            'phone',
            'email',
            'guardian_name',
            'guardian_phone',
            'guardian_email',
            'indigenous_status',
            'interpreter_required',
            'education_status',
            'assigned_caseworker',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }

    def clean_education_status(self):
        return self.cleaned_data['education_status'] or 'unknown'


class CaseForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = [
            'case_number',
            'young_person',
            'caseworker',
            'status',
            'risk_level',
            'closed_date',
            'notes',
        ]
        widgets = {
            'closed_date': forms.DateInput(attrs={'type': 'date'}),
        }


class CaseCreateForm(forms.ModelForm):
    class Meta:
        model = Case
        fields = [
            'case_number',
            'young_person',
            'caseworker',
            'risk_level',
            'notes',
        ]

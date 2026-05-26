import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cases.models import Program

programs = [
    {'name': 'Youth Diversion Initiative', 'program_type': 'diversion', 'description': 'Early intervention program for first-time and low-risk offenders. Diverts young people from the formal justice system through community engagement and restorative practices.', 'duration_weeks': 8, 'capacity': 15, 'facilitator': 'NT Department of Territory Families', 'is_active': True},
    {'name': 'Reconnect Education Program', 'program_type': 'education', 'description': 'Supports young people who have disengaged from school to re-enrol and complete secondary education. Includes tutoring, mentoring, and vocational pathways.', 'duration_weeks': 26, 'capacity': 20, 'facilitator': 'Northern Territory Department of Education', 'is_active': True},
    {'name': 'Cognitive Behaviour Therapy Program', 'program_type': 'counselling', 'description': 'Individual and group CBT sessions targeting anger management, impulse control, and decision-making skills. Delivered by qualified psychologists.', 'duration_weeks': 12, 'capacity': 10, 'facilitator': 'Darwin Community Mental Health Services', 'is_active': True},
    {'name': 'Community Service Order Program', 'program_type': 'community_service', 'description': 'Structured community service placements to fulfil court-ordered obligations. Young people contribute to local organisations and develop work-readiness skills.', 'duration_weeks': 16, 'capacity': 25, 'facilitator': 'NT Correctional Services', 'is_active': True},
    {'name': 'Drug and Alcohol Rehabilitation', 'program_type': 'rehabilitation', 'description': 'Residential and outpatient rehabilitation for young people with substance use issues. Includes detox support, counselling, and relapse prevention planning.', 'duration_weeks': 20, 'capacity': 12, 'facilitator': 'Danila Dilba Health Service', 'is_active': True},
    {'name': 'On Country Cultural Program', 'program_type': 'rehabilitation', 'description': 'Land-based healing program connecting Indigenous young people with Country, culture, and Elders. Incorporates traditional practices alongside modern rehabilitation principles.', 'duration_weeks': 10, 'capacity': 8, 'facilitator': 'Aboriginal Areas Protection Authority', 'is_active': True},
]

created = 0
for p in programs:
    _, was_created = Program.objects.get_or_create(name=p['name'], defaults=p)
    if was_created:
        created += 1

print(f'Done. {created} programs created, {len(programs) - created} already existed.')

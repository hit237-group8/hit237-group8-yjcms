import os

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User

from cases.models import Caseworker


caseworkers = [
    {
        'username': 'maya.thompson',
        'first_name': 'Maya',
        'last_name': 'Thompson',
        'email': 'maya.thompson@example.gov.au',
        'staff_id': 'CW-NT-101',
        'phone': '08 8999 1101',
        'department': 'Youth Diversion',
    },
    {
        'username': 'liam.walker',
        'first_name': 'Liam',
        'last_name': 'Walker',
        'email': 'liam.walker@example.gov.au',
        'staff_id': 'CW-NT-102',
        'phone': '08 8999 1102',
        'department': 'Court Support',
    },
    {
        'username': 'aaliyah.ali',
        'first_name': 'Aaliyah',
        'last_name': 'Ali',
        'email': 'aaliyah.ali@example.gov.au',
        'staff_id': 'CW-NT-103',
        'phone': '08 8999 1103',
        'department': 'Family Services',
    },
    {
        'username': 'ethan.nguyen',
        'first_name': 'Ethan',
        'last_name': 'Nguyen',
        'email': 'ethan.nguyen@example.gov.au',
        'staff_id': 'CW-NT-104',
        'phone': '08 8999 1104',
        'department': 'Community Programs',
    },
    {
        'username': 'charlotte.namara',
        'first_name': 'Charlotte',
        'last_name': 'Namara',
        'email': 'charlotte.namara@example.gov.au',
        'staff_id': 'CW-NT-105',
        'phone': '08 8999 1105',
        'department': 'Intake and Assessment',
    },
]

created = 0
updated = 0

for record in caseworkers:
    user, _ = User.objects.update_or_create(
        username=record['username'],
        defaults={
            'first_name': record['first_name'],
            'last_name': record['last_name'],
            'email': record['email'],
            'is_staff': True,
        },
    )
    worker, was_created = Caseworker.objects.update_or_create(
        staff_id=record['staff_id'],
        defaults={
            'user': user,
            'phone': record['phone'],
            'department': record['department'],
        },
    )
    created += int(was_created)
    updated += int(not was_created)

print(f'Done. {created} caseworkers created, {updated} updated.')

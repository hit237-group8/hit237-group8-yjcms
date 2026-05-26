import os
from datetime import date

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from cases.models import Caseworker, YoungPerson


def worker(staff_id):
    return Caseworker.objects.filter(staff_id=staff_id).first()


young_people = [
    {
        'first_name': 'Jayden',
        'last_name': 'Marrakai',
        'date_of_birth': date(2010, 8, 14),
        'gender': 'M',
        'street_address': '12 Daly Street',
        'suburb': 'Darwin',
        'state': 'NT',
        'postcode': '0800',
        'phone': '0400 111 201',
        'email': 'jayden.marrakai@example.com',
        'guardian_name': 'Tara Marrakai',
        'guardian_phone': '0400 111 202',
        'guardian_email': 'tara.marrakai@example.com',
        'indigenous_status': True,
        'interpreter_required': False,
        'education_status': 'enrolled',
        'assigned_caseworker': worker('CW-NT-101'),
    },
    {
        'first_name': 'Sienna',
        'last_name': 'Clarke',
        'date_of_birth': date(2009, 3, 2),
        'gender': 'F',
        'street_address': '8 Casuarina Drive',
        'suburb': 'Casuarina',
        'state': 'NT',
        'postcode': '0810',
        'phone': '0400 111 203',
        'email': 'sienna.clarke@example.com',
        'guardian_name': 'Helen Clarke',
        'guardian_phone': '0400 111 204',
        'guardian_email': 'helen.clarke@example.com',
        'indigenous_status': False,
        'interpreter_required': False,
        'education_status': 'not_enrolled',
        'assigned_caseworker': worker('CW-NT-105'),
    },
    {
        'first_name': 'Noah',
        'last_name': 'Wilson',
        'date_of_birth': date(2008, 11, 27),
        'gender': 'M',
        'street_address': '31 Smith Street',
        'suburb': 'Palmerston',
        'state': 'NT',
        'postcode': '0830',
        'phone': '0400 111 205',
        'email': 'noah.wilson@example.com',
        'guardian_name': 'Mark Wilson',
        'guardian_phone': '0400 111 206',
        'guardian_email': 'mark.wilson@example.com',
        'indigenous_status': False,
        'interpreter_required': False,
        'education_status': 'enrolled',
        'assigned_caseworker': worker('CW-NT-102'),
    },
    {
        'first_name': 'Amelia',
        'last_name': 'Garcia',
        'date_of_birth': date(2011, 5, 19),
        'gender': 'F',
        'street_address': '4 Nightcliff Road',
        'suburb': 'Nightcliff',
        'state': 'NT',
        'postcode': '0810',
        'phone': '0400 111 207',
        'email': 'amelia.garcia@example.com',
        'guardian_name': 'Rosa Garcia',
        'guardian_phone': '0400 111 208',
        'guardian_email': 'rosa.garcia@example.com',
        'indigenous_status': False,
        'interpreter_required': True,
        'education_status': 'enrolled',
        'assigned_caseworker': worker('CW-NT-103'),
    },
    {
        'first_name': 'Kai',
        'last_name': 'Roberts',
        'date_of_birth': date(2007, 9, 5),
        'gender': 'O',
        'street_address': '19 Trower Road',
        'suburb': 'Millner',
        'state': 'NT',
        'postcode': '0810',
        'phone': '0400 111 209',
        'email': 'kai.roberts@example.com',
        'guardian_name': 'Grace Roberts',
        'guardian_phone': '0400 111 210',
        'guardian_email': 'grace.roberts@example.com',
        'indigenous_status': True,
        'interpreter_required': False,
        'education_status': 'completed',
        'assigned_caseworker': worker('CW-NT-104'),
    },
]

created = 0
updated = 0

for record in young_people:
    _, was_created = YoungPerson.objects.update_or_create(
        first_name=record['first_name'],
        last_name=record['last_name'],
        date_of_birth=record['date_of_birth'],
        defaults=record,
    )
    created += int(was_created)
    updated += int(not was_created)

print(f'Done. {created} young people created, {updated} updated.')

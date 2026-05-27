# Entity Relationship Diagram — Version 2
**Updated for Assessment 4**

---

## ERD — Mermaid

```mermaid
erDiagram
    USER { int id PK  string username  string first_name  string last_name }
    CASEWORKER { int id PK  int user_id FK  string staff_id  string department }
    YOUNGPERSON {
        int id PK
        string first_name  string last_name  date date_of_birth  char gender
        string street_address  string suburb  string state  string postcode
        string phone  string email
        string guardian_name  string guardian_phone  string guardian_email
        bool indigenous_status  bool interpreter_required  string education_status
        int assigned_caseworker_id FK  datetime created_at  datetime updated_at
    }
    OFFENCE { int id PK  string name  string severity  bool requires_court }
    CASE {
        int id PK  string case_number
        int young_person_id FK  int caseworker_id FK
        string status  string risk_level  date opened_date  date closed_date
    }
    CASEOFFENCE { int id PK  int case_id FK  int offence_id FK  date date_of_offence  string location }
    COURTHEARING { int id PK  int case_id FK  datetime hearing_date  string court_name  string outcome }
    PROGRAM { int id PK  string name  string program_type  int capacity  bool is_active }
    ENROLMENT { int id PK  int case_id FK  int program_id FK  date enrolment_date  string status  date completion_date }

    USER ||--|| CASEWORKER : "has profile"
    CASEWORKER ||--o{ YOUNGPERSON : "assigned_caseworker"
    CASEWORKER ||--o{ CASE : "manages"
    YOUNGPERSON ||--o{ CASE : "involved_in"
    CASE ||--o{ CASEOFFENCE : "involves"
    OFFENCE ||--o{ CASEOFFENCE : "recorded_via"
    CASE ||--o{ COURTHEARING : "has"
    CASE ||--o{ ENROLMENT : "enrolled_via"
    PROGRAM ||--o{ ENROLMENT : "receives"
```

---

## Assessment 4 changes to YoungPerson

| Old (A2) | New (A4) | Reason |
|---|---|---|
| `address = TextField` | `street_address`, `suburb`, `state`, `postcode` | Structured fields enable filtering and reporting |
| (missing) | `email`, `guardian_email` | Contact channels for staff |
| (missing) | `interpreter_required` | Court hearing logistics |
| (missing) | `education_status` with choices | Key risk factor in youth justice |
| (missing) | `indexes on last_name, first_name` | Search uses `icontains` — index improves performance |

## Service layer data flow

```
HTTP Request
    ↓
View — validates input, calls service, catches domain exceptions
    ↓
Service — enforces domain rules, raises named exceptions
    ↓
Model — data, constraints, business logic methods
    ↓
Database
```

"""Shared employee dict fixtures for DSN unit tests."""

# Standard CDI employee — all fields present
JEAN_DUPONT: dict = {
    "employee_id": "HR-EMP-00003",
    "first_name": "Jean",
    "last_name": "DUPONT",
    "nir": "182017505603712",
    "date_of_birth": "1982-01-15",
    "birth_department": "75",
    "birth_city": "PARIS",
    "birth_country_code": "100",
    "date_of_joining": "2023-01-02",
    "contract_type_code": "01",  # CDI
    "professional_status_code": "229",  # employé
    "gross_pay": 3500.00,
    "net_pay": 3097.50,
    "payment_days": 151.67,
}

# CDD employee
MARIE_LECLERC: dict = {
    "employee_id": "HR-EMP-00004",
    "first_name": "Marie",
    "last_name": "LECLERC",
    "nir": "278056912345678",
    "date_of_birth": "1978-06-20",
    "birth_department": "69",
    "birth_city": "LYON",
    "birth_country_code": "100",
    "date_of_joining": "2026-01-15",
    "contract_type_code": "02",  # CDD
    "professional_status_code": "229",
    "gross_pay": 2800.00,
    "net_pay": 2499.00,
    "payment_days": 120.00,
}

# Edge case: missing NIR and date_of_birth
MISSING_NIR: dict = {
    **JEAN_DUPONT,
    "employee_id": "HR-EMP-00005",
    "nir": "",
    "date_of_birth": "",
}

# Edge case: single-quote in last name — must be escaped per DSN spec
DARTAGNAN: dict = {
    **JEAN_DUPONT,
    "employee_id": "HR-EMP-00006",
    "last_name": "D'ARTAGNAN",
    "first_name": "Alexandre",
}

# Edge case: non-standard amounts (rounding required)
FLOAT_AMOUNTS: dict = {
    **JEAN_DUPONT,
    "employee_id": "HR-EMP-00007",
    "gross_pay": 3500.999,  # must round to 3501.0
    "net_pay": 3097.004,  # must round to 3097.0
}

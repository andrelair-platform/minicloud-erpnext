"""
Create a test employee with a salary structure and January 2026 salary slip.

Run from inside the gunicorn pod:
  cd /home/frappe/frappe-bench/sites
  python /tmp/setup_test_employee.py

Requires erpnext_dsn to be pip-installed and bench-registered:
  bench --site erp.devandre.sbs install-app erpnext_dsn
"""

import frappe
from frappe.utils import now_datetime

frappe.init(site="erp.devandre.sbs")
frappe.connect()

COMPANY = "ktayl solution"  # must match the ERPNext company name

# ---------------------------------------------------------------------------
# 1. Department
# ---------------------------------------------------------------------------
if not frappe.db.exists("Department", {"department_name": "Assurance", "company": COMPANY}):
    dept = frappe.get_doc({
        "doctype": "Department",
        "department_name": "Assurance",
        "company": COMPANY,
        "parent_department": "All Departments",
    })
    dept.insert(ignore_permissions=True)
    print("Created department: Assurance")
else:
    print("Department Assurance already exists")

# ---------------------------------------------------------------------------
# 2. Employee — Jean Dupont (NIR fictif pour qualification Net-Entreprises)
# ---------------------------------------------------------------------------
# NIR fictif: 1 82 01 75 056 037 xx (homme, né janvier 1982, Paris 6e)
# En qualification, Net-Entreprises accepte les NIR fictifs.
EMP_ID = "EMP-DSN-001"

if not frappe.db.exists("Employee", EMP_ID):
    emp = frappe.get_doc({
        "doctype": "Employee",
        "employee": EMP_ID,
        "employee_name": "Jean Dupont",
        "first_name": "Jean",
        "last_name": "Dupont",
        "company": COMPANY,
        "status": "Active",
        "employment_type": "CDI",
        "department": "Assurance",
        "date_of_joining": "2023-01-02",
        "date_of_birth": "1982-01-15",
        "gender": "Male",
        # DSN-specific custom fields (must exist on Employee doctype)
        # Add via ERPNext Customize Form if not present.
        "custom_nir": "182017505603712",       # fictitious NIR (13 digits + 2 key)
        "custom_birth_department": "75",
        "custom_birth_city": "PARIS",
        "custom_birth_country_code": "100",    # 100 = France (DSN code)
        "custom_professional_status_code": "229",  # 229 = employé
    })
    emp.insert(ignore_permissions=True)
    print(f"Created employee: {EMP_ID} — Jean Dupont")
else:
    print(f"Employee {EMP_ID} already exists")

# ---------------------------------------------------------------------------
# 3. Salary Component — Salaire de base
# ---------------------------------------------------------------------------
for component in [
    {"salary_component": "Salaire de base", "salary_component_abbr": "SB",
     "type": "Earning", "is_tax_applicable": 1},
    {"salary_component": "Cotisation retraite", "salary_component_abbr": "RETR",
     "type": "Deduction", "is_tax_applicable": 0},
    {"salary_component": "CSG/CRDS non déductible", "salary_component_abbr": "CSG",
     "type": "Deduction", "is_tax_applicable": 0},
]:
    if not frappe.db.exists("Salary Component", component["salary_component"]):
        sc = frappe.get_doc({"doctype": "Salary Component", **component})
        sc.insert(ignore_permissions=True)
        print(f"Created salary component: {component['salary_component']}")

# ---------------------------------------------------------------------------
# 4. Salary Structure — CDI temps plein assurance
# ---------------------------------------------------------------------------
SS_NAME = "CDI Temps Plein Assurance"

if not frappe.db.exists("Salary Structure", SS_NAME):
    ss = frappe.get_doc({
        "doctype": "Salary Structure",
        "name": SS_NAME,
        "company": COMPANY,
        "currency": "EUR",
        "is_active": "Yes",
        "payroll_frequency": "Monthly",
        "earnings": [
            {"salary_component": "Salaire de base", "abbr": "SB",
             "amount_based_on_formula": 0, "amount": 3500.00},
        ],
        "deductions": [
            {"salary_component": "Cotisation retraite", "abbr": "RETR",
             "amount_based_on_formula": 0, "amount": 350.00},
            {"salary_component": "CSG/CRDS non déductible", "abbr": "CSG",
             "amount_based_on_formula": 0, "amount": 52.50},
        ],
    })
    ss.insert(ignore_permissions=True)
    print(f"Created salary structure: {SS_NAME}")
else:
    print(f"Salary structure {SS_NAME} already exists")

# ---------------------------------------------------------------------------
# 5. Salary Structure Assignment
# ---------------------------------------------------------------------------
if not frappe.db.exists("Salary Structure Assignment", {"employee": EMP_ID, "salary_structure": SS_NAME}):
    ssa = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": EMP_ID,
        "salary_structure": SS_NAME,
        "company": COMPANY,
        "from_date": "2023-01-02",
        "base": 3500.00,
    })
    ssa.insert(ignore_permissions=True)
    ssa.submit()
    print(f"Created salary structure assignment for {EMP_ID}")
else:
    print(f"Salary structure assignment for {EMP_ID} already exists")

# ---------------------------------------------------------------------------
# 6. Salary Slip — January 2026
# ---------------------------------------------------------------------------
SLIP_EXISTS = frappe.db.exists("Salary Slip", {
    "employee": EMP_ID,
    "start_date": "2026-01-01",
    "end_date": "2026-01-31",
    "docstatus": ["!=", 2],
})

if not SLIP_EXISTS:
    slip = frappe.get_doc({
        "doctype": "Salary Slip",
        "employee": EMP_ID,
        "company": COMPANY,
        "salary_structure": SS_NAME,
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "posting_date": "2026-01-31",
        "payment_days": 23,
        "working_days": 23,
    })
    slip.insert(ignore_permissions=True)
    # Calculate earnings/deductions from structure
    slip.get_sal_slip_items()
    slip.save()
    slip.submit()
    print(f"Created and submitted salary slip for {EMP_ID} — January 2026")
    print(f"  Gross: {slip.gross_pay} EUR  |  Net: {slip.net_pay} EUR")
else:
    print(f"Salary slip for {EMP_ID} January 2026 already exists")

frappe.db.commit()
print("\n✅ Test employee setup complete.")
print("Next: bench --site erp.devandre.sbs install-app erpnext_dsn")
print("Then: call /api/method/erpnext_dsn.api.submit_monthly_dsn?year=2026&month=1")

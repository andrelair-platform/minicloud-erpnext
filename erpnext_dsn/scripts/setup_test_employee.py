"""
Create a test employee with a salary structure and January 2026 salary slip.

Run from inside the gunicorn pod:
  kubectl exec -n erp <gunicorn-pod> -- bash -c \
    'cd /home/frappe/frappe-bench/sites && \
     /home/frappe/frappe-bench/env/bin/python /tmp/setup_test_employee.py'

Requires hrms to be bench-installed in the ERPNext site:
  bench --site erp.devandre.sbs install-app hrms

Known ERPNext / hrms gotchas (discovered 2026-08):
  1. HR Settings emp_created_by must be explicitly saved to tabSingles —
     frappe.db.get_single_value returns '' until saved, even though the
     in-memory default is "Naming Series".
  2. Employee autoname is controlled by the Naming Series; "employee" field
     supplied at insert time is ignored.  Capture emp.name AFTER insert.
  3. Employment Type: the autoname field is "employee_type_name", not
     "employment_type".
  4. Department names get company-abbreviation suffix: "Assurance" → "Assurance - KS".
  5. Salary Structure Assignment from_date must fall within an active Fiscal
     Year — use 2026-01-01, not 2023-01-02.
  6. hrms get_holiday_list_for_employee() queries the Holiday List Assignment
     doctype (submitted), NOT the employee.holiday_list field.
  7. The Salary Structure must be submitted (docstatus=1) for check_sal_struct()
     to find it.  Insert alone leaves it at docstatus=0.
  8. get_sal_slip_items() does not exist in hrms.  insert() calls validate()
     which calls get_emp_and_working_day_details() — earnings/deductions are
     populated automatically.
"""

import frappe

frappe.init(site="erp.devandre.sbs")
frappe.connect()

COMPANY = "Ktayl Solutions"  # exact company name in ERPNext
DEPT_NAME = "Assurance - KS"  # ERPNext appends " - KS" (company abbreviation)
SS_NAME = "CDI Temps Plein Assurance"
HL_NAME = "Jours fériés France 2026"

# ---------------------------------------------------------------------------
# 1. HR Settings — ensure emp_created_by is persisted (gotcha #1)
# ---------------------------------------------------------------------------
if not frappe.db.get_single_value("HR Settings", "emp_created_by"):
    hr = frappe.get_single("HR Settings")
    hr.emp_created_by = "Naming Series"
    hr.save(ignore_permissions=True)
    frappe.db.commit()
    print("Set HR Settings: emp_created_by = Naming Series")

# ---------------------------------------------------------------------------
# 2. Department (gotcha #4)
# ---------------------------------------------------------------------------
if not frappe.db.exists("Department", DEPT_NAME):
    frappe.get_doc({
        "doctype": "Department",
        "department_name": "Assurance",
        "company": COMPANY,
        "parent_department": "All Departments",
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"Created department: {DEPT_NAME}")
else:
    print(f"Department {DEPT_NAME} already exists")

# ---------------------------------------------------------------------------
# 3. Employment Types (gotcha #3: field is employee_type_name)
# ---------------------------------------------------------------------------
for et in ["CDI", "CDD", "Alternance", "Stage"]:
    if not frappe.db.exists("Employment Type", et):
        frappe.get_doc({"doctype": "Employment Type", "employee_type_name": et}).insert(ignore_permissions=True)
        print(f"Created employment type: {et}")
frappe.db.commit()

# ---------------------------------------------------------------------------
# 4. Employee — look up by employee_name, capture actual name after insert
#    (gotchas #1 and #2)
# ---------------------------------------------------------------------------
EMP_ID = frappe.db.get_value("Employee", {"employee_name": "Jean Dupont"}, "name")
if not EMP_ID:
    emp = frappe.get_doc({
        "doctype": "Employee",
        "employee_name": "Jean Dupont",
        "first_name": "Jean",
        "last_name": "Dupont",
        "company": COMPANY,
        "status": "Active",
        "employment_type": "CDI",
        "department": DEPT_NAME,
        "date_of_joining": "2023-01-02",
        "date_of_birth": "1982-01-15",
        "gender": "Male",
        # DSN-specific custom fields
        "custom_nir": "182017505603712",       # fictitious NIR (13 digits + 2 key)
        "custom_birth_department": "75",
        "custom_birth_city": "PARIS",
        "custom_birth_country_code": "100",    # 100 = France (DSN code)
        "custom_professional_status_code": "229",  # 229 = employé
    })
    emp.insert(ignore_permissions=True)
    frappe.db.commit()
    EMP_ID = emp.name  # capture name assigned by Naming Series (e.g. HR-EMP-00003)
    print(f"Created employee: {EMP_ID} — Jean Dupont")
else:
    print(f"Employee Jean Dupont already exists: {EMP_ID}")

# ---------------------------------------------------------------------------
# 5. Salary Components
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
        frappe.get_doc({"doctype": "Salary Component", **component}).insert(ignore_permissions=True)
        print(f"Created salary component: {component['salary_component']}")
frappe.db.commit()

# ---------------------------------------------------------------------------
# 6. Salary Structure — insert THEN submit (gotcha #7: check_sal_struct
#    requires ss.docstatus == 1 via its SSA JOIN query)
# ---------------------------------------------------------------------------
ss_docstatus = frappe.db.get_value("Salary Structure", SS_NAME, "docstatus")
if ss_docstatus is None:
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
    ss.submit()
    frappe.db.commit()
    print(f"Created and submitted salary structure: {SS_NAME}")
elif ss_docstatus == 0:
    frappe.get_doc("Salary Structure", SS_NAME).submit()
    frappe.db.commit()
    print(f"Submitted existing salary structure: {SS_NAME}")
else:
    print(f"Salary structure {SS_NAME} already submitted")

# ---------------------------------------------------------------------------
# 7. Salary Structure Assignment — from_date in active FY (gotcha #5)
# ---------------------------------------------------------------------------
if not frappe.db.exists("Salary Structure Assignment",
                         {"employee": EMP_ID, "salary_structure": SS_NAME}):
    ssa = frappe.get_doc({
        "doctype": "Salary Structure Assignment",
        "employee": EMP_ID,
        "salary_structure": SS_NAME,
        "company": COMPANY,
        "from_date": "2026-01-01",  # must be within an active Fiscal Year
        "base": 3500.00,
    })
    ssa.insert(ignore_permissions=True)
    ssa.submit()
    frappe.db.commit()
    print(f"Created salary structure assignment for {EMP_ID}")
else:
    print(f"Salary structure assignment for {EMP_ID} already exists")

# ---------------------------------------------------------------------------
# 8. Holiday List 2026 (gotcha #6: hrms requires Holiday List Assignment,
#    not employee.holiday_list field)
# ---------------------------------------------------------------------------
if not frappe.db.exists("Holiday List", HL_NAME):
    hl = frappe.get_doc({
        "doctype": "Holiday List",
        "holiday_list_name": HL_NAME,
        "from_date": "2026-01-01",
        "to_date": "2026-12-31",
        "holidays": [
            {"description": "Jour de l'An", "holiday_date": "2026-01-01"},
            {"description": "Lundi de Pâques", "holiday_date": "2026-04-06"},
            {"description": "Fête du Travail", "holiday_date": "2026-05-01"},
            {"description": "Victoire 1945", "holiday_date": "2026-05-08"},
            {"description": "Ascension", "holiday_date": "2026-05-14"},
            {"description": "Lundi de Pentecôte", "holiday_date": "2026-05-25"},
            {"description": "Fête Nationale", "holiday_date": "2026-07-14"},
            {"description": "Assomption", "holiday_date": "2026-08-15"},
            {"description": "Toussaint", "holiday_date": "2026-11-01"},
            {"description": "Armistice", "holiday_date": "2026-11-11"},
            {"description": "Noël", "holiday_date": "2026-12-25"},
        ],
    })
    hl.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"Created: {HL_NAME}")
else:
    print(f"Holiday list {HL_NAME} already exists")

# Holiday List Assignment (submitted) for the employee
if not frappe.db.exists("Holiday List Assignment",
                         {"assigned_to": EMP_ID, "docstatus": 1}):
    hla = frappe.get_doc({
        "doctype": "Holiday List Assignment",
        "holiday_list": HL_NAME,
        "assigned_to": EMP_ID,
        "from_date": "2026-01-01",
    })
    hla.insert(ignore_permissions=True)
    hla.submit()
    frappe.db.commit()
    print(f"Created Holiday List Assignment for {EMP_ID}")
else:
    print(f"Holiday List Assignment for {EMP_ID} already exists")

# ---------------------------------------------------------------------------
# 9. Salary Slip — January 2026
#    insert() triggers validate() → get_emp_and_working_day_details()
#    which auto-populates earnings/deductions (gotcha #8: no get_sal_slip_items)
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
    })
    slip.insert(ignore_permissions=True)
    slip.submit()
    frappe.db.commit()
    print(f"Created and submitted salary slip: {slip.name}")
    print(f"  Gross: {slip.gross_pay} EUR  |  Net: {slip.net_pay} EUR")
else:
    existing = frappe.db.get_value("Salary Slip", {
        "employee": EMP_ID, "start_date": "2026-01-01", "docstatus": ["!=", 2]
    }, ["name", "gross_pay", "net_pay"], as_dict=True)
    print(f"Salary slip {existing.name} already exists — "
          f"gross: {existing.gross_pay} EUR, net: {existing.net_pay} EUR")

print(f"\n✅ Test employee setup complete.")
print(f"   Company:  {COMPANY}")
print(f"   Employee: {EMP_ID} (Jean Dupont)")
print(f"\nNext — test the DSN API:")
print(f"  POST /api/method/erpnext_dsn.api.submit_monthly_dsn?year=2026&month=1")

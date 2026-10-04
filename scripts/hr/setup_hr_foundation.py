"""
HR-01 — ERPNext HR foundation config (reproducible, idempotent).

Creates the baseline every HR workflow needs: French Leave Types, a 2026 France Holiday List
(the work calendar), Departments, Designations, and the approval Roles. Idempotent get_or_create —
safe to re-run. This is the runnable source of truth; the same records are also shipped as
`erpnext_hr` fixtures (bench migrate) for a fresh-site self-configure.

Run from inside the gunicorn pod (same pattern as erpnext_dsn/scripts/setup_test_employee.py):
  kubectl exec -n erp <gunicorn-pod> -- bash -c \
    'cd /home/frappe/frappe-bench/sites && \
     /home/frappe/frappe-bench/env/bin/python /tmp/setup_hr_foundation.py'

Requires `hrms` installed (it is — the Leave/Holiday doctypes live there).

Gotchas handled (from the repo's ERPNext notes):
  - Department autoname appends the company abbreviation ("Souscription" → "Souscription - KS"),
    so we get_or_create by the resolved name and never assume the bare name.
  - Single-field defaults (HR Settings) are not relied on here.
  - All writes use ignore_permissions (console/system context).
"""
# pyright: reportMissingImports=false
import frappe

SITE = "erp.devandre.sbs"


def _company():
    return frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all(
        "Company", limit=1, pluck="name"
    )[0]


def ensure(doctype: str, filters: dict, fields: dict) -> str:
    """get_or_create a doc; returns its name. Updates nothing if it already exists."""
    existing = frappe.db.get_value(doctype, filters)
    if existing:
        print(f"  = {doctype}: {existing} (exists)")
        return existing
    doc = frappe.get_doc({"doctype": doctype, **filters, **fields})
    doc.insert(ignore_permissions=True)
    print(f"  + {doctype}: {doc.name} (created)")
    return doc.name


def main():
    company = _company()
    print(f"company = {company}")

    # 1. Leave Types (French) — CP (carry-forward), RTT, Maladie, Sans solde (unpaid).
    print("Leave Types:")
    ensure("Leave Type", {"leave_type_name": "Congé Payé"},
           {"max_leaves_allowed": 25, "is_carry_forward": 1, "include_holiday": 0})
    ensure("Leave Type", {"leave_type_name": "RTT"},
           {"max_leaves_allowed": 10, "is_carry_forward": 0})
    ensure("Leave Type", {"leave_type_name": "Maladie"},
           {"max_leaves_allowed": 0, "is_carry_forward": 0})
    ensure("Leave Type", {"leave_type_name": "Sans solde"},
           {"is_lwp": 1, "is_carry_forward": 0})

    # 2. Holiday List "France 2026" = the work calendar (Sat+Sun off + public holidays).
    print("Holiday List:")
    hl_name = frappe.db.get_value("Holiday List", {"holiday_list_name": "France 2026"})
    if hl_name:
        print(f"  = Holiday List: {hl_name} (exists)")
    else:
        hl = frappe.get_doc({
            "doctype": "Holiday List",
            "holiday_list_name": "France 2026",
            "from_date": "2026-01-01",
            "to_date": "2026-12-31",
            "weekly_off": "Sunday",
        })
        hl.insert(ignore_permissions=True)
        hl.get_weekly_off_dates()  # populate Sundays
        # Saturday off too (35h/Fr standard is Mon-Fri)
        hl.weekly_off = "Saturday"
        hl.get_weekly_off_dates()
        for d, desc in [
            ("2026-01-01", "Jour de l'An"), ("2026-04-06", "Lundi de Pâques"),
            ("2026-05-01", "Fête du Travail"), ("2026-05-08", "Victoire 1945"),
            ("2026-05-14", "Ascension"), ("2026-05-25", "Lundi de Pentecôte"),
            ("2026-07-14", "Fête Nationale"), ("2026-08-15", "Assomption"),
            ("2026-11-01", "Toussaint"), ("2026-11-11", "Armistice 1918"),
            ("2026-12-25", "Noël"),
        ]:
            hl.append("holidays", {"holiday_date": d, "description": desc})
        hl.save(ignore_permissions=True)
        print(f"  + Holiday List: {hl.name} (created, {len(hl.holidays)} days)")
    # make it the company work calendar (weekends + public holidays — fuller than any pre-existing list).
    if frappe.db.get_value("Company", company, "default_holiday_list") != "France 2026":
        frappe.db.set_value("Company", company, "default_holiday_list", "France 2026")
        print(f"  = Company.default_holiday_list → France 2026")

    # 3. Departments (the autoname suffixes " - <abbr>"; get_or_create by department_name).
    print("Departments:")
    for dept in ["Direction", "Souscription", "Sinistres", "Finance",
                 "Ressources Humaines", "Informatique"]:
        if frappe.db.get_value("Department", {"department_name": dept, "company": company}):
            print(f"  = Department: {dept} (exists)")
        else:
            doc = frappe.get_doc({"doctype": "Department", "department_name": dept, "company": company})
            doc.insert(ignore_permissions=True)
            print(f"  + Department: {doc.name} (created)")

    # 4. Designations.
    print("Designations:")
    for desig in ["Directeur", "Souscripteur", "Gestionnaire Sinistres", "Comptable",
                  "Responsable RH", "Ingénieur IT"]:
        ensure("Designation", {"designation_name": desig}, {})

    # 5. Approval Roles. "Leave Approver" + "HR Manager" ship with ERPNext/hrms; "Direction" is ours.
    print("Roles:")
    for role in ["Leave Approver", "HR Manager", "Direction"]:
        ensure("Role", {"role_name": role}, {"desk_access": 1})

    frappe.db.commit()
    print("HR-01 foundation config applied.")


if __name__ == "__main__":
    frappe.init(site=SITE)
    frappe.connect()
    try:
        main()
    finally:
        frappe.destroy()

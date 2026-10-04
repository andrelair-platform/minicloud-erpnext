"""
HR-02b — make leave self-service REAL (reproducible, idempotent). Closes the three gaps that stop a
real employee completing the Congé flow: (1) link each Employee to a login User, (2) route the
leave_approver up the reports_to chain + grant those managers the Leave Approver role, (3) allocate a
2026 balance so there is something to request against. After this: a user logs in → requests Congé
Payé against their balance → their manager Approves in the HR UI (the HR-02 Workflow) → ledger updates.

Run in the gunicorn pod (same pattern as setup_hr_foundation.py):
  kubectl exec -n erp <pod> -- bash -c 'cd /home/frappe/frappe-bench/sites && \
     /home/frappe/frappe-bench/env/bin/python /tmp/setup_leave_self_service.py'

Identity note: matricule 100001 = the owner → linked to the REAL Authentik-SSO user
(kanmegnea@devandre.sbs). The synthetic subordinates (100002–4) get ERPNext login users
(<matricule>@ktayl.local) — enough to exercise ESS + the workflow end-to-end; real SSO for them is
provided later by the JML onboarding (IAM) which creates their Authentik accounts. Idempotent throughout.
"""
# pyright: reportMissingImports=false
import frappe

SITE = "erp.devandre.sbs"
OWNER_MATRICULE = "100001"
OWNER_USER = "kanmegnea@devandre.sbs"
ALLOCATE = [("Congé Payé", 25), ("RTT", 10)]  # Maladie/Sans-solde are requested ad hoc, not allocated
YEAR_FROM, YEAR_TO = "2026-01-01", "2026-12-31"


def ensure_user(email: str, full_name: str) -> str:
    if frappe.db.exists("User", email):
        u = frappe.get_doc("User", email)
    else:
        u = frappe.get_doc({
            "doctype": "User", "email": email, "first_name": full_name,
            "send_welcome_email": 0, "user_type": "System User", "enabled": 1,
        })
        u.insert(ignore_permissions=True)
        print(f"  + User: {email} (created)")
    if not any(r.role == "Employee" for r in u.get("roles", [])):
        u.append("roles", {"role": "Employee"})
        u.save(ignore_permissions=True)
    return email


def grant_role(email: str, role: str):
    u = frappe.get_doc("User", email)
    if not any(r.role == role for r in u.get("roles", [])):
        u.append("roles", {"role": role})
        u.save(ignore_permissions=True)
        print(f"    · granted {role} to {email}")


def main():
    emps = frappe.get_all("Employee", fields=["name", "employee_name", "employee_number", "user_id", "reports_to"])
    by_name = {e.name: e for e in emps}
    with_num = [e for e in emps if e.employee_number]

    # 1. Employee → login User.
    print("Link employees to users:")
    emp_user = {}
    for e in with_num:
        if e.employee_number == OWNER_MATRICULE:
            user = OWNER_USER                      # real Authentik-SSO user
            ensure_user(user, e.employee_name or "Owner")
        else:
            user = f"{e.employee_number}@ktayl.local"
            ensure_user(user, e.employee_name or e.employee_number)
        emp_user[e.name] = user
        if e.user_id != user:
            frappe.db.set_value("Employee", e.name, "user_id", user)
            print(f"  = {e.name} ({e.employee_number}) → user_id {user}")

    # 2. leave_approver = the reports_to manager's user; grant that manager the Leave Approver role.
    print("Route leave approvers (reports_to chain):")
    for e in with_num:
        mgr = by_name.get(e.reports_to)
        if not mgr:
            print(f"  · {e.name} is top of chain — no approver (HR Manager can still act)")
            continue
        mgr_user = emp_user.get(mgr.name)
        if not mgr_user:
            continue
        if frappe.db.get_value("Employee", e.name, "leave_approver") != mgr_user:
            frappe.db.set_value("Employee", e.name, "leave_approver", mgr_user)
            print(f"  = {e.name} leave_approver → {mgr_user}")
        grant_role(mgr_user, "Leave Approver")

    # 2b. Holiday List Assignment (submitted) per employee — hrms resolves an employee's calendar via
    # the Holiday List Assignment doctype, NOT the company default alone (repo ERPNext gotcha #6), so a
    # Leave Application errors "No Holiday List found" without it.
    print("Assign the work calendar (Holiday List Assignment):")
    for e in with_num:
        if frappe.db.exists("Holiday List Assignment",
                            {"assigned_to": e.name, "holiday_list": "France 2026", "docstatus": 1}):
            print(f"  = {e.name} holiday list already assigned")
            continue
        hla = frappe.get_doc({
            "doctype": "Holiday List Assignment", "applicable_for": "Employee",
            "assigned_to": e.name, "holiday_list": "France 2026", "from_date": YEAR_FROM,
        })
        hla.insert(ignore_permissions=True)
        hla.submit()
        print(f"  + {e.name} → France 2026")

    # 3. 2026 Leave Allocations (the balance to request against). Direct Leave Allocation (submitted).
    print("Allocate 2026 balances:")
    for e in with_num:
        for leave_type, qty in ALLOCATE:
            exists = frappe.db.exists("Leave Allocation", {
                "employee": e.name, "leave_type": leave_type, "from_date": YEAR_FROM, "docstatus": 1,
            })
            if exists:
                print(f"  = {e.name} {leave_type} already allocated")
                continue
            la = frappe.get_doc({
                "doctype": "Leave Allocation", "employee": e.name, "leave_type": leave_type,
                "from_date": YEAR_FROM, "to_date": YEAR_TO, "new_leaves_allocated": qty,
            })
            la.insert(ignore_permissions=True)
            la.submit()
            print(f"  + {e.name} {leave_type}: {qty} days")

    frappe.db.commit()
    print("HR-02b applied — leave self-service is live (link + approver + balance).")


if __name__ == "__main__":
    frappe.init(site=SITE)
    frappe.connect()
    try:
        main()
    finally:
        frappe.destroy()

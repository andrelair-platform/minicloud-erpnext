"""
HR-03/HR-04 enablement — grant the approver roles to the managers (reproducible, idempotent).

So the Expense Claim and Timesheet workflows are usable by REAL manager logins (not just
Administrator), this grants:
  - "Expense Approver"   (HR-03 leg 1) + "Timesheet Approver" (HR-04) to every MANAGER — a manager
    being any user that is the `reports_to` target of an active employee.
  - "Accounts User"      (HR-03 leg 2, the finance leg) to the finance/HR owner so the second,
    distinct expense leg has a holder.

Mirrors HR-02b (which routed `leave_approver` + the Leave Approver role up the reports_to chain).
Idempotent: `add_roles` is a no-op for roles a user already has.

Run from inside the gunicorn pod:
  kubectl exec -n erp <gunicorn-pod> -- bash -c \
    'cd /home/frappe/frappe-bench/sites && \
     /home/frappe/frappe-bench/env/bin/python /tmp/setup_approver_roles.py'
"""
# pyright: reportMissingImports=false
import frappe

SITE = "erp.devandre.sbs"
MANAGER_ROLES = ["Expense Approver", "Timesheet Approver"]
FINANCE_ROLE = "Accounts User"


def main():
    emps = frappe.get_all("Employee", filters={"status": "Active"},
                          fields=["name", "user_id", "reports_to"])
    by_name = {e.name: e for e in emps}

    # A manager = anyone an active employee reports to (resolve to the manager's user_id).
    manager_users = set()
    for e in emps:
        if e.reports_to and e.reports_to in by_name:
            mu = by_name[e.reports_to].user_id
            if mu:
                manager_users.add(mu)

    print(f"managers: {sorted(manager_users)}")
    for user in sorted(manager_users):
        u = frappe.get_doc("User", user)
        before = set(frappe.get_roles(user))
        u.add_roles(*MANAGER_ROLES)
        added = [r for r in MANAGER_ROLES if r not in before]
        print(f"  {user}: +{added or 'none (already had)'}")

    # Finance leg holder — the HR/finance owner (top of the chain) already holds Accounts User;
    # ensure at least one user has it so the distinct finance leg is always fillable.
    top = [e.user_id for e in emps if not e.reports_to and e.user_id]
    for user in top:
        u = frappe.get_doc("User", user)
        if FINANCE_ROLE not in set(frappe.get_roles(user)):
            u.add_roles(FINANCE_ROLE)
            print(f"  {user}: +['{FINANCE_ROLE}']")
        else:
            print(f"  {user}: already has {FINANCE_ROLE}")

    frappe.db.commit()
    print("approver roles granted.")


if __name__ == "__main__":
    frappe.init(site=SITE)
    frappe.connect()
    try:
        main()
    finally:
        frappe.destroy()

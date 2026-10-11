"""
HR-03 — Notes de frais: the Expense Claim approval Workflow (reproducible, idempotent).

Creates a Frappe **Workflow** on Expense Claim with TWO DISTINCT approval legs (AC-3):

    Applied ──Approve(Expense Approver=manager)──▶ Manager Approved
            ──Reject───────────────────────────▶ Rejected
    Manager Approved ──Approve(Accounts User=finance)──▶ Approved   (docstatus 1)
                     ──Reject────────────────────────▶ Rejected

The manager leg is a line-manager control (budget/relevance); the finance leg is a separate
accounts control (coding/compliance/payment). They are deliberately held by different roles —
"Expense Approver" (the manager) vs "Accounts User" (finance) — so neither can single-handedly
drive a claim to payment. The native `approval_status` Select (Draft/Approved/Rejected) is driven
via `update_field`, so the final Approved state submits the claim and books the expense.

Also ensures at least one Expense Claim Type exists (the doctype starts empty → a claim can't be
created without one) + its default expense account, so the workflow is demonstrable end-to-end.

Run from inside the gunicorn pod (same pattern as setup_leave_workflow.py):
  kubectl exec -n erp <gunicorn-pod> -- bash -c \
    'cd /home/frappe/frappe-bench/sites && \
     /home/frappe/frappe-bench/env/bin/python /tmp/setup_expense_workflow.py'

Idempotent: skips the Workflow if one for Expense Claim already exists; get_or_create for the
masters. Frappe auto-adds the `workflow_state` Select field when the Workflow is saved.
"""
# pyright: reportMissingImports=false
import frappe

SITE = "erp.devandre.sbs"
DOCTYPE = "Expense Claim"
WORKFLOW = "Expense Claim Approval"
MANAGER_ROLE = "Expense Approver"   # leg 1 — the line manager
FINANCE_ROLE = "Accounts User"      # leg 2 — finance / accounts (distinct from the manager)


def _company():
    return frappe.db.get_single_value("Global Defaults", "default_company") or frappe.get_all(
        "Company", limit=1, pluck="name"
    )[0]


def ensure_master(doctype: str, name_field: str, name: str, extra: dict | None = None):
    if frappe.db.exists(doctype, name):
        print(f"  = {doctype}: {name} (exists)")
        return
    frappe.get_doc({"doctype": doctype, name_field: name, **(extra or {})}).insert(
        ignore_permissions=True
    )
    print(f"  + {doctype}: {name}")


def ensure_expense_claim_type(company: str):
    """Expense Claim can't be filed with zero types — seed a couple of common French ones."""
    print("Expense Claim Types:")
    # a default expense account for the type→company row. French PCG class 6 = charges, so prefer a
    # "6…" leaf; fall back to any Expense-group leaf if the chart has none.
    account = frappe.db.get_value(
        "Account",
        {"company": company, "root_type": "Expense", "is_group": 0, "account_number": ["like", "6%"]},
        "name",
    ) or frappe.db.get_value(
        "Account", {"company": company, "root_type": "Expense", "is_group": 0}, "name"
    )
    for t in ["Frais de déplacement", "Frais de repas", "Hébergement", "Fournitures"]:
        if frappe.db.exists("Expense Claim Type", t):
            print(f"  = Expense Claim Type: {t} (exists)")
            continue
        doc = frappe.get_doc({
            "doctype": "Expense Claim Type",
            "expense_type": t,
            "accounts": [{"company": company, "default_account": account}] if account else [],
        })
        doc.insert(ignore_permissions=True)
        print(f"  + Expense Claim Type: {doc.name}" + (f" (account {account})" if account else ""))


def main():
    company = _company()
    print(f"company = {company}")

    ensure_expense_claim_type(company)

    # Workflow State / Action masters.
    print("Workflow States / Actions:")
    ensure_master("Workflow State", "workflow_state_name", "Applied", {"style": "Warning"})
    ensure_master("Workflow State", "workflow_state_name", "Manager Approved", {"style": "Primary"})
    ensure_master("Workflow State", "workflow_state_name", "Approved", {"style": "Success"})
    ensure_master("Workflow State", "workflow_state_name", "Rejected", {"style": "Danger"})
    ensure_master("Workflow Action Master", "workflow_action_name", "Approve")
    ensure_master("Workflow Action Master", "workflow_action_name", "Reject")

    # The Workflow (idempotent on document_type).
    existing = frappe.db.get_value("Workflow", {"document_type": DOCTYPE})
    if existing:
        print(f"= Workflow for {DOCTYPE} already exists: {existing}")
        return

    wf = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": WORKFLOW,
        "document_type": DOCTYPE,
        "is_active": 1,
        "workflow_state_field": "workflow_state",
        "send_email_alert": 1,
        "states": [
            # state · docstatus · who may edit · native approval_status mapping
            {"state": "Applied", "doc_status": "0", "allow_edit": "Employee",
             "update_field": "approval_status", "update_value": "Draft"},
            {"state": "Manager Approved", "doc_status": "0", "allow_edit": FINANCE_ROLE,
             "update_field": "approval_status", "update_value": "Draft"},
            {"state": "Approved", "doc_status": "1", "allow_edit": FINANCE_ROLE,
             "update_field": "approval_status", "update_value": "Approved"},
            {"state": "Rejected", "doc_status": "1", "allow_edit": MANAGER_ROLE,
             "update_field": "approval_status", "update_value": "Rejected"},
        ],
        "transitions": [
            # leg 1 — the manager (Expense Approver)
            {"state": "Applied", "action": "Approve", "next_state": "Manager Approved",
             "allowed": MANAGER_ROLE},
            {"state": "Applied", "action": "Reject", "next_state": "Rejected",
             "allowed": MANAGER_ROLE},
            # leg 2 — finance (Accounts User), a DISTINCT role from the manager (AC-3)
            {"state": "Manager Approved", "action": "Approve", "next_state": "Approved",
             "allowed": FINANCE_ROLE},
            {"state": "Manager Approved", "action": "Reject", "next_state": "Rejected",
             "allowed": FINANCE_ROLE},
        ],
    })
    wf.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"+ Workflow: {wf.name}")
    print(f"  Applied →[{MANAGER_ROLE}]→ Manager Approved →[{FINANCE_ROLE}]→ Approved")


if __name__ == "__main__":
    frappe.init(site=SITE)
    frappe.connect()
    try:
        main()
    finally:
        frappe.destroy()

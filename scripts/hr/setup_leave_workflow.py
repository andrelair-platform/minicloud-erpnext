"""
HR-02 — Congés / absences: the Leave Application approval Workflow (reproducible, idempotent).

Creates a Frappe **Workflow** on Leave Application: Applied → (manager) Approve → Approved, or
Reject → Rejected. The native balance + overlap check runs in Leave Application.validate()
(automatic — a request over the balance / overlapping is blocked before it can be approved). The
workflow's state→status mapping drives the Leave Application `status`, so an approval submits the
doc and the leave ledger updates. Approval/rejection are gated to the "Leave Approver" role.

Run from inside the gunicorn pod (same pattern as setup_hr_foundation.py):
  kubectl exec -n erp <gunicorn-pod> -- bash -c \
    'cd /home/frappe/frappe-bench/sites && \
     /home/frappe/frappe-bench/env/bin/python /tmp/setup_leave_workflow.py'

Idempotent: skips if a Workflow for Leave Application already exists. Frappe auto-adds the
`workflow_state` Select field to Leave Application when the Workflow is saved.
"""
# pyright: reportMissingImports=false
import frappe

SITE = "erp.devandre.sbs"
DOCTYPE = "Leave Application"
WORKFLOW = "Leave Approval"
APPROVER_ROLE = "Leave Approver"


def ensure_master(doctype: str, name_field: str, name: str, extra: dict | None = None):
    if frappe.db.exists(doctype, name):
        return
    frappe.get_doc({"doctype": doctype, name_field: name, **(extra or {})}).insert(
        ignore_permissions=True
    )
    print(f"  + {doctype}: {name}")


def main():
    # 1. Workflow State masters (name + a UI style).
    print("Workflow States / Actions:")
    ensure_master("Workflow State", "workflow_state_name", "Applied", {"style": "Warning"})
    ensure_master("Workflow State", "workflow_state_name", "Approved", {"style": "Success"})
    ensure_master("Workflow State", "workflow_state_name", "Rejected", {"style": "Danger"})
    ensure_master("Workflow Action Master", "workflow_action_name", "Approve")
    ensure_master("Workflow Action Master", "workflow_action_name", "Reject")

    # 2. The Workflow (idempotent on document_type).
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
        "send_email_alert": 1,  # notify on transitions (approver on apply, requester on decision)
        "states": [
            # state · doc_status · who may edit here · map to the native `status` field
            {"state": "Applied", "doc_status": "0", "allow_edit": "Employee",
             "update_field": "status", "update_value": "Open"},
            {"state": "Approved", "doc_status": "1", "allow_edit": APPROVER_ROLE,
             "update_field": "status", "update_value": "Approved"},
            {"state": "Rejected", "doc_status": "1", "allow_edit": APPROVER_ROLE,
             "update_field": "status", "update_value": "Rejected"},
        ],
        "transitions": [
            # from · action · to · who may do it (the manager / leave approver)
            {"state": "Applied", "action": "Approve", "next_state": "Approved", "allowed": APPROVER_ROLE},
            {"state": "Applied", "action": "Reject", "next_state": "Rejected", "allowed": APPROVER_ROLE},
        ],
    })
    wf.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"+ Workflow: {wf.name} (Applied → Approve/Reject by {APPROVER_ROLE})")


if __name__ == "__main__":
    frappe.init(site=SITE)
    frappe.connect()
    try:
        main()
    finally:
        frappe.destroy()

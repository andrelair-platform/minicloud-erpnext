app_name = "erpnext_hr_lifecycle"
app_title = "ERPNext HR Lifecycle"
app_publisher = "AndreLiar"
app_description = (
    "Joiner/Mover/Leaver lifecycle event emission — the ERPNext (HR) side of the "
    "HR#8 ↔ ktayl-iam#17 seam. Publishes SIGNED events to NATS JetStream HR_LIFECYCLE "
    "(the durable backbone ktayl-iam v3 consumes for access) and triggers the n8n "
    "NON-access fan-out (GLPI software task + email). ERPNext never writes Authentik."
)
app_version = "0.1.0"

# Lifecycle events fire from these doc events. Each handler enqueues a background publish
# (frappe.enqueue) so a slow/failed fan-out can NEVER block or roll back the HR transaction.
doc_events = {
    "Employee": {
        # A new Employee row = the Joiner. (ERPNext already webhooks Employee/after_insert to
        # Backstage; this is the IAM/audit lifecycle event, a separate concern.)
        "after_insert": "erpnext_hr_lifecycle.events.on_employee_insert",
    },
    "Employee Promotion": {
        "on_submit": "erpnext_hr_lifecycle.events.on_promotion",
    },
    "Employee Transfer": {
        "on_submit": "erpnext_hr_lifecycle.events.on_transfer",
    },
    "Employee Separation": {
        # Submitting the separation = the Leaver (its relieve/exit is now effective).
        "on_submit": "erpnext_hr_lifecycle.events.on_separation",
    },
}

# A whitelisted helper so the live seam can be smoke-tested without mutating HR data.
whitelisted_api = {
    "erpnext_hr_lifecycle.events.emit_test_event": True,
}

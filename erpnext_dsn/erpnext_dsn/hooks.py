app_name = "erpnext_dsn"
app_title = "ERPNext DSN"
app_publisher = "AndreLiar"
app_description = "DSN phase 3.1 monthly payroll declaration for French insurance IS"
app_version = "0.1.0"

doc_events = {
    "Salary Slip": {
        # Validates that the employee has all DSN-mandatory fields on submission.
        # Does NOT auto-generate the declaration — DSN is monthly, not per-slip.
        "on_submit": "erpnext_dsn.salary_hook.validate_dsn_fields",
    }
}

# Exposed via /api/method/erpnext_dsn.api.generate_monthly_dsn
# Called manually or by an n8n workflow on the last working day of each month.
whitelisted_api = {
    "erpnext_dsn.api.generate_monthly_dsn": True,
    "erpnext_dsn.api.submit_monthly_dsn": True,
}

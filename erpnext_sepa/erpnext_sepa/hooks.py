app_name = "erpnext_sepa"
app_title = "ERPNext SEPA"
app_publisher = "AndreLiar"
app_description = "SEPA Direct Debit integration — GoCardless mandate + PAIN.008"
app_version = "1.0.0"

# Custom fields exported via bench export-fixtures
fixtures = [
    {
        "doctype": "Custom Field",
        "filters": [["module", "=", "ERPNext SEPA"]],
    }
]

app_name = "erpnext_facturx"
app_title = "ERPNext Factur-X"
app_publisher = "AndreLiar"
app_description = "Factur-X Minimum e-invoicing for French insurance IS"
app_version = "0.1.0"

doc_events = {
    "Sales Invoice": {
        "on_submit": "erpnext_facturx.facturx.generate_and_attach",
    }
}

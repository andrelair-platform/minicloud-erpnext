import frappe


_REQUIRED_EMPLOYEE_FIELDS = [
    ("custom_nir", "NIR (numéro de sécurité sociale)"),
    ("date_of_birth", "Date de naissance"),
    ("gender", "Genre"),
    ("date_of_joining", "Date d'entrée"),
    ("employment_type", "Type de contrat"),
]


def validate_dsn_fields(doc, method=None):
    """Warn (not block) when DSN-mandatory employee fields are missing."""
    employee = frappe.get_doc("Employee", doc.employee)
    missing = [
        label
        for field, label in _REQUIRED_EMPLOYEE_FIELDS
        if not getattr(employee, field, None)
    ]
    if missing:
        frappe.msgprint(
            "DSN : champs manquants sur la fiche employé — la déclaration mensuelle "
            f"sera incomplète : {', '.join(missing)}",
            alert=True,
            indicator="orange",
        )

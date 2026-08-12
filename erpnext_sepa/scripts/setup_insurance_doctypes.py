import frappe

frappe.init(site="erp.devandre.sbs")
frappe.connect()

LOB_OPTIONS = (
    "\nIARD - Automobile\nIARD - MRH\nIARD - RC Professionnelle\n"
    "IARD - Transport\nIARD - Construction\nIARD - Agricole\n"
    "IARD - Risques Industriels\nIARD - Risques Divers\n"
    "Vie\nPrévoyance Individuelle\nPrévoyance Collective\nÉpargne"
)
FREQ_OPTIONS = "\nAnnuel\nSemestriel\nTrimestriel\nMensuel"
POLICY_STATUS = "\nEn attente\nEn cours\nSuspendu\nRésilié\nExpiré"
CLAIM_STATUS = "\nDéclaré\nEn cours d'instruction\nExpertisé\nAccepté\nRefusé\nRéglé\nClôturé"


def make_doctype(name, fields_spec, is_submittable=0, autoname=None):
    if frappe.db.exists("DocType", name):
        print("  skip  " + name)
        return
    doc = frappe.new_doc("DocType")
    doc.name = name
    doc.module = "Custom"
    doc.custom = 1
    doc.is_submittable = is_submittable
    if autoname:
        doc.autoname = autoname

    for f in fields_spec:
        row = doc.append("fields", {})
        for k, v in f.items():
            row.set(k, v)

    p = doc.append("permissions", {})
    p.role = "System Manager"
    p.read = p.write = p.create = p.delete = 1
    if is_submittable:
        p.submit = p.cancel = p.amend = 1

    p2 = doc.append("permissions", {})
    p2.role = "Accounts User"
    p2.read = p2.write = p2.create = 1
    if is_submittable:
        p2.submit = 1

    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print("  ✓     " + name)


# ─────────────────────────────────────────────────────────────
# 1. Insurance Product (reference data, not submittable)
# ─────────────────────────────────────────────────────────────
print("\n=== 1. Insurance Product ===")
make_doctype(
    "Insurance Product",
    is_submittable=0,
    autoname="field:product_code",
    fields_spec=[
        {
            "fieldname": "product_code",
            "label": "Code produit",
            "fieldtype": "Data",
            "reqd": 1,
            "in_list_view": 1,
            "bold": 1,
            "unique": 1,
        },
        {
            "fieldname": "product_name",
            "label": "Nom du produit",
            "fieldtype": "Data",
            "reqd": 1,
            "in_list_view": 1,
        },
        {"fieldname": "cb_id1", "fieldtype": "Column Break"},
        {
            "fieldname": "risk_type",
            "label": "Ligne de produit (LOB)",
            "fieldtype": "Select",
            "options": LOB_OPTIONS,
            "reqd": 1,
            "in_list_view": 1,
        },
        {"fieldname": "is_active", "label": "Actif", "fieldtype": "Check", "default": "1"},
        {"fieldname": "pricing_section", "label": "Tarification", "fieldtype": "Section Break"},
        {"fieldname": "base_premium", "label": "Prime de base (€/an)", "fieldtype": "Currency"},
        {
            "fieldname": "tsca_rate",
            "label": "Taux TSCA (%)",
            "fieldtype": "Float",
            "description": "9 / 13 / 33 selon la garantie (art. 991 CGI)",
        },
        {"fieldname": "cb_pricing1", "fieldtype": "Column Break"},
        {"fieldname": "company", "label": "Société", "fieldtype": "Link", "options": "Company"},
        {
            "fieldname": "item",
            "label": "Article ERPNext (facturation)",
            "fieldtype": "Link",
            "options": "Item",
        },
        {"fieldname": "desc_section", "label": "Présentation", "fieldtype": "Section Break"},
        {
            "fieldname": "description",
            "label": "Description commerciale",
            "fieldtype": "Text Editor",
        },
        {
            "fieldname": "cov_section",
            "label": "Garanties & Exclusions",
            "fieldtype": "Section Break",
        },
        {
            "fieldname": "coverage_details",
            "label": "Garanties couvertes",
            "fieldtype": "Text Editor",
        },
        {"fieldname": "exclusions", "label": "Exclusions de garantie", "fieldtype": "Text Editor"},
    ],
)

# ─────────────────────────────────────────────────────────────
# 2. Insurance Policy (submittable)
# ─────────────────────────────────────────────────────────────
print("\n=== 2. Insurance Policy ===")
make_doctype(
    "Insurance Policy",
    is_submittable=1,
    autoname="naming_series:",
    fields_spec=[
        # naming_series must be Select in Frappe v16
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "INS-POL-.YYYY.-.####\n",
            "reqd": 1,
        },
        {
            "fieldname": "customer",
            "label": "Assuré (client)",
            "fieldtype": "Link",
            "options": "Customer",
            "reqd": 1,
            "in_list_view": 1,
            "bold": 1,
        },
        {
            "fieldname": "insurance_product",
            "label": "Produit d'assurance",
            "fieldtype": "Link",
            "options": "Insurance Product",
            "reqd": 1,
            "in_list_view": 1,
        },
        {"fieldname": "cb_main1", "fieldtype": "Column Break"},
        {
            "fieldname": "status",
            "label": "Statut",
            "fieldtype": "Select",
            "options": POLICY_STATUS,
            "default": "En attente",
            "in_list_view": 1,
            "bold": 1,
        },
        {
            "fieldname": "company",
            "label": "Société",
            "fieldtype": "Link",
            "options": "Company",
            "reqd": 1,
        },
        {"fieldname": "dates_section", "label": "Couverture", "fieldtype": "Section Break"},
        {
            "fieldname": "effective_date",
            "label": "Date d'effet",
            "fieldtype": "Date",
            "reqd": 1,
            "in_list_view": 1,
        },
        {"fieldname": "expiry_date", "label": "Date d'expiration", "fieldtype": "Date", "reqd": 1},
        {"fieldname": "cb_dates1", "fieldtype": "Column Break"},
        {"fieldname": "renewal_date", "label": "Prochaine échéance", "fieldtype": "Date"},
        {
            "fieldname": "payment_frequency",
            "label": "Fréquence de paiement",
            "fieldtype": "Select",
            "options": FREQ_OPTIONS,
            "default": "Annuel",
        },
        {"fieldname": "lob_section", "label": "Risque assuré", "fieldtype": "Section Break"},
        {
            "fieldname": "risk_type",
            "label": "Ligne de produit (LOB)",
            "fieldtype": "Select",
            "options": LOB_OPTIONS,
        },
        {
            "fieldname": "insured_name",
            "label": "Nom de l'assuré (si ≠ client)",
            "fieldtype": "Data",
        },
        {"fieldname": "cb_lob1", "fieldtype": "Column Break"},
        {
            "fieldname": "premium_amount",
            "label": "Montant de la prime (€)",
            "fieldtype": "Currency",
        },
        {
            "fieldname": "currency",
            "label": "Devise",
            "fieldtype": "Link",
            "options": "Currency",
            "default": "EUR",
        },
        {
            "fieldname": "links_section",
            "label": "Liens CRM & Facturation",
            "fieldtype": "Section Break",
        },
        {
            "fieldname": "opportunity",
            "label": "Opportunité CRM",
            "fieldtype": "Link",
            "options": "Opportunity",
        },
        {
            "fieldname": "sales_invoice",
            "label": "Facture de prime",
            "fieldtype": "Link",
            "options": "Sales Invoice",
        },
        {"fieldname": "cb_links1", "fieldtype": "Column Break"},
        {
            "fieldname": "sepa_mandate_ref",
            "label": "Référence mandat SEPA",
            "fieldtype": "Data",
            "read_only": 1,
            "description": "Copié depuis Customer.sepa_mandate_id à la souscription",
        },
        {"fieldname": "notes_section", "label": "Notes", "fieldtype": "Section Break"},
        {"fieldname": "notes", "label": "Notes", "fieldtype": "Text"},
    ],
)

# ─────────────────────────────────────────────────────────────
# 3. Insurance Claim (submittable)
# ─────────────────────────────────────────────────────────────
print("\n=== 3. Insurance Claim ===")
make_doctype(
    "Insurance Claim",
    is_submittable=1,
    autoname="naming_series:",
    fields_spec=[
        {
            "fieldname": "naming_series",
            "label": "Série",
            "fieldtype": "Select",
            "options": "INS-CLM-.YYYY.-.####\n",
            "reqd": 1,
        },
        {
            "fieldname": "policy",
            "label": "Contrat d'assurance",
            "fieldtype": "Link",
            "options": "Insurance Policy",
            "reqd": 1,
            "in_list_view": 1,
            "bold": 1,
        },
        {
            "fieldname": "customer",
            "label": "Déclarant",
            "fieldtype": "Link",
            "options": "Customer",
            "in_list_view": 1,
            "fetch_from": "policy.customer",
            "fetch_if_empty": 1,
        },
        {"fieldname": "cb_main1", "fieldtype": "Column Break"},
        {
            "fieldname": "status",
            "label": "Statut",
            "fieldtype": "Select",
            "options": CLAIM_STATUS,
            "default": "Déclaré",
            "in_list_view": 1,
            "bold": 1,
        },
        {
            "fieldname": "company",
            "label": "Société",
            "fieldtype": "Link",
            "options": "Company",
            "fetch_from": "policy.company",
            "fetch_if_empty": 1,
        },
        {"fieldname": "incident_section", "label": "Sinistre", "fieldtype": "Section Break"},
        {
            "fieldname": "incident_date",
            "label": "Date du sinistre",
            "fieldtype": "Date",
            "reqd": 1,
            "in_list_view": 1,
        },
        {
            "fieldname": "declaration_date",
            "label": "Date de déclaration",
            "fieldtype": "Date",
            "default": "Today",
        },
        {"fieldname": "cb_incident1", "fieldtype": "Column Break"},
        {
            "fieldname": "risk_type",
            "label": "Ligne de produit (LOB)",
            "fieldtype": "Select",
            "options": LOB_OPTIONS,
            "fetch_from": "policy.risk_type",
            "fetch_if_empty": 1,
        },
        {"fieldname": "adjuster_name", "label": "Expert mandaté", "fieldtype": "Data"},
        {"fieldname": "amounts_section", "label": "Montants", "fieldtype": "Section Break"},
        {"fieldname": "claim_amount", "label": "Montant déclaré (€)", "fieldtype": "Currency"},
        {
            "fieldname": "currency",
            "label": "Devise",
            "fieldtype": "Link",
            "options": "Currency",
            "default": "EUR",
        },
        {"fieldname": "cb_amounts1", "fieldtype": "Column Break"},
        {"fieldname": "settlement_amount", "label": "Montant réglé (€)", "fieldtype": "Currency"},
        {"fieldname": "desc_section", "label": "Description", "fieldtype": "Section Break"},
        {
            "fieldname": "description",
            "label": "Description du sinistre",
            "fieldtype": "Text Editor",
            "reqd": 1,
        },
        {"fieldname": "notes_section", "label": "Notes internes", "fieldtype": "Section Break"},
        {"fieldname": "notes", "label": "Notes", "fieldtype": "Text"},
    ],
)

# ─────────────────────────────────────────────────────────────
# 4. Custom fields on Opportunity
# ─────────────────────────────────────────────────────────────
print("\n=== 4. Opportunity Custom Fields ===")
opp_fields = [
    {
        "dt": "Opportunity",
        "fieldname": "insurance_section",
        "label": "Assurance",
        "fieldtype": "Section Break",
        "insert_after": "risk_type",
        "collapsible": 1,
    },
    {
        "dt": "Opportunity",
        "fieldname": "quoted_product",
        "label": "Produit proposé",
        "fieldtype": "Link",
        "options": "Insurance Product",
        "insert_after": "insurance_section",
        "description": "Produit d'assurance présenté lors de cette opportunité",
    },
    {
        "dt": "Opportunity",
        "fieldname": "cb_ins1",
        "fieldtype": "Column Break",
        "insert_after": "quoted_product",
    },
    {
        "dt": "Opportunity",
        "fieldname": "linked_policy",
        "label": "Contrat souscrit",
        "fieldtype": "Link",
        "options": "Insurance Policy",
        "insert_after": "cb_ins1",
        "read_only": 1,
        "description": "Contrat créé à l'issue de cette opportunité",
    },
]
for cf in opp_fields:
    name = cf["dt"] + "-" + cf["fieldname"]
    if frappe.db.exists("Custom Field", name):
        print("  skip  " + name)
        continue
    doc = frappe.new_doc("Custom Field")
    doc.update(cf)
    doc.name = name
    doc.insert(ignore_permissions=True)
    print("  ✓     " + name)
frappe.db.commit()

# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
print("\n=== Summary ===")
for dt in ["Insurance Product", "Insurance Policy", "Insurance Claim"]:
    print("  " + ("✓" if frappe.db.exists("DocType", dt) else "✗") + "  " + dt)
cf_names = [
    "Opportunity-quoted_product",
    "Opportunity-linked_policy",
    "Opportunity-insurance_section",
    "Opportunity-cb_ins1",
]
cf_count = len(frappe.db.get_all("Custom Field", filters={"name": ["in", cf_names]}))
print("  Opportunity custom fields: " + str(cf_count) + "/4")

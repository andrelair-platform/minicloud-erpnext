import frappe

frappe.init(site="erp.devandre.sbs")
frappe.connect()

COMPANY = "Ktayl Solutions"

products = [
    {
        "product_code": "IARD-AUTO-RC",
        "product_name": "RC Automobile — Assurance responsabilité civile auto",
        "risk_type": "IARD - Automobile",
        "base_premium": 350.0,
        "tsca_rate": 13.0,
        "is_active": 1,
        "company": COMPANY,
        "description": "Garantie responsabilité civile obligatoire pour tout véhicule terrestre à moteur.",
        "coverage_details": "Dommages corporels et matériels causés à des tiers. Défense pénale et recours.",
        "exclusions": "Dommages au véhicule assuré. Conduite en état d'ivresse. Usage commercial non déclaré.",
    },
    {
        "product_code": "IARD-HAB-MRH",
        "product_name": "MRH — Multirisques Habitation",
        "risk_type": "IARD - MRH",
        "base_premium": 180.0,
        "tsca_rate": 9.0,
        "is_active": 1,
        "company": COMPANY,
        "description": "Assurance multirisques habitation couvrant le logement et les biens mobiliers.",
        "coverage_details": "Incendie, dégâts des eaux, vol, bris de glace, catastrophes naturelles. Responsabilité civile vie privée.",
        "exclusions": "Logements vacants depuis plus de 90 jours. Sinistres intentionnels.",
    },
    {
        "product_code": "PREV-IND-01",
        "product_name": "Prévoyance Individuelle — Arrêt de travail & Décès",
        "risk_type": "Prévoyance Individuelle",
        "base_premium": 420.0,
        "tsca_rate": 9.0,
        "is_active": 1,
        "company": COMPANY,
        "description": "Contrat de prévoyance individuelle couvrant l'incapacité de travail et le décès.",
        "coverage_details": "Indemnités journalières en cas d'arrêt de travail. Capital décès. Invalidité permanente.",
        "exclusions": "Maladies préexistantes non déclarées. Sports extrêmes (option possible). Guerre.",
    },
]

print("=== Seeding Insurance Products ===")
for p in products:
    code = p["product_code"]
    if frappe.db.exists("Insurance Product", code):
        print("  skip  " + code)
        continue
    doc = frappe.new_doc("Insurance Product")
    doc.update(p)
    doc.insert(ignore_permissions=True)
    print("  ✓     " + code)

frappe.db.commit()
print("\nDone — " + str(len(frappe.db.get_all("Insurance Product"))) + " products total.")

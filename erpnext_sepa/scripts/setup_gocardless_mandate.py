"""
setup_gocardless_mandate.py
===========================
Run inside the ERPNext gunicorn pod to:
  1. Create a GoCardless sandbox Customer + BankAccount + Mandate
  2. Add custom fields (gc_customer_id, gc_mandate_id) to ERPNext Customer
  3. Add custom fields (gc_payment_id, gc_payment_status) to ERPNext Sales Invoice
  4. Store GoCardless IDs on the existing test customer (Cabinet Dupont)

Usage:
    kubectl exec -n erp <gunicorn-pod> -- bash -c \
      "GC_API_KEY=<sandbox-token> \
       cd /home/frappe/frappe-bench/sites && \
       /home/frappe/frappe-bench/env/bin/python /tmp/setup_gocardless_mandate.py"

Prerequisites:
  - GC_API_KEY env var set to GoCardless sandbox access token
  - ERPNext site has customer "Cabinet Dupont" (from ERP-1 test invoice setup)
"""

import os
import sys

import frappe
import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SITE = "erp.devandre.sbs"
GC_BASE = "https://api-sandbox.gocardless.com"
GC_VERSION = "2015-07-06"
GC_API_KEY = os.environ.get("GC_API_KEY", "")

# Test data — matches the ERP-1 test invoice Cabinet Dupont
CUSTOMER_FRAPPE_NAME = "Cabinet Dupont"
GC_CUSTOMER = {
    "customers": {
        "email": "cabinet.dupont@example.fr",
        "given_name": "Cabinet",
        "family_name": "Dupont",
        "company_name": "Cabinet Dupont Assurances",
        "country_code": "FR",
        "language": "fr-FR",
        "metadata": {"erpnext_customer": CUSTOMER_FRAPPE_NAME},
    }
}
GC_BANK_ACCOUNT = {
    "account_holder_name": "Cabinet Dupont Assurances",
    "iban": "FR7630006000011234567890189",  # GoCardless sandbox test IBAN
}
GC_MANDATE_SCHEME = "sepa_core"


def _gc_headers() -> dict:
    return {
        "Authorization": f"Bearer {GC_API_KEY}",
        "GoCardless-Version": GC_VERSION,
        "Content-Type": "application/json",
    }


def _gc_post(path: str, body: dict) -> dict:
    r = requests.post(f"{GC_BASE}{path}", headers=_gc_headers(), json=body, timeout=30)
    if r.status_code not in (200, 201):
        print(f"  ERROR {r.status_code}: {r.text}")
        sys.exit(1)
    return r.json()


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------

CUSTOM_FIELDS = [
    # Customer fields
    {
        "dt": "Customer",
        "fieldname": "gc_customer_id",
        "label": "GoCardless Customer ID",
        "fieldtype": "Data",
        "insert_after": "customer_name",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
    {
        "dt": "Customer",
        "fieldname": "gc_mandate_id",
        "label": "GoCardless Mandate ID",
        "fieldtype": "Data",
        "insert_after": "gc_customer_id",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
    # Sales Invoice fields
    {
        "dt": "Sales Invoice",
        "fieldname": "gc_payment_id",
        "label": "GoCardless Payment ID",
        "fieldtype": "Data",
        "insert_after": "remarks",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
    {
        "dt": "Sales Invoice",
        "fieldname": "gc_payment_status",
        "label": "GoCardless Payment Status",
        "fieldtype": "Select",
        "options": "\npending_submission\npending_customer_approval\nsubmitted\nconfirmed\npaid_out\nfailed\ncancelled\ncustomer_approval_denied\ncleaned_up",
        "insert_after": "gc_payment_id",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
]


def setup_custom_fields():
    print("Setting up custom fields...")
    for cf in CUSTOM_FIELDS:
        name = f"{cf['dt']}-{cf['fieldname']}"
        if frappe.db.exists("Custom Field", name):
            print(f"  Custom field {name} already exists — skipping")
            continue
        doc = frappe.new_doc("Custom Field")
        doc.update(cf)
        doc.name = name
        doc.insert(ignore_permissions=True)
        print(f"  Created custom field: {name}")
    frappe.db.commit()


# ---------------------------------------------------------------------------
# GoCardless setup
# ---------------------------------------------------------------------------


def create_gc_customer() -> str:
    print("Creating GoCardless customer...")
    resp = _gc_post("/customers", GC_CUSTOMER)
    gc_id = resp["customers"]["id"]
    print(f"  GoCardless customer: {gc_id}")
    return gc_id


def create_gc_bank_account(gc_customer_id: str) -> str:
    print("Creating GoCardless bank account...")
    body = {
        "customer_bank_accounts": {
            **GC_BANK_ACCOUNT,
            "links": {"customer": gc_customer_id},
        }
    }
    resp = _gc_post("/customer_bank_accounts", body)
    ba_id = resp["customer_bank_accounts"]["id"]
    print(f"  GoCardless bank account: {ba_id}")
    return ba_id


def create_gc_mandate(bank_account_id: str) -> str:
    print("Creating GoCardless SEPA mandate...")
    body = {
        "mandates": {
            "scheme": GC_MANDATE_SCHEME,
            "links": {"customer_bank_account": bank_account_id},
        }
    }
    resp = _gc_post("/mandates", body)
    mandate_id = resp["mandates"]["id"]
    print(f"  GoCardless mandate: {mandate_id}")
    return mandate_id


def store_gc_ids_on_customer(gc_customer_id: str, mandate_id: str):
    print(f"Storing GoCardless IDs on ERPNext customer '{CUSTOMER_FRAPPE_NAME}'...")
    frappe.db.set_value(
        "Customer",
        CUSTOMER_FRAPPE_NAME,
        {
            "gc_customer_id": gc_customer_id,
            "gc_mandate_id": mandate_id,
        },
    )
    frappe.db.commit()
    print("  Done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not GC_API_KEY:
        print("ERROR: GC_API_KEY env var not set")
        sys.exit(1)

    frappe.init(site=SITE)
    frappe.connect()

    setup_custom_fields()

    if not frappe.db.exists("Customer", CUSTOMER_FRAPPE_NAME):
        print(f"ERROR: Customer '{CUSTOMER_FRAPPE_NAME}' not found in ERPNext")
        sys.exit(1)

    gc_customer_id = create_gc_customer()
    bank_account_id = create_gc_bank_account(gc_customer_id)
    mandate_id = create_gc_mandate(bank_account_id)
    store_gc_ids_on_customer(gc_customer_id, mandate_id)

    print()
    print("✅ GoCardless sandbox mandate setup complete.")
    print(f"   GC Customer:  {gc_customer_id}")
    print(f"   GC Mandate:   {mandate_id}")
    print()
    print("Next steps:")
    print("  1. Add GoCardless webhook in sandbox dashboard:")
    print("     URL: https://erp.devandre.sbs/api/method/erpnext_sepa.api.gocardless_webhook")
    print("     Events: payments.paid_out, payments.failed, mandates.active")
    print("  2. Store webhook secret in Vault:")
    print("     vault kv patch secret/platform/gocardless webhook_secret=<secret>")
    print("  3. Import n8n workflow: workflows/sepa_invoice_to_payment.json")

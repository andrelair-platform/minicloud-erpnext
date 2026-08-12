"""
setup_stripe_customer.py
========================
Run once inside the ERPNext gunicorn pod to:
  1. Add custom fields to ERPNext (Customer + Sales Invoice)
  2. Create a Stripe Customer for "Cabinet Dupont"
  3. Attach a SEPA Direct Debit payment method (test IBAN)
  4. Confirm a SetupIntent → mandate collected
  5. Store Stripe IDs back on the ERPNext Customer

Usage:
    kubectl exec -n erp <gunicorn-pod> -- bash -c \
      "STRIPE_SECRET_KEY=sk_test_... \
       cd /home/frappe/frappe-bench/sites && \
       /home/frappe/frappe-bench/env/bin/python /tmp/setup_stripe_customer.py"

Stripe test IBANs:
    AT611904300234573201  →  payment always succeeds
    AT861904300235473202  →  payment always fails
"""

import os
import sys

import frappe
import stripe

SITE = "erp.devandre.sbs"
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
CUSTOMER_FRAPPE_NAME = "Cabinet Dupont"

# Stripe test IBAN that always succeeds (Austria test number)
TEST_IBAN = "AT611904300234573201"


# ---------------------------------------------------------------------------
# Custom fields
# ---------------------------------------------------------------------------

CUSTOM_FIELDS = [
    {
        "dt": "Customer",
        "fieldname": "stripe_customer_id",
        "label": "Stripe Customer ID",
        "fieldtype": "Data",
        "insert_after": "customer_name",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
    {
        "dt": "Customer",
        "fieldname": "stripe_payment_method_id",
        "label": "Stripe Payment Method ID",
        "fieldtype": "Data",
        "insert_after": "stripe_customer_id",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
    {
        "dt": "Sales Invoice",
        "fieldname": "stripe_payment_intent_id",
        "label": "Stripe Payment Intent ID",
        "fieldtype": "Data",
        "insert_after": "remarks",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
    {
        "dt": "Sales Invoice",
        "fieldname": "stripe_payment_status",
        "label": "Stripe Payment Status",
        "fieldtype": "Select",
        "options": (
            "\nrequires_payment_method\nrequires_confirmation\n"
            "requires_action\nprocessing\nrequires_capture\n"
            "canceled\nsucceeded\nfailed"
        ),
        "insert_after": "stripe_payment_intent_id",
        "read_only": 1,
        "module": "ERPNext SEPA",
    },
]


def setup_custom_fields() -> None:
    print("Setting up ERPNext custom fields...")
    for cf in CUSTOM_FIELDS:
        name = f"{cf['dt']}-{cf['fieldname']}"
        if frappe.db.exists("Custom Field", name):
            print(f"  {name} already exists — skipping")
            continue
        doc = frappe.new_doc("Custom Field")
        doc.update(cf)
        doc.name = name
        doc.insert(ignore_permissions=True)
        print(f"  Created: {name}")
    frappe.db.commit()


# ---------------------------------------------------------------------------
# Stripe setup
# ---------------------------------------------------------------------------

def create_stripe_customer(frappe_customer_name: str) -> str:
    print("Creating Stripe customer...")
    customer = stripe.Customer.create(
        name=frappe_customer_name,
        email="cabinet.dupont@example.fr",
        metadata={"erpnext_customer": frappe_customer_name},
    )
    print(f"  Stripe customer: {customer.id}")
    return customer.id


def attach_sepa_payment_method(stripe_customer_id: str) -> str:
    """
    Creates a SEPA Direct Debit payment method with the test IBAN
    and attaches it to the Stripe customer.
    """
    print("Creating SEPA payment method (test IBAN)...")
    pm = stripe.PaymentMethod.create(
        type="sepa_debit",
        sepa_debit={"iban": TEST_IBAN},
        billing_details={
            "name": "Cabinet Dupont Assurances",
            "email": "cabinet.dupont@example.fr",
        },
    )
    stripe.PaymentMethod.attach(pm.id, customer=stripe_customer_id)
    print(f"  Payment method: {pm.id}")
    return pm.id


def confirm_setup_intent(stripe_customer_id: str, pm_id: str) -> str:
    """
    Creates and immediately confirms a SetupIntent — this collects the
    SEPA mandate. In production this step happens via Stripe.js in a
    browser; in test mode we can confirm server-side.
    """
    print("Creating and confirming SetupIntent (mandate collection)...")
    si = stripe.SetupIntent.create(
        customer=stripe_customer_id,
        payment_method_types=["sepa_debit"],
        payment_method=pm_id,
        usage="off_session",
        confirm=True,
        mandate_data={
            "customer_acceptance": {
                "type": "offline",
            }
        },
    )
    print(f"  SetupIntent: {si.id}  status: {si.status}")
    return si.id


def store_stripe_ids(stripe_customer_id: str, pm_id: str) -> None:
    print(f"Storing Stripe IDs on ERPNext customer '{CUSTOMER_FRAPPE_NAME}'...")
    frappe.db.set_value("Customer", CUSTOMER_FRAPPE_NAME, {
        "stripe_customer_id": stripe_customer_id,
        "stripe_payment_method_id": pm_id,
    })
    frappe.db.commit()
    print("  Done.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if not STRIPE_SECRET_KEY:
        print("ERROR: STRIPE_SECRET_KEY env var not set")
        sys.exit(1)

    stripe.api_key = STRIPE_SECRET_KEY

    frappe.init(site=SITE)
    frappe.connect()

    if not frappe.db.exists("Customer", CUSTOMER_FRAPPE_NAME):
        print(f"ERROR: Customer '{CUSTOMER_FRAPPE_NAME}' not found in ERPNext")
        sys.exit(1)

    setup_custom_fields()

    stripe_customer_id = create_stripe_customer(CUSTOMER_FRAPPE_NAME)
    pm_id = attach_sepa_payment_method(stripe_customer_id)
    confirm_setup_intent(stripe_customer_id, pm_id)
    store_stripe_ids(stripe_customer_id, pm_id)

    print()
    print("✅ Stripe SEPA setup complete.")
    print(f"   Stripe Customer:       {stripe_customer_id}")
    print(f"   Payment Method (SEPA): {pm_id}")
    print()
    print("Next steps:")
    print("  1. Configure Stripe webhook in Dashboard → Developers → Webhooks:")
    print("     Endpoint: https://erp.devandre.sbs/api/method/erpnext_sepa.api.stripe_webhook")
    print("     Events: payment_intent.succeeded, payment_intent.payment_failed,")
    print("             setup_intent.succeeded")
    print("  2. Store secrets in Vault:")
    print("     vault kv put secret/platform/stripe \\")
    print("       secret_key=sk_test_... \\")
    print("       webhook_secret=whsec_...")
    print("  3. Import n8n workflow: workflows/stripe_invoice_to_payment.json")
    print("  4. Submit ACC-SINV-2026-00001 — watch Stripe Dashboard + ERPNext")

"""
erpnext_sepa.api
================
Stripe SEPA Direct Debit integration for ERPNext.

Endpoints
---------
POST /api/method/erpnext_sepa.api.stripe_webhook
    Receives all Stripe webhook events (signature-verified).
    payment_intent.succeeded      → Payment Entry + reconcile invoice
    payment_intent.payment_failed → flag invoice gc_payment_status=failed
    setup_intent.succeeded        → store stripe_payment_method_id on Customer

GET  /api/method/erpnext_sepa.api.get_payment_status?invoice=<name>
    Returns Stripe payment status for a given Sales Invoice.

Environment variables (fed from Vault secret/platform/stripe via ESO)
----------------------------------------------------------------------
STRIPE_SECRET_KEY      sk_test_... or sk_live_...
STRIPE_WEBHOOK_SECRET  whsec_...  (from Stripe Dashboard → Webhooks)
"""

import os

import frappe
import stripe
from frappe.utils import nowdate

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")


# ---------------------------------------------------------------------------
# Public webhook receiver
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def stripe_webhook():
    """
    Entry point for all Stripe webhook events.
    Stripe-Signature header is verified using the webhook endpoint secret.
    """
    payload: bytes = frappe.request.data
    sig_header: str = frappe.request.headers.get("Stripe-Signature", "")
    webhook_secret: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    if not webhook_secret:
        frappe.log_error("STRIPE_WEBHOOK_SECRET not configured", "Stripe SEPA")
        frappe.throw("Webhook secret not configured", frappe.AuthenticationError)

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except stripe.SignatureVerificationError:
        frappe.throw("Invalid Stripe webhook signature", frappe.AuthenticationError)

    etype = event["type"]

    if etype == "payment_intent.succeeded":
        _handle_payment_succeeded(event["data"]["object"])
    elif etype == "payment_intent.payment_failed":
        _handle_payment_failed(event["data"]["object"])
    elif etype == "setup_intent.succeeded":
        _handle_setup_succeeded(event["data"]["object"])

    return {"received": True}


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_payment_status(invoice: str) -> dict:
    doc = frappe.get_doc("Sales Invoice", invoice)
    return {
        "invoice": invoice,
        "stripe_payment_intent_id": doc.get("stripe_payment_intent_id"),
        "stripe_payment_status": doc.get("stripe_payment_status"),
        "outstanding_amount": doc.outstanding_amount,
    }


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_payment_succeeded(payment_intent: dict) -> None:
    intent_id = payment_intent["id"]
    invoice_name = _invoice_for_intent(intent_id)

    if not invoice_name:
        frappe.log_error(
            f"Stripe PaymentIntent {intent_id} has no matching Sales Invoice",
            "Stripe SEPA",
        )
        return

    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    if invoice.outstanding_amount <= 0:
        return  # already reconciled

    amount_eur = payment_intent["amount_received"] / 100.0
    _create_payment_entry(invoice, intent_id, amount_eur)

    frappe.db.set_value("Sales Invoice", invoice_name, "stripe_payment_status", "succeeded")
    frappe.db.commit()


def _handle_payment_failed(payment_intent: dict) -> None:
    intent_id = payment_intent["id"]
    invoice_name = _invoice_for_intent(intent_id)

    if not invoice_name:
        return

    failure_msg = (
        payment_intent.get("last_payment_error", {}) or {}
    ).get("message", "unknown")

    frappe.db.set_value("Sales Invoice", invoice_name, "stripe_payment_status", "failed")
    frappe.db.commit()
    frappe.log_error(
        f"Stripe payment failed for invoice {invoice_name} "
        f"(intent {intent_id}): {failure_msg}",
        "Stripe SEPA Payment Failed",
    )


def _handle_setup_succeeded(setup_intent: dict) -> None:
    """Store the confirmed payment method on the ERPNext Customer."""
    pm_id = setup_intent.get("payment_method")
    stripe_customer_id = setup_intent.get("customer")

    if not (pm_id and stripe_customer_id):
        return

    rows = frappe.db.get_all(
        "Customer",
        filters={"stripe_customer_id": stripe_customer_id},
        fields=["name"],
        limit=1,
    )
    if rows:
        frappe.db.set_value("Customer", rows[0]["name"], "stripe_payment_method_id", pm_id)
        frappe.db.commit()


# ---------------------------------------------------------------------------
# Payment Entry creation
# ---------------------------------------------------------------------------

def _create_payment_entry(invoice, intent_id: str, amount: float) -> None:
    pe = frappe.new_doc("Payment Entry")
    pe.payment_type = "Receive"
    pe.posting_date = nowdate()
    pe.company = invoice.company
    pe.mode_of_payment = "Wire Transfer"
    pe.party_type = "Customer"
    pe.party = invoice.customer
    pe.paid_amount = amount
    pe.received_amount = amount
    pe.paid_from = frappe.db.get_value(
        "Company", invoice.company, "default_receivable_account"
    )
    pe.paid_to = frappe.db.get_value(
        "Company", invoice.company, "default_bank_account"
    )
    pe.reference_no = intent_id
    pe.reference_date = nowdate()
    pe.append(
        "references",
        {
            "reference_doctype": "Sales Invoice",
            "reference_name": invoice.name,
            "allocated_amount": amount,
        },
    )
    pe.insert(ignore_permissions=True)
    pe.submit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _invoice_for_intent(intent_id: str) -> str | None:
    rows = frappe.db.get_all(
        "Sales Invoice",
        filters={"stripe_payment_intent_id": intent_id},
        fields=["name"],
        limit=1,
    )
    return rows[0]["name"] if rows else None

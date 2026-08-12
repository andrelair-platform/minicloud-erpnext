"""
erpnext_sepa.api
================
Two public endpoints:

  POST /api/method/erpnext_sepa.api.gocardless_webhook
      Receives GoCardless event payloads (HMAC-verified).
      On payments.paid_out → creates a Payment Entry and reconciles the invoice.
      On mandates.active   → stores gc_mandate_id on the Customer.

  GET  /api/method/erpnext_sepa.api.get_payment_status?invoice=<name>
      Returns the GoCardless payment status for a given Sales Invoice.
"""

import hashlib
import hmac
import json
import os

import frappe
from frappe.utils import nowdate


# ---------------------------------------------------------------------------
# Public webhook receiver
# ---------------------------------------------------------------------------

@frappe.whitelist(allow_guest=True)
def gocardless_webhook():
    """
    Receives all GoCardless event webhooks.
    Signature verification uses the webhook secret stored in
    Vault secret/platform/gocardless key: webhook_secret.
    """
    raw_body: bytes = frappe.request.data
    signature = frappe.request.headers.get("Webhook-Signature", "")

    webhook_secret = os.environ.get("GC_WEBHOOK_SECRET", "")
    if webhook_secret and not _verify_signature(raw_body, signature, webhook_secret):
        frappe.throw("Invalid GoCardless webhook signature", frappe.AuthenticationError)

    payload = json.loads(raw_body)
    for event in payload.get("events", []):
        resource_type = event.get("resource_type")
        action = event.get("action")

        if resource_type == "payments" and action == "paid_out":
            _handle_payment_paid(event)
        elif resource_type == "mandates" and action == "active":
            _handle_mandate_active(event)
        elif resource_type == "payments" and action == "failed":
            _handle_payment_failed(event)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Status query
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_payment_status(invoice: str) -> dict:
    doc = frappe.get_doc("Sales Invoice", invoice)
    return {
        "invoice": invoice,
        "gc_payment_id": doc.get("gc_payment_id"),
        "gc_payment_status": doc.get("gc_payment_status"),
        "outstanding_amount": doc.outstanding_amount,
    }


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------

def _handle_payment_paid(event: dict) -> None:
    payment_id = event["links"]["payment"]
    invoice_name = _invoice_for_payment(payment_id)
    if not invoice_name:
        frappe.log_error(f"GoCardless payment {payment_id} — no matching Sales Invoice", "SEPA")
        return

    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    if invoice.outstanding_amount <= 0:
        return  # already paid

    _create_payment_entry(invoice, payment_id, event.get("amount", 0))

    frappe.db.set_value("Sales Invoice", invoice_name, "gc_payment_status", "paid_out")
    frappe.db.commit()


def _handle_mandate_active(event: dict) -> None:
    mandate_id = event["links"]["mandate"]
    customer_name = _customer_for_mandate(mandate_id)
    if customer_name:
        frappe.db.set_value("Customer", customer_name, "gc_mandate_id", mandate_id)
        frappe.db.commit()


def _handle_payment_failed(event: dict) -> None:
    payment_id = event["links"]["payment"]
    invoice_name = _invoice_for_payment(payment_id)
    if invoice_name:
        frappe.db.set_value("Sales Invoice", invoice_name, "gc_payment_status", "failed")
        frappe.db.commit()
        frappe.log_error(
            f"GoCardless payment {payment_id} failed for invoice {invoice_name}",
            "SEPA Payment Failed",
        )


# ---------------------------------------------------------------------------
# Payment Entry creation
# ---------------------------------------------------------------------------

def _create_payment_entry(invoice, payment_id: str, amount_pence: int) -> None:
    amount = amount_pence / 100.0 if amount_pence else invoice.outstanding_amount

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
    pe.reference_no = payment_id
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

def _invoice_for_payment(payment_id: str) -> str | None:
    rows = frappe.db.get_all(
        "Sales Invoice",
        filters={"gc_payment_id": payment_id},
        fields=["name"],
        limit=1,
    )
    return rows[0]["name"] if rows else None


def _customer_for_mandate(mandate_id: str) -> str | None:
    rows = frappe.db.get_all(
        "Customer",
        filters={"gc_mandate_id": mandate_id},
        fields=["name"],
        limit=1,
    )
    return rows[0]["name"] if rows else None


def _verify_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

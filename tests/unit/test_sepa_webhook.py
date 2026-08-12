"""
Unit tests for erpnext_sepa.api webhook parsing helpers.
All Frappe calls are mocked via the conftest sys.modules mock.
"""

import hashlib
import hmac
import json
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

# ---------------------------------------------------------------------------
# Import module under test after frappe mock is in place
# ---------------------------------------------------------------------------
from erpnext_sepa.api import (
    _verify_signature,
    _handle_payment_paid,
    _handle_mandate_active,
    _handle_payment_failed,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PAYMENT_PAID_EVENT = {
    "id": "EV001",
    "resource_type": "payments",
    "action": "paid_out",
    "links": {"payment": "PM12345"},
    "amount": 169500,
}

MANDATE_ACTIVE_EVENT = {
    "id": "EV002",
    "resource_type": "mandates",
    "action": "active",
    "links": {"mandate": "MD000026"},
}

PAYMENT_FAILED_EVENT = {
    "id": "EV003",
    "resource_type": "payments",
    "action": "failed",
    "links": {"payment": "PM99999"},
}


# ---------------------------------------------------------------------------
# _verify_signature
# ---------------------------------------------------------------------------

class TestVerifySignature:
    def _sig(self, body: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature_returns_true(self):
        body = b'{"events": []}'
        secret = "mysecret"
        assert _verify_signature(body, self._sig(body, secret), secret) is True

    def test_invalid_signature_returns_false(self):
        body = b'{"events": []}'
        assert _verify_signature(body, "badsig", "mysecret") is False

    def test_empty_body_valid_sig(self):
        body = b""
        secret = "s"
        assert _verify_signature(body, self._sig(body, secret), secret) is True

    def test_tampered_body_returns_false(self):
        body = b'{"events": []}'
        secret = "mysecret"
        sig = self._sig(body, secret)
        assert _verify_signature(b'{"events": [{}]}', sig, secret) is False


# ---------------------------------------------------------------------------
# _handle_payment_paid
# ---------------------------------------------------------------------------

class TestHandlePaymentPaid:
    def setup_method(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.reset_mock()

    def _make_invoice(self, outstanding=1695.0, **kwargs):
        inv = MagicMock()
        inv.name = "ACC-SINV-2026-00001"
        inv.customer = "Cabinet Dupont"
        inv.company = "Ktayl Solutions"
        inv.outstanding_amount = outstanding
        for k, v in kwargs.items():
            setattr(inv, k, v)
        return inv

    def test_no_matching_invoice_logs_error(self):
        self.frappe.db.get_all.return_value = []
        _handle_payment_paid(PAYMENT_PAID_EVENT)
        self.frappe.log_error.assert_called_once()

    def test_already_paid_invoice_skipped(self):
        invoice = self._make_invoice(outstanding=0.0)
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        _handle_payment_paid(PAYMENT_PAID_EVENT)
        # Payment Entry should NOT be created
        self.frappe.new_doc.assert_not_called()

    def test_payment_entry_created_for_unpaid_invoice(self):
        invoice = self._make_invoice(outstanding=1695.0)
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        self.frappe.db.get_value.return_value = "4111 - Clients - KS"
        pe_mock = MagicMock()
        self.frappe.new_doc.return_value = pe_mock

        _handle_payment_paid(PAYMENT_PAID_EVENT)

        self.frappe.new_doc.assert_called_once_with("Payment Entry")
        pe_mock.insert.assert_called_once()
        pe_mock.submit.assert_called_once()

    def test_payment_status_updated_to_paid_out(self):
        invoice = self._make_invoice(outstanding=1695.0)
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        self.frappe.db.get_value.return_value = "4111 - Clients - KS"
        self.frappe.new_doc.return_value = MagicMock()

        _handle_payment_paid(PAYMENT_PAID_EVENT)

        self.frappe.db.set_value.assert_called_with(
            "Sales Invoice", invoice.name, "gc_payment_status", "paid_out"
        )


# ---------------------------------------------------------------------------
# _handle_mandate_active
# ---------------------------------------------------------------------------

class TestHandleMandateActive:
    def setup_method(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.reset_mock()

    def test_stores_mandate_id_on_customer(self):
        self.frappe.db.get_all.return_value = [{"name": "Cabinet Dupont"}]
        _handle_mandate_active(MANDATE_ACTIVE_EVENT)
        self.frappe.db.set_value.assert_called_with(
            "Customer", "Cabinet Dupont", "gc_mandate_id", "MD000026"
        )

    def test_no_customer_does_not_call_set_value(self):
        self.frappe.db.get_all.return_value = []
        _handle_mandate_active(MANDATE_ACTIVE_EVENT)
        self.frappe.db.set_value.assert_not_called()


# ---------------------------------------------------------------------------
# _handle_payment_failed
# ---------------------------------------------------------------------------

class TestHandlePaymentFailed:
    def setup_method(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.reset_mock()

    def test_updates_status_to_failed(self):
        self.frappe.db.get_all.return_value = [{"name": "ACC-SINV-2026-00002"}]
        _handle_payment_failed(PAYMENT_FAILED_EVENT)
        self.frappe.db.set_value.assert_called_with(
            "Sales Invoice", "ACC-SINV-2026-00002", "gc_payment_status", "failed"
        )

    def test_logs_error_on_failure(self):
        self.frappe.db.get_all.return_value = [{"name": "ACC-SINV-2026-00002"}]
        _handle_payment_failed(PAYMENT_FAILED_EVENT)
        self.frappe.log_error.assert_called_once()

    def test_no_matching_invoice_does_not_set_value(self):
        self.frappe.db.get_all.return_value = []
        _handle_payment_failed(PAYMENT_FAILED_EVENT)
        self.frappe.db.set_value.assert_not_called()

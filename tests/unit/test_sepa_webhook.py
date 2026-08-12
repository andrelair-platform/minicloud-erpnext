"""
Unit tests for erpnext_sepa.api (Stripe webhook handlers).

_handle_payment_succeeded / _handle_payment_failed / _handle_setup_succeeded
are pure business-logic functions tested with the frappe sys.modules mock.

stripe.Webhook.construct_event is tested via the signature helper in mock_stripe.
"""

import sys
from unittest.mock import MagicMock

import pytest

from erpnext_sepa.api import (
    _handle_payment_failed,
    _handle_payment_succeeded,
    _handle_setup_succeeded,
    _invoice_for_intent,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

PAYMENT_INTENT_SUCCEEDED = {
    "id": "pi_test_succeeded",
    "object": "payment_intent",
    "status": "succeeded",
    "amount": 169500,
    "amount_received": 169500,
    "currency": "eur",
    "customer": "cus_test123",
    "payment_method": "pm_test123",
    "metadata": {"erpnext_invoice": "ACC-SINV-2026-00001"},
    "last_payment_error": None,
}

PAYMENT_INTENT_FAILED = {
    "id": "pi_test_failed",
    "object": "payment_intent",
    "status": "requires_payment_method",
    "amount": 169500,
    "amount_received": 0,
    "currency": "eur",
    "customer": "cus_test123",
    "last_payment_error": {"message": "Your card has insufficient funds."},
}

SETUP_INTENT_SUCCEEDED = {
    "id": "seti_test123",
    "object": "setup_intent",
    "status": "succeeded",
    "customer": "cus_test123",
    "payment_method": "pm_sepa_test123",
}


# ---------------------------------------------------------------------------
# _handle_payment_succeeded
# ---------------------------------------------------------------------------

class TestHandlePaymentSucceeded:
    def setup_method(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.reset_mock()

    def _invoice(self, outstanding: float = 1695.0) -> MagicMock:
        inv = MagicMock()
        inv.name = "ACC-SINV-2026-00001"
        inv.customer = "Cabinet Dupont"
        inv.company = "Ktayl Solutions"
        inv.outstanding_amount = outstanding
        return inv

    def test_no_matching_invoice_logs_error(self):
        self.frappe.db.get_all.return_value = []
        _handle_payment_succeeded(PAYMENT_INTENT_SUCCEEDED)
        self.frappe.log_error.assert_called_once()
        assert "pi_test_succeeded" in self.frappe.log_error.call_args[0][0]

    def test_already_paid_invoice_is_skipped(self):
        invoice = self._invoice(outstanding=0.0)
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        _handle_payment_succeeded(PAYMENT_INTENT_SUCCEEDED)
        self.frappe.new_doc.assert_not_called()

    def test_payment_entry_created_for_unpaid_invoice(self):
        invoice = self._invoice()
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        self.frappe.db.get_value.return_value = "4111 - Clients - KS"
        pe_mock = MagicMock()
        self.frappe.new_doc.return_value = pe_mock

        _handle_payment_succeeded(PAYMENT_INTENT_SUCCEEDED)

        self.frappe.new_doc.assert_called_once_with("Payment Entry")
        pe_mock.insert.assert_called_once()
        pe_mock.submit.assert_called_once()

    def test_amount_converted_from_cents(self):
        """amount_received=169500 cents → 1695.0 EUR on Payment Entry."""
        invoice = self._invoice()
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        self.frappe.db.get_value.return_value = "4111 - Clients - KS"
        pe_mock = MagicMock()
        self.frappe.new_doc.return_value = pe_mock

        _handle_payment_succeeded(PAYMENT_INTENT_SUCCEEDED)

        assert pe_mock.paid_amount == pytest.approx(1695.0)
        assert pe_mock.received_amount == pytest.approx(1695.0)

    def test_intent_id_stored_as_reference(self):
        invoice = self._invoice()
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        self.frappe.db.get_value.return_value = "4111 - Clients - KS"
        pe_mock = MagicMock()
        self.frappe.new_doc.return_value = pe_mock

        _handle_payment_succeeded(PAYMENT_INTENT_SUCCEEDED)

        assert pe_mock.reference_no == "pi_test_succeeded"

    def test_status_updated_to_succeeded(self):
        invoice = self._invoice()
        self.frappe.db.get_all.return_value = [{"name": invoice.name}]
        self.frappe.get_doc.return_value = invoice
        self.frappe.db.get_value.return_value = "4111 - Clients - KS"
        self.frappe.new_doc.return_value = MagicMock()

        _handle_payment_succeeded(PAYMENT_INTENT_SUCCEEDED)

        self.frappe.db.set_value.assert_called_with(
            "Sales Invoice", invoice.name, "stripe_payment_status", "succeeded"
        )


# ---------------------------------------------------------------------------
# _handle_payment_failed
# ---------------------------------------------------------------------------

class TestHandlePaymentFailed:
    def setup_method(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.reset_mock()

    def test_status_updated_to_failed(self):
        self.frappe.db.get_all.return_value = [{"name": "ACC-SINV-2026-00001"}]
        _handle_payment_failed(PAYMENT_INTENT_FAILED)
        self.frappe.db.set_value.assert_called_with(
            "Sales Invoice", "ACC-SINV-2026-00001", "stripe_payment_status", "failed"
        )

    def test_error_is_logged(self):
        self.frappe.db.get_all.return_value = [{"name": "ACC-SINV-2026-00001"}]
        _handle_payment_failed(PAYMENT_INTENT_FAILED)
        self.frappe.log_error.assert_called_once()

    def test_failure_message_included_in_log(self):
        self.frappe.db.get_all.return_value = [{"name": "ACC-SINV-2026-00001"}]
        _handle_payment_failed(PAYMENT_INTENT_FAILED)
        log_msg = self.frappe.log_error.call_args[0][0]
        assert "insufficient funds" in log_msg

    def test_no_matching_invoice_does_not_set_value(self):
        self.frappe.db.get_all.return_value = []
        _handle_payment_failed(PAYMENT_INTENT_FAILED)
        self.frappe.db.set_value.assert_not_called()

    def test_none_last_payment_error_does_not_crash(self):
        intent = {**PAYMENT_INTENT_FAILED, "last_payment_error": None}
        self.frappe.db.get_all.return_value = [{"name": "ACC-SINV-2026-00001"}]
        _handle_payment_failed(intent)
        self.frappe.log_error.assert_called_once()


# ---------------------------------------------------------------------------
# _handle_setup_succeeded
# ---------------------------------------------------------------------------

class TestHandleSetupSucceeded:
    def setup_method(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.reset_mock()

    def test_stores_payment_method_on_customer(self):
        self.frappe.db.get_all.return_value = [{"name": "Cabinet Dupont"}]
        _handle_setup_succeeded(SETUP_INTENT_SUCCEEDED)
        self.frappe.db.set_value.assert_called_with(
            "Customer", "Cabinet Dupont", "stripe_payment_method_id", "pm_sepa_test123"
        )

    def test_no_customer_does_not_set_value(self):
        self.frappe.db.get_all.return_value = []
        _handle_setup_succeeded(SETUP_INTENT_SUCCEEDED)
        self.frappe.db.set_value.assert_not_called()

    def test_missing_payment_method_does_not_crash(self):
        intent = {**SETUP_INTENT_SUCCEEDED, "payment_method": None}
        _handle_setup_succeeded(intent)
        self.frappe.db.set_value.assert_not_called()

    def test_missing_customer_does_not_crash(self):
        intent = {**SETUP_INTENT_SUCCEEDED, "customer": None}
        _handle_setup_succeeded(intent)
        self.frappe.db.set_value.assert_not_called()


# ---------------------------------------------------------------------------
# _invoice_for_intent
# ---------------------------------------------------------------------------

class TestInvoiceForIntent:
    def setup_method(self):
        self.frappe = sys.modules["frappe"]
        self.frappe.reset_mock()

    def test_returns_invoice_name_when_found(self):
        self.frappe.db.get_all.return_value = [{"name": "ACC-SINV-2026-00001"}]
        result = _invoice_for_intent("pi_test_succeeded")
        assert result == "ACC-SINV-2026-00001"

    def test_returns_none_when_not_found(self):
        self.frappe.db.get_all.return_value = []
        assert _invoice_for_intent("pi_unknown") is None

    def test_queries_correct_field(self):
        self.frappe.db.get_all.return_value = []
        _invoice_for_intent("pi_test")
        call_kwargs = self.frappe.db.get_all.call_args
        filters = call_kwargs[1]["filters"] if call_kwargs[1] else call_kwargs[0][1]
        assert "stripe_payment_intent_id" in filters

"""
Unit tests for erpnext_sepa.sepa_pain008.build_pain008().
Pure function — no Frappe, no DB, no network.
"""

import xml.etree.ElementTree as ET
from datetime import datetime

import pytest
from erpnext_sepa.sepa_pain008 import _esc, _msg_id, build_pain008

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

CREDITOR = {
    "creditor_name": "Ktayl Solutions",
    "creditor_iban": "FR7630006000019876543210189",
    "creditor_bic": "BNPAFRPPXXX",
    "creditor_id": "FR72ZZZ123456",
}

INVOICE_1 = {
    "invoice_name": "ACC-SINV-2026-00001",
    "amount": 1695.0,
    "currency": "EUR",
    "customer_name": "Cabinet Dupont",
    "iban": "FR7630006000011234567890189",
    "bic": "BNPAFRPPXXX",
    "mandate_id": "MD000026",
    "mandate_date": "2026-01-01",
    "due_date": "2026-02-01",
}

INVOICE_2 = {
    "invoice_name": "ACC-SINV-2026-00002",
    "amount": 850.50,
    "currency": "EUR",
    "customer_name": "Assurance Martin",
    "iban": "FR7630006000019999999999189",
    "bic": "BNPAFRPPXXX",
    "mandate_id": "MD000027",
    "mandate_date": "2026-01-15",
    "due_date": "2026-02-01",
}

NS = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"


def _Q(tag):
    return f"{{{NS}}}{tag}"


def _xml(invoices=None, **kwargs) -> ET.Element:
    if invoices is None:
        invoices = [INVOICE_1]
    params = {**CREDITOR, **kwargs}
    raw = build_pain008(invoices, **params)
    return ET.fromstring(raw)


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------


class TestOutputFormat:
    def test_returns_bytes(self):
        assert isinstance(build_pain008([INVOICE_1], **CREDITOR), bytes)

    def test_utf8_decodable(self):
        raw = build_pain008([INVOICE_1], **CREDITOR)
        assert raw.decode("utf-8")

    def test_xml_declaration_present(self):
        raw = build_pain008([INVOICE_1], **CREDITOR)
        assert raw.startswith(b'<?xml version="1.0"')

    def test_valid_xml(self):
        root = _xml()
        assert root is not None

    def test_root_is_document(self):
        root = _xml()
        assert root.tag == _Q("Document")

    def test_namespace_correct(self):
        raw = build_pain008([INVOICE_1], **CREDITOR)
        assert b"pain.008.001.02" in raw


# ---------------------------------------------------------------------------
# Group Header
# ---------------------------------------------------------------------------


class TestGroupHeader:
    def _grp_hdr(self, invoices=None):
        root = _xml(invoices)
        init = root.find(_Q("CstmrDrctDbtInitn"))
        return init.find(_Q("GrpHdr"))

    def test_msg_id_present(self):
        hdr = self._grp_hdr()
        assert hdr.find(_Q("MsgId")).text.startswith("MINICLOUD-")

    def test_creation_dt_format(self):
        dt = datetime(2026, 2, 1, 12, 0, 0)
        raw = build_pain008([INVOICE_1], **CREDITOR, creation_dt=dt)
        root = ET.fromstring(raw)
        hdr = root.find(_Q("CstmrDrctDbtInitn")).find(_Q("GrpHdr"))
        assert hdr.find(_Q("CreDtTm")).text == "2026-02-01T12:00:00"

    def test_nb_of_txs_one(self):
        hdr = self._grp_hdr([INVOICE_1])
        assert hdr.find(_Q("NbOfTxs")).text == "1"

    def test_nb_of_txs_two(self):
        hdr = self._grp_hdr([INVOICE_1, INVOICE_2])
        assert hdr.find(_Q("NbOfTxs")).text == "2"

    def test_ctrl_sum_one_invoice(self):
        hdr = self._grp_hdr([INVOICE_1])
        assert float(hdr.find(_Q("CtrlSum")).text) == pytest.approx(1695.0)

    def test_ctrl_sum_two_invoices(self):
        hdr = self._grp_hdr([INVOICE_1, INVOICE_2])
        assert float(hdr.find(_Q("CtrlSum")).text) == pytest.approx(2545.50)

    def test_initiating_party_name(self):
        hdr = self._grp_hdr()
        party = hdr.find(_Q("InitgPty"))
        assert party.find(_Q("Nm")).text == "Ktayl Solutions"


# ---------------------------------------------------------------------------
# Payment Information
# ---------------------------------------------------------------------------


class TestPaymentInfo:
    def _pmt_inf(self, invoices=None):
        root = _xml(invoices)
        init = root.find(_Q("CstmrDrctDbtInitn"))
        return init.find(_Q("PmtInf"))

    def test_payment_method_dd(self):
        assert self._pmt_inf().find(_Q("PmtMtd")).text == "DD"

    def test_service_level_sepa(self):
        sl = self._pmt_inf().find(f".//{_Q('SvcLvl')}")
        assert sl.find(_Q("Cd")).text == "SEPA"

    def test_local_instrument_core(self):
        li = self._pmt_inf().find(f".//{_Q('LclInstrm')}")
        assert li.find(_Q("Cd")).text == "CORE"

    def test_sequence_type_rcur(self):
        assert self._pmt_inf().find(f".//{_Q('SeqTp')}").text == "RCUR"

    def test_collection_date(self):
        assert self._pmt_inf().find(_Q("ReqdColltnDt")).text == "2026-02-01"

    def test_creditor_name(self):
        cdtr = self._pmt_inf().find(_Q("Cdtr"))
        assert cdtr.find(_Q("Nm")).text == "Ktayl Solutions"

    def test_creditor_iban(self):
        acct = self._pmt_inf().find(_Q("CdtrAcct"))
        assert acct.find(f".//{_Q('IBAN')}").text == "FR7630006000019876543210189"

    def test_creditor_bic(self):
        agt = self._pmt_inf().find(_Q("CdtrAgt"))
        assert agt.find(f".//{_Q('BIC')}").text == "BNPAFRPPXXX"

    def test_creditor_scheme_id(self):
        # CdtrSchmeId/Id/PrvtId/Othr/Id — the outer Id has no text, inner Othr/Id has the value
        scheme = self._pmt_inf().find(f".//{_Q('CdtrSchmeId')}")
        othr_id = scheme.find(f".//{_Q('Othr')}/{_Q('Id')}")
        assert othr_id.text == "FR72ZZZ123456"


# ---------------------------------------------------------------------------
# Transaction block
# ---------------------------------------------------------------------------


class TestTransaction:
    def _txs(self, invoices=None):
        root = _xml(invoices)
        pmt = root.find(_Q("CstmrDrctDbtInitn")).find(_Q("PmtInf"))
        return pmt.findall(_Q("DrctDbtTxInf"))

    def test_one_transaction_for_one_invoice(self):
        assert len(self._txs([INVOICE_1])) == 1

    def test_two_transactions_for_two_invoices(self):
        assert len(self._txs([INVOICE_1, INVOICE_2])) == 2

    def test_end_to_end_id_is_invoice_name(self):
        tx = self._txs()[0]
        pmtid = tx.find(_Q("PmtId"))
        assert pmtid.find(_Q("EndToEndId")).text == "ACC-SINV-2026-00001"

    def test_amount_and_currency(self):
        tx = self._txs()[0]
        amt = tx.find(_Q("InstdAmt"))
        assert float(amt.text) == pytest.approx(1695.0)
        assert amt.get("Ccy") == "EUR"

    def test_mandate_id(self):
        tx = self._txs()[0]
        mndt = tx.find(f".//{_Q('MndtId')}")
        assert mndt.text == "MD000026"

    def test_mandate_date(self):
        tx = self._txs()[0]
        dt = tx.find(f".//{_Q('DtOfSgntr')}")
        assert dt.text == "2026-01-01"

    def test_debtor_name(self):
        tx = self._txs()[0]
        dbtr = tx.find(_Q("Dbtr"))
        assert dbtr.find(_Q("Nm")).text == "Cabinet Dupont"

    def test_debtor_iban(self):
        tx = self._txs()[0]
        acct = tx.find(_Q("DbtrAcct"))
        assert acct.find(f".//{_Q('IBAN')}").text == "FR7630006000011234567890189"

    def test_debtor_bic(self):
        tx = self._txs()[0]
        agt = tx.find(_Q("DbtrAgt"))
        assert agt.find(f".//{_Q('BIC')}").text == "BNPAFRPPXXX"

    def test_purpose_code_insu(self):
        """Insurance payments must carry purpose code INSU (ISO 20022)."""
        tx = self._txs()[0]
        purp = tx.find(_Q("Purp"))
        assert purp.find(_Q("Cd")).text == "INSU"

    def test_remittance_info_is_invoice_name(self):
        tx = self._txs()[0]
        rmt = tx.find(_Q("RmtInf"))
        assert rmt.find(_Q("Ustrd")).text == "ACC-SINV-2026-00001"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_invoices_produces_valid_xml(self):
        raw = build_pain008([], **CREDITOR)
        root = ET.fromstring(raw)
        assert root is not None

    def test_amount_rounded_to_two_decimals(self):
        inv = {**INVOICE_1, "amount": 100.999}
        raw = build_pain008([inv], **CREDITOR)
        root = ET.fromstring(raw)
        tx = root.find(f".//{_Q('DrctDbtTxInf')}")
        assert float(tx.find(_Q("InstdAmt")).text) == pytest.approx(101.0)

    def test_special_chars_escaped_in_name(self):
        inv = {**INVOICE_1, "customer_name": "Dupont & Fils <SARL>"}
        raw = build_pain008([inv], **CREDITOR)
        assert b"&amp;" in raw
        assert b"&lt;" in raw


# ---------------------------------------------------------------------------
# Helper: _esc
# ---------------------------------------------------------------------------


class TestEsc:
    def test_ampersand(self):
        assert _esc("A&B") == "A&amp;B"

    def test_less_than(self):
        assert _esc("A<B") == "A&lt;B"

    def test_greater_than(self):
        assert _esc("A>B") == "A&gt;B"

    def test_no_special(self):
        assert _esc("DUPONT") == "DUPONT"


# ---------------------------------------------------------------------------
# Helper: _msg_id
# ---------------------------------------------------------------------------


class TestMsgId:
    def test_starts_with_minicloud(self):
        dt = datetime(2026, 2, 1, 12, 0, 0)
        assert _msg_id(dt).startswith("MINICLOUD-")

    def test_contains_timestamp(self):
        dt = datetime(2026, 2, 1, 12, 0, 0)
        assert "20260201120000" in _msg_id(dt)

    def test_deterministic_for_same_dt(self):
        dt = datetime(2026, 2, 1, 12, 0, 0)
        assert _msg_id(dt) == _msg_id(dt)

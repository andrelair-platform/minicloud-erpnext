"""
Unit tests for erpnext_facturx.erpnext_facturx.facturx._build_cii_xml().

frappe.get_doc() is mocked via the conftest.py sys.modules mock.
We test the CII XML structure independently of PDF/A-3 embedding.
"""

import sys
import xml.etree.ElementTree as ET

import pytest

# Import _build_cii_xml after conftest has installed the frappe mock
from erpnext_facturx.facturx import _build_cii_xml

from tests.conftest import make_company_doc, make_invoice_doc

RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"


@pytest.fixture(autouse=True)
def mock_frappe_get_doc():
    """Return a deterministic company doc from frappe.get_doc for every test."""
    frappe = sys.modules["frappe"]
    company = make_company_doc()
    frappe.get_doc.return_value = company
    yield frappe
    frappe.get_doc.reset_mock()


def _xml(doc=None) -> ET.Element:
    """Build CII XML and parse it, returning the root element."""
    if doc is None:
        doc = make_invoice_doc()
    raw = _build_cii_xml(doc)
    return ET.fromstring(raw)


class TestCiiXmlOutput:
    def test_returns_bytes(self):
        doc = make_invoice_doc()
        result = _build_cii_xml(doc)
        assert isinstance(result, bytes)

    def test_is_valid_xml(self):
        doc = make_invoice_doc()
        raw = _build_cii_xml(doc)
        root = ET.fromstring(raw)
        assert root is not None

    def test_root_element_is_cross_industry_invoice(self):
        root = _xml()
        assert f"{{{RSM}}}CrossIndustryInvoice" in root.tag


class TestGuidelineId:
    def test_minimum_profile_id(self):
        """The Factur-X Minimum profile ID must be declared."""
        root = _xml()
        ctx = root.find(f"{{{RSM}}}ExchangedDocumentContext")
        gl = ctx.find(f".//{{{RAM}}}ID")  # type: ignore[union-attr]
        assert gl is not None
        assert gl.text == "urn:factur-x.eu:1p0:minimum"


class TestExchangedDocument:
    def test_invoice_id(self):
        """ExchangedDocument/ID must equal the invoice doc name."""
        doc = make_invoice_doc(name="ACC-SINV-2026-99999")
        root = _xml(doc)
        ex_doc = root.find(f"{{{RSM}}}ExchangedDocument")
        id_elem = ex_doc.find(f"{{{RAM}}}ID")  # type: ignore[union-attr]
        assert id_elem is not None
        assert id_elem.text == "ACC-SINV-2026-99999"

    def test_type_code_380(self):
        """TypeCode 380 = Commercial Invoice (EN 16931)."""
        root = _xml()
        ex_doc = root.find(f"{{{RSM}}}ExchangedDocument")
        type_elem = ex_doc.find(f"{{{RAM}}}TypeCode")  # type: ignore[union-attr]
        assert type_elem is not None
        assert type_elem.text == "380"

    def test_date_format_yyyymmdd(self):
        """Issue date must be formatted as YYYYMMDD (format code 102)."""
        doc = make_invoice_doc(posting_date="2026-01-31")
        root = _xml(doc)
        ex_doc = root.find(f"{{{RSM}}}ExchangedDocument")
        dts = ex_doc.find(f".//{{{UDT}}}DateTimeString")  # type: ignore[union-attr]
        assert dts is not None
        assert dts.text == "20260131"
        assert dts.get("format") == "102"


class TestTradeParties:
    def test_seller_name_is_company(self):
        doc = make_invoice_doc(company="Ktayl Solutions")
        root = _xml(doc)
        seller = root.find(f".//{{{RAM}}}SellerTradeParty")
        name = seller.find(f"{{{RAM}}}Name")  # type: ignore[union-attr]
        assert name is not None
        assert name.text == "Ktayl Solutions"

    def test_buyer_name_is_customer(self):
        doc = make_invoice_doc(customer="Cabinet Dupont")
        root = _xml(doc)
        buyer = root.find(f".//{{{RAM}}}BuyerTradeParty")
        name = buyer.find(f"{{{RAM}}}Name")  # type: ignore[union-attr]
        assert name is not None
        assert name.text == "Cabinet Dupont"

    def test_siret_extracted_from_registration(self):
        """SIRET extracted from company registration_details field."""
        frappe = sys.modules["frappe"]
        frappe.get_doc.return_value = make_company_doc(registration_details="SIRET: 12345678901234")
        root = _xml()
        # Find by schemeID attribute
        seller = root.find(f".//{{{RAM}}}SellerTradeParty")
        regs = seller.findall(f".//{{{RAM}}}ID")  # type: ignore[union-attr]
        siret_ids = [r for r in regs if r.get("schemeID") == "0002"]
        assert len(siret_ids) == 1
        assert siret_ids[0].text == "12345678901234"

    def test_missing_siret_uses_default(self):
        """No SIRET in registration_details → fallback 00000000000000."""
        frappe = sys.modules["frappe"]
        frappe.get_doc.return_value = make_company_doc(registration_details="")
        root = _xml()
        seller = root.find(f".//{{{RAM}}}SellerTradeParty")
        regs = seller.findall(f".//{{{RAM}}}ID")  # type: ignore[union-attr]
        siret_ids = [r for r in regs if r.get("schemeID") == "0002"]
        assert siret_ids[0].text == "00000000000000"


class TestMonetarySummation:
    def test_currency_code(self):
        doc = make_invoice_doc(currency="EUR")
        root = _xml(doc)
        inv_currency = root.find(f".//{{{RAM}}}InvoiceCurrencyCode")
        assert inv_currency is not None
        assert inv_currency.text == "EUR"

    def test_net_total(self):
        doc = make_invoice_doc(net_total=1500.0)
        root = _xml(doc)
        tax_basis = root.find(f".//{{{RAM}}}TaxBasisTotalAmount")
        assert tax_basis is not None
        assert float(tax_basis.text) == pytest.approx(1500.0)  # type: ignore[arg-type]

    def test_grand_total(self):
        doc = make_invoice_doc(grand_total=1695.0)
        root = _xml(doc)
        grand = root.find(f".//{{{RAM}}}GrandTotalAmount")
        assert grand is not None
        assert float(grand.text) == pytest.approx(1695.0)  # type: ignore[arg-type]

    def test_tax_total(self):
        doc = make_invoice_doc(total_taxes_and_charges=195.0)
        root = _xml(doc)
        tax = root.find(f".//{{{RAM}}}TaxTotalAmount")
        assert tax is not None
        assert float(tax.text) == pytest.approx(195.0)  # type: ignore[arg-type]

import io
import xml.etree.ElementTree as ET
from xml.dom import minidom

import frappe
from frappe.utils.file_manager import save_file


def generate_and_attach(doc, method=None):
    xml_bytes = _build_cii_xml(doc)
    pdf_bytes = _get_invoice_pdf(doc)

    if pdf_bytes:
        try:
            from facturx import generate_from_file

            buf = io.BytesIO(pdf_bytes)
            out_buf = io.BytesIO()
            generate_from_file(buf, {"factur-x.xml": xml_bytes}, output_pdf_file=out_buf)
            out_buf.seek(0)
            final_pdf = out_buf.read()
            filename = f"{doc.name}-facturx.pdf"
            save_file(filename, final_pdf, doc.doctype, doc.name, is_private=1)
        except Exception:
            # Fallback: attach XML only (PDF/A-3 embedding failed)
            save_file(
                f"{doc.name}-facturx.xml",
                xml_bytes,
                doc.doctype,
                doc.name,
                is_private=1,
            )
    else:
        save_file(
            f"{doc.name}-facturx.xml",
            xml_bytes,
            doc.doctype,
            doc.name,
            is_private=1,
        )


_RSM = "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
_RAM = "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
_UDT = "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100"


def _build_cii_xml(doc):
    RSM = _RSM  # noqa: N806
    RAM = _RAM  # noqa: N806
    UDT = _UDT  # noqa: N806

    ET.register_namespace("rsm", RSM)
    ET.register_namespace("ram", RAM)
    ET.register_namespace("udt", UDT)

    root = ET.Element(f"{{{RSM}}}CrossIndustryInvoice")

    # 1. ExchangedDocumentContext
    ctx = ET.SubElement(root, f"{{{RSM}}}ExchangedDocumentContext")
    gl = ET.SubElement(ctx, f"{{{RAM}}}GuidelineSpecifiedDocumentContextParameter")
    ET.SubElement(gl, f"{{{RAM}}}ID").text = "urn:factur-x.eu:1p0:minimum"

    # 2. ExchangedDocument
    exdoc = ET.SubElement(root, f"{{{RSM}}}ExchangedDocument")
    ET.SubElement(exdoc, f"{{{RAM}}}ID").text = doc.name
    ET.SubElement(exdoc, f"{{{RAM}}}TypeCode").text = "380"
    date_node = ET.SubElement(exdoc, f"{{{RAM}}}IssueDateTime")
    dts = ET.SubElement(date_node, f"{{{UDT}}}DateTimeString", {"format": "102"})
    dts.text = str(doc.posting_date or frappe.utils.today()).replace("-", "")

    # 3. SupplyChainTradeTransaction
    sctt = ET.SubElement(root, f"{{{RSM}}}SupplyChainTradeTransaction")
    header = ET.SubElement(sctt, f"{{{RAM}}}ApplicableHeaderTradeAgreement")

    # Seller
    seller = ET.SubElement(header, f"{{{RAM}}}SellerTradeParty")
    company = frappe.get_doc("Company", doc.company)
    ET.SubElement(seller, f"{{{RAM}}}Name").text = doc.company
    seller_tax = ET.SubElement(seller, f"{{{RAM}}}SpecifiedTaxRegistration")
    siret_id = ET.SubElement(seller_tax, f"{{{RAM}}}ID", {"schemeID": "0002"})
    reg = getattr(company, "registration_details", "") or ""
    siret = _extract_siret(reg) or "00000000000000"
    siret_id.text = siret
    if getattr(company, "tax_id", None):
        vat_reg = ET.SubElement(seller, f"{{{RAM}}}SpecifiedTaxRegistration")
        ET.SubElement(vat_reg, f"{{{RAM}}}ID", {"schemeID": "VA"}).text = company.tax_id

    # Buyer
    buyer = ET.SubElement(header, f"{{{RAM}}}BuyerTradeParty")
    ET.SubElement(buyer, f"{{{RAM}}}Name").text = doc.customer

    # Delivery
    delivery = ET.SubElement(sctt, f"{{{RAM}}}ApplicableHeaderTradeDelivery")
    ET.SubElement(delivery, f"{{{RAM}}}ActualDeliverySupplyChainEvent")

    # Settlement
    settlement = ET.SubElement(sctt, f"{{{RAM}}}ApplicableHeaderTradeSettlement")
    ET.SubElement(settlement, f"{{{RAM}}}InvoiceCurrencyCode").text = doc.currency or "EUR"

    monetary = ET.SubElement(
        settlement, f"{{{RAM}}}SpecifiedTradeSettlementHeaderMonetarySummation"
    )
    ET.SubElement(
        monetary, f"{{{RAM}}}TaxBasisTotalAmount", {"currencyID": doc.currency or "EUR"}
    ).text = str(round(float(doc.net_total or 0), 2))
    tax_total = ET.SubElement(
        monetary, f"{{{RAM}}}TaxTotalAmount", {"currencyID": doc.currency or "EUR"}
    )
    tax_total.text = str(round(float(doc.total_taxes_and_charges or 0), 2))
    ET.SubElement(
        monetary, f"{{{RAM}}}GrandTotalAmount", {"currencyID": doc.currency or "EUR"}
    ).text = str(round(float(doc.grand_total or 0), 2))
    ET.SubElement(
        monetary, f"{{{RAM}}}DuePayableAmount", {"currencyID": doc.currency or "EUR"}
    ).text = str(round(float(doc.outstanding_amount or doc.grand_total or 0), 2))

    raw = ET.tostring(root, encoding="unicode")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="UTF-8")
    return pretty


def _get_invoice_pdf(doc):
    try:
        from frappe.utils.pdf import get_pdf

        html = frappe.get_print(doc.doctype, doc.name, as_pdf=False)
        return get_pdf(html)
    except Exception:
        return None


def _extract_siret(registration_details):
    import re

    m = re.search(r"SIRET[:\s]+(\d{14})", registration_details)
    return m.group(1) if m else None

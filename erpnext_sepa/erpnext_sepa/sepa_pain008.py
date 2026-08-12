"""
SEPA PAIN.008 XML generator (ISO 20022 — Core Direct Debit).

Generates a syntactically valid PAIN.008.001.02 batch file ready to
transmit to a bank. One file per monthly run; one <DrctDbtTxInf> per
invoice/mandate pair.

Usage:
    invoices = [
        {
            "invoice_name": "ACC-SINV-2026-00001",
            "amount": 1695.0,          # EUR
            "currency": "EUR",
            "customer_name": "Cabinet Dupont",
            "iban": "FR7630006000011234567890189",
            "bic": "BNPAFRPPXXX",
            "mandate_id": "MD000026",
            "mandate_date": "2026-01-01",  # date mandate was signed
            "due_date": "2026-02-01",
        }
    ]
    xml_bytes = build_pain008(invoices, creditor_name="Ktayl Solutions",
                              creditor_iban="FR7630006000019876543210189",
                              creditor_bic="BNPAFRPPXXX",
                              creditor_id="FR72ZZZ123456")
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from typing import Any


_NS = "urn:iso:std:iso:20022:tech:xsd:pain.008.001.02"


def build_pain008(
    invoices: list[dict[str, Any]],
    creditor_name: str,
    creditor_iban: str,
    creditor_bic: str,
    creditor_id: str,
    creation_dt: datetime | None = None,
) -> bytes:
    """Return a PAIN.008 XML document as UTF-8 bytes."""
    if creation_dt is None:
        creation_dt = datetime.utcnow()

    msg_id = _msg_id(creation_dt)
    total_amount = sum(float(inv.get("amount", 0)) for inv in invoices)
    nb_of_txs = len(invoices)

    lines: list[str] = []
    lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    lines.append(f'<Document xmlns="{_NS}">')
    lines.append("  <CstmrDrctDbtInitn>")

    # Group Header
    lines.append("    <GrpHdr>")
    lines.append(f"      <MsgId>{_esc(msg_id)}</MsgId>")
    lines.append(f"      <CreDtTm>{creation_dt.strftime('%Y-%m-%dT%H:%M:%S')}</CreDtTm>")
    lines.append(f"      <NbOfTxs>{nb_of_txs}</NbOfTxs>")
    lines.append(f"      <CtrlSum>{total_amount:.2f}</CtrlSum>")
    lines.append("      <InitgPty>")
    lines.append(f"        <Nm>{_esc(creditor_name)}</Nm>")
    lines.append("      </InitgPty>")
    lines.append("    </GrpHdr>")

    # One Payment Information block (batch — all same due date)
    if invoices:
        due_date = invoices[0].get("due_date", date.today().isoformat())
        pmt_inf_id = f"PMT-{msg_id}"
        lines.append("    <PmtInf>")
        lines.append(f"      <PmtInfId>{_esc(pmt_inf_id)}</PmtInfId>")
        lines.append("      <PmtMtd>DD</PmtMtd>")
        lines.append(f"      <NbOfTxs>{nb_of_txs}</NbOfTxs>")
        lines.append(f"      <CtrlSum>{total_amount:.2f}</CtrlSum>")
        lines.append("      <PmtTpInf>")
        lines.append("        <SvcLvl><Cd>SEPA</Cd></SvcLvl>")
        lines.append("        <LclInstrm><Cd>CORE</Cd></LclInstrm>")
        lines.append("        <SeqTp>RCUR</SeqTp>")
        lines.append("      </PmtTpInf>")
        lines.append(f"      <ReqdColltnDt>{due_date}</ReqdColltnDt>")

        # Creditor
        lines.append("      <Cdtr>")
        lines.append(f"        <Nm>{_esc(creditor_name)}</Nm>")
        lines.append("      </Cdtr>")
        lines.append("      <CdtrAcct>")
        lines.append("        <Id><IBAN>" + _esc(creditor_iban) + "</IBAN></Id>")
        lines.append("      </CdtrAcct>")
        lines.append("      <CdtrAgt>")
        lines.append("        <FinInstnId><BIC>" + _esc(creditor_bic) + "</BIC></FinInstnId>")
        lines.append("      </CdtrAgt>")
        lines.append(f"      <CdtrSchmeId><Id><PrvtId><Othr>")
        lines.append(f"        <Id>{_esc(creditor_id)}</Id>")
        lines.append(f"        <SchmeNm><Prtry>SEPA</Prtry></SchmeNm>")
        lines.append(f"      </Othr></PrvtId></Id></CdtrSchmeId>")

        for inv in invoices:
            lines.extend(_tx_block(inv))

        lines.append("    </PmtInf>")

    lines.append("  </CstmrDrctDbtInitn>")
    lines.append("</Document>")

    return "\n".join(lines).encode("utf-8")


def _tx_block(inv: dict[str, Any]) -> list[str]:
    end_to_end = inv.get("invoice_name", str(uuid.uuid4()))
    amount = float(inv.get("amount", 0))
    currency = inv.get("currency", "EUR")
    mandate_id = inv.get("mandate_id", "NOTPROVIDED")
    mandate_date = inv.get("mandate_date", date.today().isoformat())
    debtor_name = inv.get("customer_name", "")
    debtor_iban = inv.get("iban", "")
    debtor_bic = inv.get("bic", "")

    lines = []
    lines.append("      <DrctDbtTxInf>")
    lines.append("        <PmtId>")
    lines.append(f"          <EndToEndId>{_esc(end_to_end)}</EndToEndId>")
    lines.append("        </PmtId>")
    lines.append(f'        <InstdAmt Ccy="{currency}">{amount:.2f}</InstdAmt>')
    lines.append("        <DrctDbtTx>")
    lines.append("          <MndtRltdInf>")
    lines.append(f"            <MndtId>{_esc(mandate_id)}</MndtId>")
    lines.append(f"            <DtOfSgntr>{mandate_date}</DtOfSgntr>")
    lines.append("          </MndtRltdInf>")
    lines.append("        </DrctDbtTx>")
    lines.append("        <DbtrAgt>")
    lines.append("          <FinInstnId><BIC>" + _esc(debtor_bic) + "</BIC></FinInstnId>")
    lines.append("        </DbtrAgt>")
    lines.append("        <Dbtr>")
    lines.append(f"          <Nm>{_esc(debtor_name)}</Nm>")
    lines.append("        </Dbtr>")
    lines.append("        <DbtrAcct>")
    lines.append("          <Id><IBAN>" + _esc(debtor_iban) + "</IBAN></Id>")
    lines.append("        </DbtrAcct>")
    lines.append("        <Purp><Cd>INSU</Cd></Purp>")
    lines.append(f"        <RmtInf><Ustrd>{_esc(end_to_end)}</Ustrd></RmtInf>")
    lines.append("      </DrctDbtTxInf>")
    return lines


def _msg_id(dt: datetime) -> str:
    token = dt.strftime("%Y%m%d%H%M%S")
    suffix = hashlib.sha1(token.encode()).hexdigest()[:6].upper()
    return f"MINICLOUD-{token}-{suffix}"


def _esc(val: str) -> str:
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

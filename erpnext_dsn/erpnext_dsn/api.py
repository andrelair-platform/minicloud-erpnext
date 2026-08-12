"""
Whitelisted Frappe API methods for DSN operations.

Usage:
  POST /api/method/erpnext_dsn.api.generate_monthly_dsn
       ?year=2026&month=1

  POST /api/method/erpnext_dsn.api.submit_monthly_dsn
       ?year=2026&month=1
"""

from __future__ import annotations

import frappe
from frappe.utils.file_manager import save_file

from erpnext_dsn.dsn_generator import build_dsn
from erpnext_dsn.dsn_submitter import submit_dsn

# ---------------------------------------------------------------------------
# Public API methods
# ---------------------------------------------------------------------------


@frappe.whitelist()
def generate_monthly_dsn(year: int, month: int) -> dict:
    """
    Collect all submitted Salary Slips for the given month, generate a DSN
    phase 3.1 file, attach it to the first Payroll Entry found, and return
    the filename + any validation warnings.
    """
    year, month = int(year), int(month)
    slips = _collect_slips(year, month)
    if not slips:
        frappe.throw(f"Aucun bulletin de salaire soumis pour {month:02d}/{year}.")

    filename = f"DSN-{year}-{month:02d}-mensuelle.dsn"
    dsn_bytes = build_dsn(year, month, slips)

    # Attach to Payroll Entry if one exists; otherwise to the first Salary Slip.
    anchor_doctype, anchor_name = _find_anchor(year, month)
    save_file(filename, dsn_bytes, anchor_doctype, anchor_name, is_private=1)

    return {
        "filename": filename,
        "employees": len(slips),
        "anchor": f"{anchor_doctype} — {anchor_name}",
        "warnings": _collect_warnings(slips),
    }


@frappe.whitelist()
def submit_monthly_dsn(year: int, month: int) -> dict:
    """
    Generate and immediately submit the DSN to Net-Entreprises.
    Stores the submission result as a note on the anchor document.
    """
    year, month = int(year), int(month)
    slips = _collect_slips(year, month)
    if not slips:
        frappe.throw(f"Aucun bulletin de salaire soumis pour {month:02d}/{year}.")

    filename = f"DSN-{year}-{month:02d}-mensuelle.dsn"
    dsn_bytes = build_dsn(year, month, slips)

    result = submit_dsn(dsn_bytes, filename)

    # Attach the file regardless of submission outcome (for audit trail).
    anchor_doctype, anchor_name = _find_anchor(year, month)
    save_file(filename, dsn_bytes, anchor_doctype, anchor_name, is_private=1)

    # Store submission result as a comment on the anchor doc.
    status = "✅ Acceptée" if result["success"] else "❌ Rejetée"
    frappe.get_doc(
        {
            "doctype": "Comment",
            "comment_type": "Comment",
            "reference_doctype": anchor_doctype,
            "reference_name": anchor_name,
            "content": (
                f"<b>DSN {month:02d}/{year} — {status}</b><br>"
                f"Endpoint: {result['endpoint']}<br>"
                f"HTTP: {result['status_code']}<br>"
                f"Soumis le: {result['submitted_at']}<br>"
                f"<pre>{result['response_body'][:1024]}</pre>"
            ),
        }
    ).insert(ignore_permissions=True)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_slips(year: int, month: int) -> list[dict]:
    """Return DSN-ready dicts for all submitted Salary Slips in the given month."""
    from calendar import monthrange

    last_day = monthrange(year, month)[1]
    start = f"{year}-{month:02d}-01"
    end = f"{year}-{month:02d}-{last_day}"

    slip_names = frappe.db.get_all(
        "Salary Slip",
        filters={"docstatus": 1, "start_date": [">=", start], "end_date": ["<=", end]},
        pluck="name",
    )
    return [_slip_to_dict(n) for n in slip_names]


def _slip_to_dict(slip_name: str) -> dict:
    """Map a Salary Slip to the flat dict expected by dsn_generator.build_dsn()."""
    slip = frappe.get_doc("Salary Slip", slip_name)
    emp = frappe.get_doc("Employee", slip.employee)

    return {
        "slip_name": slip_name,
        "employee_id": emp.name,
        "last_name": (emp.last_name or emp.employee_name or "").upper(),
        "first_name": emp.first_name or "",
        "nir": getattr(emp, "custom_nir", "") or "",
        "date_of_birth": str(emp.date_of_birth or ""),
        "birth_department": getattr(emp, "custom_birth_department", "75") or "75",
        "birth_city": (getattr(emp, "custom_birth_city", "") or "PARIS").upper(),
        "birth_country_code": getattr(emp, "custom_birth_country_code", "100") or "100",
        "date_of_joining": str(emp.date_of_joining or ""),
        "contract_type_code": _contract_type_code(emp.employment_type or ""),
        "professional_status_code": getattr(emp, "custom_professional_status_code", "229") or "229",
        "gross_pay": slip.gross_pay or 0,
        "net_pay": slip.net_pay or 0,
        "payment_days": slip.payment_days or 151.67,
    }


def _contract_type_code(employment_type: str) -> str:
    # Map ERPNext employment_type free-text to DSN contract nature code.
    mapping = {
        "Temps plein": "01",  # CDI temps plein
        "CDI": "01",
        "CDD": "02",
        "Alternance": "29",  # contrat d'apprentissage
        "Stage": "29",
    }
    return mapping.get(employment_type, "01")


def _collect_warnings(slips: list[dict]) -> list[str]:
    warnings = []
    for s in slips:
        if not s.get("nir"):
            warnings.append(f"{s['employee_id']}: NIR manquant — déclaration incomplète")
        if not s.get("date_of_birth"):
            warnings.append(f"{s['employee_id']}: Date de naissance manquante")
    return warnings


def _find_anchor(year: int, month: int) -> tuple[str, str]:
    """Find the Payroll Entry for the period, or fall back to the first Salary Slip."""
    from calendar import monthrange

    last_day = monthrange(year, month)[1]
    pe = frappe.db.get_value(
        "Payroll Entry",
        {
            "docstatus": 1,
            "start_date": [">=", f"{year}-{month:02d}-01"],
            "end_date": ["<=", f"{year}-{month:02d}-{last_day}"],
        },
        "name",
    )
    if pe:
        return "Payroll Entry", pe

    slips = frappe.db.get_all(
        "Salary Slip",
        filters={"docstatus": 1, "start_date": [">=", f"{year}-{month:02d}-01"]},
        pluck="name",
        limit=1,
    )
    return ("Salary Slip", slips[0]) if slips else ("Salary Slip", "unknown")

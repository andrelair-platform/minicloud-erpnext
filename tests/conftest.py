"""
Global test configuration.

frappe is not installed in the unit-test environment — it only exists inside
the ERPNext Docker image / bench.  We install a mock of the entire frappe
package into sys.modules BEFORE any test file imports app code, so that
api.py, facturx.py, and salary_hook.py can be imported without a running bench.

The facturx PDF library is also mocked — CII XML generation is tested
independently of the PDF/A-3 embedding step.
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock


def _make_frappe_mock() -> MagicMock:
    m = MagicMock(name="frappe")
    m.utils = MagicMock(name="frappe.utils")
    m.utils.file_manager = MagicMock(name="frappe.utils.file_manager")
    m.utils.today.return_value = "2026-01-31"
    m.utils.pdf = MagicMock(name="frappe.utils.pdf")
    return m


_frappe = _make_frappe_mock()

# Register before any import of app code
for _mod in (
    "frappe",
    "frappe.utils",
    "frappe.utils.file_manager",
    "frappe.utils.pdf",
):
    sys.modules.setdefault(_mod, _frappe)

sys.modules.setdefault("facturx", MagicMock(name="facturx"))


def make_invoice_doc(**kwargs) -> SimpleNamespace:
    """Factory: minimal ERPNext Sales Invoice doc for Factur-X tests."""
    defaults = dict(
        name="ACC-SINV-2026-00001",
        doctype="Sales Invoice",
        company="Ktayl Solutions",
        posting_date="2026-01-31",
        customer="Cabinet Assurance Test",
        currency="EUR",
        net_total=1500.0,
        total_taxes_and_charges=195.0,
        grand_total=1695.0,
        outstanding_amount=1695.0,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def make_company_doc(**kwargs) -> SimpleNamespace:
    """Factory: minimal ERPNext Company doc."""
    defaults = dict(
        name="Ktayl Solutions",
        registration_details="SIRET: 12345678901234",
        tax_id="FR12345678901",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)

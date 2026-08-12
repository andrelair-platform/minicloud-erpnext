"""
Unit tests for pure helper functions in erpnext_dsn.api.

_contract_type_code() and _collect_warnings() contain no Frappe calls —
they are importable after the frappe sys.modules mock in conftest.py.
"""

from erpnext_dsn.api import _collect_warnings, _contract_type_code

from tests.fixtures.employees import JEAN_DUPONT, MISSING_NIR


class TestContractTypeCode:
    def test_cdi(self):
        assert _contract_type_code("CDI") == "01"

    def test_cdd(self):
        assert _contract_type_code("CDD") == "02"

    def test_alternance(self):
        assert _contract_type_code("Alternance") == "29"

    def test_stage(self):
        assert _contract_type_code("Stage") == "29"

    def test_temps_plein(self):
        assert _contract_type_code("Temps plein") == "01"

    def test_unknown_defaults_to_cdi(self):
        """Unknown types fall back to CDI (01) — safe default."""
        assert _contract_type_code("Inconnu") == "01"

    def test_empty_string_defaults_to_cdi(self):
        assert _contract_type_code("") == "01"

    def test_case_sensitive(self):
        """Mapping is case-sensitive — 'cdi' is not a key, returns default '01'."""
        assert _contract_type_code("cdi") == "01"


class TestCollectWarnings:
    def test_complete_slip_no_warnings(self):
        warnings = _collect_warnings([JEAN_DUPONT])
        assert warnings == []

    def test_missing_nir_produces_warning(self):
        warnings = _collect_warnings([MISSING_NIR])
        nir_warnings = [w for w in warnings if "NIR" in w]
        assert len(nir_warnings) == 1

    def test_missing_dob_produces_warning(self):
        warnings = _collect_warnings([MISSING_NIR])
        dob_warnings = [w for w in warnings if "naissance" in w.lower() or "birth" in w.lower()]
        assert len(dob_warnings) == 1

    def test_warning_includes_employee_id(self):
        warnings = _collect_warnings([MISSING_NIR])
        employee_id = MISSING_NIR["employee_id"]
        assert any(employee_id in w for w in warnings)

    def test_multiple_employees_accumulates_warnings(self):
        """Warnings from all employees are collected, not just the first."""
        missing_1 = {**MISSING_NIR, "employee_id": "HR-EMP-10"}
        missing_2 = {**MISSING_NIR, "employee_id": "HR-EMP-11"}
        warnings = _collect_warnings([missing_1, missing_2])
        ids_in_warnings = [w for w in warnings if "HR-EMP-10" in w or "HR-EMP-11" in w]
        assert len(ids_in_warnings) >= 2

    def test_empty_slip_list(self):
        assert _collect_warnings([]) == []

    def test_returns_list(self):
        result = _collect_warnings([JEAN_DUPONT])
        assert isinstance(result, list)

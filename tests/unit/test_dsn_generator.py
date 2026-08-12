"""
Unit tests for erpnext_dsn.dsn_generator.

All tests are pure — no Frappe, no DB, no network.
The generator only uses os.environ and datetime; both are patched where needed.
"""

import os
from unittest.mock import patch

import pytest
from erpnext_dsn.dsn_generator import (
    _amount,
    _date8,
    _dsn_val,
    build_dsn,
)

from tests.fixtures.employees import (
    DARTAGNAN,
    FLOAT_AMOUNTS,
    JEAN_DUPONT,
    MARIE_LECLERC,
    MISSING_NIR,
)

# ---------------------------------------------------------------------------
# Helpers: build decoded lines for easier assertions
# ---------------------------------------------------------------------------


def _lines(slips: list[dict], year: int = 2026, month: int = 1) -> list[str]:
    raw = build_dsn(year, month, slips)
    return raw.decode("utf-8").splitlines()


def _line_value(lines: list[str], rubric: str) -> str | None:
    """Return the value part of a DSN line matching the given rubric prefix."""
    for line in lines:
        if line.startswith(rubric + ":"):
            # Extract value between single quotes
            start = line.index("'") + 1
            end = line.rindex("'")
            return line[start:end]
    return None


# ---------------------------------------------------------------------------
# Output encoding and line endings
# ---------------------------------------------------------------------------


class TestOutputFormat:
    def test_returns_bytes(self):
        result = build_dsn(2026, 1, [JEAN_DUPONT])
        assert isinstance(result, bytes)

    def test_crlf_line_endings(self):
        """DSN spec requires CRLF (\\r\\n) — GIP-MDS Cahier Technique §3."""
        raw = build_dsn(2026, 1, [JEAN_DUPONT])
        assert b"\r\n" in raw

    def test_no_bare_lf(self):
        """No bare LF — every newline must be preceded by CR."""
        raw = build_dsn(2026, 1, [JEAN_DUPONT])
        text = raw.decode("utf-8")
        lines = text.split("\r\n")
        for line in lines:
            assert "\n" not in line, f"Bare LF found in: {line!r}"

    def test_utf8_decodable(self):
        raw = build_dsn(2026, 1, [JEAN_DUPONT])
        decoded = raw.decode("utf-8")
        assert len(decoded) > 0


# ---------------------------------------------------------------------------
# S10 — File header
# ---------------------------------------------------------------------------


class TestS10Header:
    def test_version_norme(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.001") == "06.1"

    def test_nature_mensuelle(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.002") == "01"

    def test_period_format(self):
        """Period must be YYYY-MM."""
        lines = _lines([JEAN_DUPONT], year=2026, month=3)
        assert _line_value(lines, "S10.G00.00.008") == "2026-03"

    def test_period_zero_padded_month(self):
        lines = _lines([JEAN_DUPONT], year=2026, month=1)
        assert _line_value(lines, "S10.G00.00.008") == "2026-01"

    def test_test_indicator_default(self):
        """Default DSN_TEST_MODE=true → indicator '01' (qualification)."""
        with patch.dict(os.environ, {"DSN_TEST_MODE": "true"}):
            lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.015") == "01"

    def test_production_indicator(self):
        """DSN_TEST_MODE=false → indicator '02' (production)."""
        with patch.dict(os.environ, {"DSN_TEST_MODE": "false"}):
            lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.015") == "02"

    def test_company_name_from_env(self):
        with patch.dict(os.environ, {"DSN_COMPANY_NAME": "MON ENTREPRISE SAS"}):
            lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.003") == "MON ENTREPRISE SAS"

    def test_siret_from_env(self):
        with patch.dict(os.environ, {"DSN_SIRET": "12345678901234"}):
            lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.005") == "12345678901234"

    def test_siret_default_when_unset(self):
        env = {k: v for k, v in os.environ.items() if k != "DSN_SIRET"}
        with patch.dict(os.environ, env, clear=True):
            lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.005") == "00000000000000"

    def test_version_cahier_technique(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.017") == "06.1"

    def test_type_declarant(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.006") == "01"

    def test_premier_envoi(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.00.012") == "01"


# ---------------------------------------------------------------------------
# S10 — Emitter
# ---------------------------------------------------------------------------


class TestS10Emitter:
    def test_type_emetteur(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.01.006") == "10"

    def test_siret_emetteur_matches_declarant(self):
        with patch.dict(os.environ, {"DSN_SIRET": "99887766554433"}):
            lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S10.G00.01.007") == "99887766554433"


# ---------------------------------------------------------------------------
# S20.G00.05 — Identification individu
# ---------------------------------------------------------------------------


class TestS20Individu:
    def test_nir_present(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.05.001") == "182017505603712"

    def test_last_name(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.05.002") == "DUPONT"

    def test_first_name(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.05.003") == "Jean"

    def test_date_of_birth_format(self):
        """Date of birth must be YYYYMMDD (no hyphens)."""
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.05.004") == "19820115"

    def test_birth_department(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.05.005") == "75"

    def test_birth_city(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.05.006") == "PARIS"

    def test_birth_country_code(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.05.007") == "100"

    def test_missing_nir_produces_empty_value(self):
        lines = _lines([MISSING_NIR])
        assert _line_value(lines, "S20.G00.05.001") == ""

    def test_missing_dob_produces_empty_value(self):
        lines = _lines([MISSING_NIR])
        assert _line_value(lines, "S20.G00.05.004") == ""


# ---------------------------------------------------------------------------
# S20.G00.07 — Contrat de travail
# ---------------------------------------------------------------------------


class TestS20Contrat:
    def test_contract_number(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.07.001") == "HR-EMP-00003"

    def test_contract_start_date_format(self):
        """Contract start date must be YYYYMMDD."""
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.07.002") == "20230102"

    def test_contract_type_cdi(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.07.006") == "01"

    def test_contract_type_cdd(self):
        lines = _lines([MARIE_LECLERC])
        assert _line_value(lines, "S20.G00.07.006") == "02"

    def test_professional_status(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.07.011") == "229"


# ---------------------------------------------------------------------------
# S20.G00.51 — Rémunération
# ---------------------------------------------------------------------------


class TestS20Remuneration:
    def test_remuneration_type(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.51.001") == "014"

    def test_payment_hours(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.51.002") == "151.67"

    def test_gross_pay(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.51.003") == "3500.0"

    def test_net_pay(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S20.G00.51.011") == "3097.5"

    def test_float_amounts_rounded(self):
        """Amounts must be rounded to 2 decimal places."""
        lines = _lines([FLOAT_AMOUNTS])
        gross = _line_value(lines, "S20.G00.51.003")
        net = _line_value(lines, "S20.G00.51.011")
        assert gross is not None and float(gross) == pytest.approx(3501.0, abs=0.01)
        assert net is not None and float(net) == pytest.approx(3097.0, abs=0.01)


# ---------------------------------------------------------------------------
# S90 — Footer
# ---------------------------------------------------------------------------


class TestS90Footer:
    def test_one_employee_count(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S90.G00.90.001") == "1"

    def test_two_employees_count(self):
        lines = _lines([JEAN_DUPONT, MARIE_LECLERC])
        assert _line_value(lines, "S90.G00.90.001") == "2"

    def test_declarations_count(self):
        lines = _lines([JEAN_DUPONT])
        assert _line_value(lines, "S90.G00.90.002") == "1"


# ---------------------------------------------------------------------------
# Multiple employees
# ---------------------------------------------------------------------------


class TestMultipleEmployees:
    def test_two_employees_both_nir_present(self):
        raw = build_dsn(2026, 1, [JEAN_DUPONT, MARIE_LECLERC])
        text = raw.decode("utf-8")
        assert "182017505603712" in text
        assert "278056912345678" in text

    def test_two_employees_both_names_present(self):
        raw = build_dsn(2026, 1, [JEAN_DUPONT, MARIE_LECLERC])
        text = raw.decode("utf-8")
        assert "DUPONT" in text
        assert "LECLERC" in text

    def test_zero_employees_still_valid(self):
        """Empty slip list — footer count = 0, no crash."""
        lines = _lines([])
        assert _line_value(lines, "S90.G00.90.001") == "0"


# ---------------------------------------------------------------------------
# DSN value escaping
# ---------------------------------------------------------------------------


class TestDsnValEscaping:
    def test_quote_in_name_is_escaped(self):
        """Single quotes in values must be escaped with backslash."""
        raw = build_dsn(2026, 1, [DARTAGNAN])
        text = raw.decode("utf-8")
        assert "D\\'ARTAGNAN" in text

    def test_dsn_val_helper_escapes_quote(self):
        assert _dsn_val("O'Brien") == "O\\'Brien"

    def test_dsn_val_no_quotes_unchanged(self):
        assert _dsn_val("DUPONT") == "DUPONT"


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------


class TestDate8:
    def test_standard_date(self):
        assert _date8("1982-01-15") == "19820115"

    def test_empty_string(self):
        assert _date8("") == ""

    def test_none_like(self):
        assert _date8(None) == ""  # type: ignore[arg-type]


class TestAmount:
    def test_float(self):
        assert _amount(3500.0) == "3500.0"

    def test_integer(self):
        # round(float(2800), 2) → 2800.0 — consistent with float output
        assert _amount(2800) == "2800.0"

    def test_rounding(self):
        assert _amount(3500.999) == "3501.0"

    def test_zero(self):
        assert _amount(0) == "0.0"

    def test_none_returns_zero(self):
        assert _amount(None) == "0.00"  # type: ignore[arg-type]

    def test_non_numeric_returns_zero(self):
        assert _amount("invalid") == "0.00"

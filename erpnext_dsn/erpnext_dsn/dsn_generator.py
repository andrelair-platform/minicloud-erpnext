"""
DSN phase 3.1 (norme 06.1) monthly declaration generator.

Spec: GIP-MDS Cahier Technique DSN phase 3.1 — https://www.dsn-info.fr/
Block notation: S<section>.G<group>.<rubric>.<instance>:'<value>'
Line ending: CRLF (required by GIP-MDS spec).

Only mandatory blocks for a mensuelle (type '01') with one employee are generated.
Rubric references are taken from the GIP-MDS cahier technique phase 3.1 rev. 2024.
"""

from __future__ import annotations

import os
from datetime import date

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def build_dsn(period_year: int, period_month: int, slips: list[dict]) -> bytes:
    """
    Generate a DSN phase 3.1 monthly declaration.

    slips: list of dicts with keys from _slip_to_dict().
    Returns UTF-8 encoded bytes with CRLF line endings.
    """
    lines: list[str] = []
    lines += _header(period_year, period_month)
    lines += _emitter()
    for slip in slips:
        lines += _individual_blocks(slip, period_year, period_month)
    lines += _footer(len(slips))
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Settings (from environment — injected via k8s Secret + ESO from Vault)
# ---------------------------------------------------------------------------


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _siret() -> str:
    return _cfg("DSN_SIRET", "00000000000000")


def _company_name() -> str:
    return _cfg("DSN_COMPANY_NAME", "KTAYL SOLUTION SAS")


def _test_indicator() -> str:
    # '01' = qualification / test  |  '02' = production
    return "01" if _cfg("DSN_TEST_MODE", "true").lower() in ("true", "1", "yes") else "02"


# ---------------------------------------------------------------------------
# S10 — Envoi (file header + emitter)
# Spec: GIP-MDS §4.1
# ---------------------------------------------------------------------------


def _header(year: int, month: int) -> list[str]:
    today = date.today().strftime("%Y%m%d")
    period = f"{year:04d}-{month:02d}"
    return [
        f"S10.G00.00.001:'{_dsn_val('06.1')}'",  # Version norme
        f"S10.G00.00.002:'{_dsn_val('01')}'",  # Nature: 01=mensuelle
        f"S10.G00.00.003:'{_dsn_val(_company_name())}'",  # Raison sociale
        f"S10.G00.00.005:'{_dsn_val(_siret())}'",  # SIRET déclarant
        f"S10.G00.00.006:'{_dsn_val('01')}'",  # Type déclarant: 01=employeur
        f"S10.G00.00.008:'{_dsn_val(period)}'",  # Période objet (YYYY-MM)
        f"S10.G00.00.009:'{_dsn_val(today)}'",  # Date d'envoi (YYYYMMDD)
        f"S10.G00.00.012:'{_dsn_val('01')}'",  # Rang: 01=premier envoi
        f"S10.G00.00.015:'{_dsn_val(_test_indicator())}'",  # Indicateur test
        f"S10.G00.00.017:'{_dsn_val('06.1')}'",  # Version cahier technique
    ]


def _emitter() -> list[str]:
    return [
        f"S10.G00.01.006:'{_dsn_val('10')}'",  # Type émetteur: 10=employeur lui-même
        f"S10.G00.01.007:'{_dsn_val(_siret())}'",  # SIRET émetteur
        f"S10.G00.01.008:'{_dsn_val(_company_name())}'",  # Raison sociale émetteur
    ]


# ---------------------------------------------------------------------------
# S20 — Individu (one block set per employee per period)
# ---------------------------------------------------------------------------


def _individual_blocks(slip: dict, year: int, month: int) -> list[str]:
    lines: list[str] = []
    lines += _s20_g00_05(slip)  # Identification individu
    lines += _s20_g00_07(slip)  # Contrat de travail
    lines += _s20_g00_51(slip)  # Rémunération
    return lines


def _s20_g00_05(slip: dict) -> list[str]:
    """Bloc S20.G00.05 — Identification individu (GIP-MDS §5.1)"""
    nir = slip.get("nir", "").replace(" ", "")
    dob = _date8(slip.get("date_of_birth", ""))
    dept_naissance = slip.get("birth_department", "75")
    commune_naissance = slip.get("birth_city", "PARIS")
    pays_naissance = slip.get("birth_country_code", "100")  # 100 = France

    return [
        f"S20.G00.05.001:'{_dsn_val(nir)}'",  # NIR individu (13+2 key)
        f"S20.G00.05.002:'{_dsn_val(slip.get('last_name', ''))}'",  # Nom de famille
        f"S20.G00.05.003:'{_dsn_val(slip.get('first_name', ''))}'",  # Prénom
        f"S20.G00.05.004:'{_dsn_val(dob)}'",  # Date de naissance (YYYYMMDD)
        f"S20.G00.05.005:'{_dsn_val(dept_naissance)}'",  # Département de naissance
        f"S20.G00.05.006:'{_dsn_val(commune_naissance)}'",  # Commune de naissance
        f"S20.G00.05.007:'{_dsn_val(pays_naissance)}'",  # Code pays de naissance
    ]


def _s20_g00_07(slip: dict) -> list[str]:
    """Bloc S20.G00.07 — Contrat de travail (GIP-MDS §5.3)"""
    contract_start = _date8(slip.get("date_of_joining", ""))
    contract_type = slip.get("contract_type_code", "01")  # 01=CDI
    professional_status = slip.get("professional_status_code", "229")  # 229=employé

    return [
        f"S20.G00.07.001:'{_dsn_val(slip.get('employee_id', ''))}'",  # Numéro contrat
        f"S20.G00.07.002:'{_dsn_val(contract_start)}'",  # Date début contrat
        f"S20.G00.07.006:'{_dsn_val(contract_type)}'",  # Nature contrat
        f"S20.G00.07.011:'{_dsn_val(professional_status)}'",  # Statut professionnel
    ]


def _s20_g00_51(slip: dict) -> list[str]:
    """Bloc S20.G00.51 — Rémunération (GIP-MDS §5.7)"""
    gross = _amount(slip.get("gross_pay", 0))
    net_to_pay = _amount(slip.get("net_pay", 0))
    hours = slip.get("payment_days", 151.67)  # heures pour un temps plein mensuel

    return [
        f"S20.G00.51.001:'{_dsn_val('014')}'",  # Type: 014=salaire brut soumis cotisations
        f"S20.G00.51.002:'{_dsn_val(str(round(float(hours), 2)))}'",  # Nb heures
        f"S20.G00.51.003:'{_dsn_val(gross)}'",  # Montant brut
        f"S20.G00.51.011:'{_dsn_val(net_to_pay)}'",  # Montant net à payer
    ]


# ---------------------------------------------------------------------------
# S90 — Fin de fichier
# ---------------------------------------------------------------------------


def _footer(n_individuals: int) -> list[str]:
    return [
        f"S90.G00.90.001:'{_dsn_val(str(n_individuals))}'",  # Nombre d'individus
        f"S90.G00.90.002:'{_dsn_val('1')}'",  # Nombre de déclarations
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dsn_val(v: str) -> str:
    """Escape single quotes in DSN values."""
    return v.replace("'", "\\'")


def _date8(d: str) -> str:
    """Convert YYYY-MM-DD or date object to YYYYMMDD."""
    if not d:
        return ""
    return str(d).replace("-", "")[:8]


def _amount(v) -> str:
    try:
        return str(round(float(v), 2))
    except (TypeError, ValueError):
        return "0.00"

"""
Net-Entreprises DSN submission.

Qualification endpoint: https://qualif01.net-entreprises.fr
Production endpoint:    https://www.net-entreprises.fr

Authentication: login + password obtained at registration.
Protocol: HTTPS multipart/form-data POST (as documented in Net-Entreprises
          technical guide "Dépôt DSN via web service").

Credentials are read from environment variables injected by k8s Secret
erpnext-dsn-config (fed by ESO from Vault secret/platform/net-entreprises).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

_TIMEOUT_S = 60


def submit_dsn(dsn_bytes: bytes, filename: str) -> dict:
    """
    POST the DSN file to Net-Entreprises.

    Returns a dict:
        {
            "success": bool,
            "status_code": int,
            "response_body": str,
            "submitted_at": "ISO8601",
            "endpoint": str,
        }
    """
    login = os.environ.get("DSN_LOGIN", "")
    password = os.environ.get("DSN_PASSWORD", "")
    # Endpoint is provided by Net-Entreprises after account creation (Cahier Technique
    # de Raccordement). Set DSN_ENDPOINT in Vault secret/platform/net-entreprises.
    endpoint = os.environ.get("DSN_ENDPOINT", "")

    if not endpoint:
        raise RuntimeError(
            "DSN_ENDPOINT not set. Obtain the qualification URL from the "
            "Net-Entreprises Cahier Technique de Raccordement after account creation, "
            "then: vault kv patch secret/platform/net-entreprises endpoint=<url>"
        )

    files = {
        "fichier": (filename, dsn_bytes, "text/plain"),
    }
    data = {
        "login": login,
        "mdp": password,
    }

    try:
        resp = requests.post(
            endpoint,
            files=files,
            data=data,
            timeout=_TIMEOUT_S,
            verify=True,
        )
    except requests.exceptions.Timeout:
        logger.error("DSN submission timeout after %ds to %s", _TIMEOUT_S, endpoint)
        raise
    except requests.exceptions.ConnectionError as exc:
        logger.error("DSN submission connection error: %s", exc)
        raise

    submitted_at = datetime.utcnow().isoformat() + "Z"
    result = {
        "success": resp.status_code == 200 and _response_is_ok(resp.text),
        "status_code": resp.status_code,
        "response_body": resp.text[:4096],  # truncate for storage
        "submitted_at": submitted_at,
        "endpoint": endpoint,
    }

    if result["success"]:
        logger.info("DSN submitted successfully at %s (HTTP %d)", submitted_at, resp.status_code)
    else:
        logger.warning(
            "DSN submission returned HTTP %d. Body: %s",
            resp.status_code,
            resp.text[:512],
        )

    return result


def _response_is_ok(body: str) -> bool:
    """
    Parse CRM (Compte Rendu Métier) XML returned by Net-Entreprises.

    ACCEPTE  + codeRetour 00 → True
    REJETE   or codeRetour ≠ 00 → False
    Non-XML fallback: check for SOAP fault indicators.
    """
    import xml.etree.ElementTree as ET

    try:
        root = ET.fromstring(body.strip())
        ns = {"crm": "urn:net-entreprises:crm:1.0"}
        etat = root.findtext("crm:etatTraitement", default="", namespaces=ns)
        code = root.findtext("crm:codeRetour", default="", namespaces=ns)
        if etat.upper() == "ACCEPTE" and code == "00":
            return True
        return False
    except ET.ParseError:
        # Not XML — fall back to SOAP fault check only
        body_lower = body.lower()
        if any(k in body_lower for k in ("<fault", "faultcode", "faultstring")):
            return False
        return True

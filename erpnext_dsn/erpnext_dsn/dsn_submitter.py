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

import os
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)

# Net-Entreprises deposit endpoints
_ENDPOINTS = {
    "qualification": "https://qualif01.net-entreprises.fr/srm/service/dsn-api/depot",
    "production": "https://www.net-entreprises.fr/srm/service/dsn-api/depot",
}

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
    test_mode = os.environ.get("DSN_TEST_MODE", "true").lower() in ("true", "1", "yes")
    endpoint = _ENDPOINTS["qualification"] if test_mode else _ENDPOINTS["production"]

    if not login or not password:
        raise RuntimeError(
            "DSN_LOGIN / DSN_PASSWORD environment variables not set. "
            "Add credentials to Vault secret/platform/net-entreprises."
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
    Net-Entreprises returns an XML or JSON body indicating acceptance or rejection.
    A '200' HTTP status alone is not sufficient — the body must not contain error codes.

    Adjust this parser once the real qualification response format is confirmed
    from the Net-Entreprises technical documentation (available after account creation).
    """
    body_lower = body.lower()
    # Common error indicators in Net-Entreprises DSN API responses
    if any(k in body_lower for k in ("erreur", "error", "rejet", "ko", "<fault")):
        return False
    return True

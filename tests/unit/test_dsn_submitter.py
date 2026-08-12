"""
Unit tests for erpnext_dsn.dsn_submitter.

_response_is_ok() is a pure function tested without mocking.
submit_dsn() is tested with unittest.mock.patch on requests.post.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from erpnext_dsn.dsn_submitter import _response_is_ok, submit_dsn
from tests.fixtures.crm_responses import (
    ACCEPTE,
    ACCEPTE_NONZERO_CODE,
    EMPTY,
    PLAIN_OK,
    REJETE,
    SOAP_FAULT,
    TRAITEMENT_SANS_ERREUR,
)


class TestResponseIsOkAccepted:
    def test_accepte_coderetour_00_returns_true(self):
        assert _response_is_ok(ACCEPTE) is True

    def test_traitement_sans_erreur_returns_true(self):
        """
        Regression: 'Traitement sans erreur' contains the substring 'erreur'.
        The old keyword-based check returned False on successful responses.
        The XML parser correctly returns True for ACCEPTE + code 00.
        """
        assert _response_is_ok(TRAITEMENT_SANS_ERREUR) is True

    def test_leading_whitespace_tolerated(self):
        """Real Net-Entreprises responses sometimes have leading whitespace."""
        assert _response_is_ok("  \n" + ACCEPTE) is True


class TestResponseIsOkRejected:
    def test_rejete_returns_false(self):
        assert _response_is_ok(REJETE) is False

    def test_accepte_nonzero_coderetour_returns_false(self):
        """etatTraitement=ACCEPTE but codeRetour != 00 is not a clean accept."""
        assert _response_is_ok(ACCEPTE_NONZERO_CODE) is False

    def test_soap_fault_returns_false(self):
        """SOAP faults are not CRM XML — fallback path must detect <fault>."""
        assert _response_is_ok(SOAP_FAULT) is False

    def test_faultcode_keyword_returns_false(self):
        assert _response_is_ok("<faultcode>Server</faultcode>") is False

    def test_faultstring_keyword_returns_false(self):
        assert _response_is_ok("<faultstring>error</faultstring>") is False


class TestResponseIsOkEdgeCases:
    def test_empty_body_returns_true(self):
        """
        Empty response: no XML parse possible, no fault keywords found.
        Fallback treats it as a pass (connection succeeded, no error signals).
        """
        assert _response_is_ok(EMPTY) is True

    def test_plain_text_no_fault_returns_true(self):
        """Plain text with no fault keywords — fallback path returns True."""
        assert _response_is_ok(PLAIN_OK) is True

    def test_case_insensitive_etat_lower(self):
        """etatTraitement is case-insensitive per implementation."""
        xml = ACCEPTE.replace("ACCEPTE", "accepte")
        assert _response_is_ok(xml) is True

    def test_missing_namespace_still_parsed(self):
        """XML without the crm namespace should not crash — falls back to plain text path."""
        bare_xml = """<?xml version="1.0"?>
<compteRenduMetier>
  <etatTraitement>ACCEPTE</etatTraitement>
  <codeRetour>00</codeRetour>
</compteRenduMetier>"""
        # No namespace match → findtext returns '' → returns False
        result = _response_is_ok(bare_xml)
        assert isinstance(result, bool)

    def test_malformed_xml_does_not_raise(self):
        """ParseError must be caught — fallback logic runs instead."""
        malformed = "<not valid xml <<< >>>"
        result = _response_is_ok(malformed)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# submit_dsn() — tested with mocked requests.post
# ---------------------------------------------------------------------------

DSN_BYTES = b"S10.G00.00.001:'06.1'\r\n"
DSN_ENV = {
    "DSN_ENDPOINT": "http://mock-net-entreprises.local/depot",
    "DSN_LOGIN": "testlogin",
    "DSN_PASSWORD": "testpass",
}


def _mock_response(status_code: int, text: str) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    return resp


class TestSubmitDsn:
    def test_successful_submission_returns_success_true(self):
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post") as mock_post:
                mock_post.return_value = _mock_response(200, ACCEPTE)
                result = submit_dsn(DSN_BYTES, "test.dsn")
        assert result["success"] is True

    def test_successful_submission_returns_status_200(self):
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post") as mock_post:
                mock_post.return_value = _mock_response(200, ACCEPTE)
                result = submit_dsn(DSN_BYTES, "test.dsn")
        assert result["status_code"] == 200

    def test_successful_submission_includes_endpoint(self):
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post") as mock_post:
                mock_post.return_value = _mock_response(200, ACCEPTE)
                result = submit_dsn(DSN_BYTES, "test.dsn")
        assert result["endpoint"] == DSN_ENV["DSN_ENDPOINT"]

    def test_rejected_crm_response_returns_success_false(self):
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post") as mock_post:
                mock_post.return_value = _mock_response(200, REJETE)
                result = submit_dsn(DSN_BYTES, "test.dsn")
        assert result["success"] is False

    def test_http_500_returns_success_false(self):
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post") as mock_post:
                mock_post.return_value = _mock_response(500, "Internal Server Error")
                result = submit_dsn(DSN_BYTES, "test.dsn")
        assert result["success"] is False

    def test_result_contains_submitted_at(self):
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post") as mock_post:
                mock_post.return_value = _mock_response(200, ACCEPTE)
                result = submit_dsn(DSN_BYTES, "test.dsn")
        assert "submitted_at" in result
        assert result["submitted_at"].endswith("Z")

    def test_result_contains_response_body(self):
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post") as mock_post:
                mock_post.return_value = _mock_response(200, ACCEPTE)
                result = submit_dsn(DSN_BYTES, "test.dsn")
        assert "response_body" in result

    def test_missing_endpoint_raises_runtime_error(self):
        env = {k: v for k, v in os.environ.items() if k != "DSN_ENDPOINT"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="DSN_ENDPOINT not set"):
                submit_dsn(DSN_BYTES, "test.dsn")

    def test_timeout_propagates(self):
        import requests as req_lib
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post", side_effect=req_lib.exceptions.Timeout):
                with pytest.raises(req_lib.exceptions.Timeout):
                    submit_dsn(DSN_BYTES, "test.dsn")

    def test_connection_error_propagates(self):
        import requests as req_lib
        with patch.dict(os.environ, DSN_ENV):
            with patch("requests.post", side_effect=req_lib.exceptions.ConnectionError):
                with pytest.raises(req_lib.exceptions.ConnectionError):
                    submit_dsn(DSN_BYTES, "test.dsn")

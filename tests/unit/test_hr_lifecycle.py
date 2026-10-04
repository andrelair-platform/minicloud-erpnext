"""
L1 unit tests for erpnext_hr_lifecycle.events — the pure, frappe-free logic:
canonical encoding determinism, HMAC signing, and event assembly/validation.

The NATS/n8n publish paths are I/O and are proven live (L4) against the running dev service, not
mocked here — a mocked NATS would only assert our own call shape (see the testing standard's mock
discipline). These tests lock down the SIGNED CONTRACT consumers depend on.
"""

import hashlib
import hmac
import json

import pytest

from erpnext_hr_lifecycle import events


class TestCanonicalBytes:
    def test_deterministic_regardless_of_key_order(self):
        a = events.canonical_bytes({"b": 1, "a": 2})
        b = events.canonical_bytes({"a": 2, "b": 1})
        assert a == b

    def test_no_whitespace(self):
        out = events.canonical_bytes({"a": 1, "b": 2})
        assert out == b'{"a":1,"b":2}'

    def test_roundtrips_to_same_object(self):
        ev = {"event": "joiner", "subject": {"matricule": "100001"}}
        assert json.loads(events.canonical_bytes(ev)) == ev


class TestSign:
    def test_empty_key_is_unsigned(self):
        assert events.sign(b"anything", "") == ""

    def test_matches_reference_hmac(self):
        body, key = b'{"event":"leaver"}', "s3cr3t"
        expected = hmac.new(key.encode(), body, hashlib.sha256).hexdigest()
        assert events.sign(body, key) == expected

    def test_signature_changes_with_body(self):
        key = "k"
        assert events.sign(b"a", key) != events.sign(b"b", key)

    def test_signature_changes_with_key(self):
        body = b"a"
        assert events.sign(body, "k1") != events.sign(body, "k2")

    def test_verifiable_by_a_consumer(self):
        ev = events.build_event(
            "joiner", {"matricule": "100001"}, occurred_at="2026-10-04T00:00:00+00:00"
        )
        body = events.canonical_bytes(ev)
        sig = events.sign(body, "shared")
        # a consumer recomputes and compares
        assert hmac.compare_digest(sig, events.sign(body, "shared"))


class TestBuildEvent:
    def test_rejects_unknown_event_type(self):
        with pytest.raises(ValueError):
            events.build_event("hired", {"matricule": "x"})

    @pytest.mark.parametrize("etype", ["joiner", "mover", "leaver"])
    def test_accepts_the_three_lifecycle_types(self, etype):
        ev = events.build_event(etype, {"matricule": "100001"})
        assert ev["event"] == etype
        assert ev["schema"] == events.SCHEMA
        assert ev["source"] == "erpnext"
        assert ev["subject"]["matricule"] == "100001"

    def test_effective_date_is_stringified(self):
        ev = events.build_event("leaver", {"matricule": "x"}, effective_date="2026-12-31")
        assert ev["effective_date"] == "2026-12-31"

    def test_effective_date_none_is_null(self):
        ev = events.build_event("joiner", {"matricule": "x"})
        assert ev["effective_date"] is None

    def test_change_block_only_when_provided(self):
        plain = events.build_event("joiner", {"matricule": "x"})
        assert "change" not in plain
        withchange = events.build_event(
            "mover", {"matricule": "x"}, change={"kind": "promotion", "changes": []}
        )
        assert withchange["change"]["kind"] == "promotion"

    def test_occurred_at_defaults_to_iso_utc(self):
        ev = events.build_event("joiner", {"matricule": "x"})
        # ISO-8601 with timezone offset
        assert "T" in ev["occurred_at"] and ("+" in ev["occurred_at"] or "Z" in ev["occurred_at"])

    def test_subject_payload_is_passed_through_verbatim(self):
        subject = {
            "matricule": "100001",
            "job": "Souscripteur",
            "entity": "Ktayl Solutions",
            "country": "France",
            "department": "Souscription - KS",
        }
        ev = events.build_event("mover", subject)
        assert ev["subject"] == subject


class TestSubjectRouting:
    @pytest.mark.parametrize(
        "etype,subject",
        [
            ("joiner", "hr.lifecycle.joiner"),
            ("mover", "hr.lifecycle.mover"),
            ("leaver", "hr.lifecycle.leaver"),
        ],
    )
    def test_subject_prefix_contract(self, etype, subject):
        # the consumers subscribe to hr.lifecycle.> — lock the subject naming
        assert f"{events.SUBJECT_PREFIX}.{etype}" == subject

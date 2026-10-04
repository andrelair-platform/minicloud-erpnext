"""
HR Joiner/Mover/Leaver lifecycle event emission.

The ERPNext (HR) side of the HR#8 ↔ ktayl-iam#17 seam. On the relevant HR doc events it builds a
canonical, signed lifecycle event and publishes it to **two sinks**, both best-effort and run in a
background job so they can NEVER block or roll back the HR transaction:

  1. NATS JetStream stream **HR_LIFECYCLE**, subject ``hr.lifecycle.<joiner|mover|leaver>`` — the
     durable, signed backbone. ktayl-iam v3 adds its own durable consumer here later to react for
     ACCESS (Joiner → workspace birthright, Leaver → revoke, Mover → recompute+recert). ERPNext
     itself NEVER writes Authentik.
  2. The **n8n** webhook — the NON-access fan-out (GLPI software-provisioning task + email). No
     hardware (BYOD). A failure here is logged and swallowed; the HR transaction already committed.

Events are signed with HMAC-SHA256 over the canonical JSON body (``HR_LIFECYCLE_SIGNING_KEY``);
consumers verify the ``HR-Signature`` NATS header / ``X-HR-Signature`` HTTP header. The pure helpers
(:func:`canonical_bytes`, :func:`sign`, :func:`build_event`) carry no frappe/nats dependency so they
are unit-tested directly.

Config (environment, injected via ESO — see minicloud-gitops manifests/erpnext):
  HR_LIFECYCLE_SIGNING_KEY   HMAC secret (required to sign; empty ⇒ unsigned, dev only)
  HR_NATS_URL                default nats://nats.messaging.svc:4222
  HR_LIFECYCLE_STREAM        default HR_LIFECYCLE
  HR_N8N_WEBHOOK_URL         n8n production webhook; empty ⇒ fan-out skipped
"""

# pyright: reportMissingImports=false
from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime

import frappe

SCHEMA = "ktayl.hr.lifecycle/v1"
SUBJECT_PREFIX = "hr.lifecycle"
VALID_EVENTS = {"joiner", "mover", "leaver"}


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# ── pure helpers (no frappe / no nats — unit-tested directly) ─────────────────────────────────


def canonical_bytes(event: dict) -> bytes:
    """Deterministic JSON encoding — sorted keys, no whitespace — so the signature is stable."""
    return json.dumps(event, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign(body: bytes, key: str) -> str:
    """HMAC-SHA256 hex digest of the canonical body (empty string if no key — dev/unsigned)."""
    if not key:
        return ""
    return hmac.new(key.encode("utf-8"), body, hashlib.sha256).hexdigest()


def build_event(
    event_type: str,
    subject: dict,
    *,
    effective_date=None,
    change=None,
    occurred_at: str | None = None,
) -> dict:
    """Assemble the canonical lifecycle event. ``subject`` is the JML identity payload."""
    if event_type not in VALID_EVENTS:
        raise ValueError(f"unknown lifecycle event type: {event_type!r}")
    ev = {
        "schema": SCHEMA,
        "event": event_type,
        "occurred_at": occurred_at or datetime.now(UTC).isoformat(),
        "effective_date": str(effective_date) if effective_date else None,
        "source": "erpnext",
        "subject": subject,
    }
    if change:
        ev["change"] = change
    return ev


# ── frappe-side plumbing ──────────────────────────────────────────────────────────────────────


def _subject_payload(employee_name: str) -> dict:  # pragma: no cover  (frappe I/O — proven live L4)
    """The canonical JML identity the consumers key on (matricule/job/dept/country/entity)."""
    e = frappe.get_doc("Employee", employee_name)
    country = frappe.db.get_value("Company", e.company, "country") if e.company else None
    return {
        "matricule": e.get("employee_number") or e.name,
        "employee": e.name,
        "employee_name": e.get("employee_name"),
        "email": e.get("company_email") or e.get("personal_email") or e.get("user_id"),
        "job": e.get("designation"),
        "department": e.get("department"),
        "grade": e.get("grade"),
        "entity": e.get("company"),
        "country": country,
        "status": e.get("status"),
    }


def _emit(  # pragma: no cover  (frappe enqueue I/O — proven live L4)
    event_type: str,
    employee_name: str,
    *,
    effective_date=None,
    change=None,
) -> None:
    """Build the event and enqueue the publish — background, so it never blocks the HR save."""
    try:
        subject = _subject_payload(employee_name)
        event = build_event(event_type, subject, effective_date=effective_date, change=change)
    except Exception:  # building must never break the HR transaction
        frappe.log_error(title="hr-lifecycle: build failed")
        return
    frappe.enqueue(
        "erpnext_hr_lifecycle.events.publish",
        queue="short",
        job_name=f"hr-lifecycle-{event_type}-{employee_name}",
        event=event,
    )


def publish(event: dict) -> None:  # pragma: no cover  (NATS/HTTP I/O — proven live L4)
    """Background worker: sign + publish to NATS (durable) and POST to n8n (fan-out). Best-effort."""
    body = canonical_bytes(event)
    signature = sign(body, _cfg("HR_LIFECYCLE_SIGNING_KEY"))
    subject = f"{SUBJECT_PREFIX}.{event['event']}"

    # 1. durable, signed backbone — NATS JetStream (ktayl-iam v3 consumes this later for access)
    try:
        _publish_nats(subject, body, signature)
    except Exception:
        frappe.log_error(title="hr-lifecycle: NATS publish failed")

    # 2. non-access fan-out — n8n (GLPI task + email). Failure here never matters to HR.
    webhook = _cfg("HR_N8N_WEBHOOK_URL")
    if webhook:
        try:
            import requests

            requests.post(
                webhook,
                data=body,
                headers={"Content-Type": "application/json", "X-HR-Signature": signature},
                timeout=10,
            )
        except Exception:
            frappe.log_error(title="hr-lifecycle: n8n fan-out failed")


def _publish_nats(subject: str, body: bytes, signature: str) -> None:  # pragma: no cover
    import asyncio

    import nats

    url = _cfg("HR_NATS_URL", "nats://nats.messaging.svc:4222")
    stream = _cfg("HR_LIFECYCLE_STREAM", "HR_LIFECYCLE")

    async def _go() -> None:
        nc = await nats.connect(url, name="erpnext-hr-lifecycle")
        try:
            js = nc.jetstream()
            headers = {"HR-Signature": signature} if signature else None
            # stream already created by the gitops stream-init Job; publish is bound to it by subject
            ack = await js.publish(subject, body, stream=stream, headers=headers)
            frappe.logger("hr-lifecycle").info(
                f"published {subject} seq={getattr(ack, 'seq', '?')}"
            )
        finally:
            await nc.close()

    asyncio.run(_go())


# ── doc_event handlers (wired in hooks.py) ────────────────────────────────────  # pragma: no cover


def on_employee_insert(doc, method=None):  # pragma: no cover
    _emit("joiner", doc.name, effective_date=doc.get("date_of_joining"))


def on_promotion(doc, method=None):  # pragma: no cover
    changes = [
        {"field": r.get("property"), "current": r.get("current"), "new": r.get("new")}
        for r in (doc.get("promotion_details") or [])
    ]
    _emit(
        "mover",
        doc.employee,
        effective_date=doc.get("promotion_date"),
        change={"kind": "promotion", "changes": changes},
    )


def on_transfer(doc, method=None):  # pragma: no cover
    _emit(
        "mover",
        doc.employee,
        effective_date=doc.get("transfer_date"),
        change={"kind": "transfer", "new_company": doc.get("new_company")},
    )


def on_separation(doc, method=None):  # pragma: no cover
    # effective = the employee's relieving date if set, else the separation start.
    eff = (
        frappe.db.get_value("Employee", doc.employee, "relieving_date")
        or doc.get("boarding_begins_on")
        or doc.get("resignation_letter_date")
    )
    _emit("leaver", doc.employee, effective_date=eff)


@frappe.whitelist()  # pragma: no cover
def emit_test_event(event_type: str = "joiner", employee: str | None = None):
    """Smoke-test the live seam without mutating HR data: enqueues a real event for an employee.

    Admin-only (whitelisted + role check). Returns the event that was enqueued.
    """
    frappe.only_for(["System Manager", "HR Manager"])
    if event_type not in VALID_EVENTS:
        frappe.throw(f"event_type must be one of {sorted(VALID_EVENTS)}")
    emp: str = (
        employee
        or frappe.get_all("Employee", filters={"status": "Active"}, limit=1, pluck="name")[0]
    )
    subject = _subject_payload(emp)
    event = build_event(event_type, subject)
    frappe.enqueue(
        "erpnext_hr_lifecycle.events.publish",
        queue="short",
        job_name=f"hr-lifecycle-test-{event_type}",
        event=event,
    )
    return {"enqueued": True, "event": event}

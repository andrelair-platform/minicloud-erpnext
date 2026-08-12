"""
Mock Stripe API server for cluster dev/CI.

Implements the subset used by erpnext_sepa + the n8n workflow:
  POST /v1/customers
  POST /v1/payment_methods
  POST /v1/payment_methods/<id>/attach
  POST /v1/setup_intents
  POST /v1/setup_intents/<id>/confirm
  POST /v1/payment_intents
  GET  /v1/payment_intents/<id>

After POST /v1/payment_intents, fires a payment_intent.succeeded webhook
to ERPNext after 2 seconds (simulating Stripe's async confirmation).

Stripe webhook signature format:
  Stripe-Signature: t=<unix_ts>,v1=<HMAC-SHA256(secret, "<ts>.<body>")>
"""

import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer

ERPNEXT_WEBHOOK_URL = os.environ.get(
    "ERPNEXT_WEBHOOK_URL",
    "http://erpnext.erp.svc.cluster.local:8000"
    "/api/method/erpnext_sepa.api.stripe_webhook",
)
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "whsec_mock_dev_secret")

_store: dict = {
    "customers": {},
    "payment_methods": {},
    "setup_intents": {},
    "payment_intents": {},
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        print(f"[mock-stripe] {self.address_string()} {format % args}")

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw)

    def do_POST(self):
        body = self._read_body()
        path = self.path.split("?")[0].rstrip("/")

        if path == "/v1/customers":
            self._handle_create_customer(body)
        elif path == "/v1/payment_methods":
            self._handle_create_payment_method(body)
        elif path.startswith("/v1/payment_methods/") and path.endswith("/attach"):
            pm_id = path.split("/")[3]
            self._handle_attach_payment_method(pm_id, body)
        elif path == "/v1/setup_intents":
            self._handle_create_setup_intent(body)
        elif path.startswith("/v1/setup_intents/") and path.endswith("/confirm"):
            si_id = path.split("/")[3]
            self._handle_confirm_setup_intent(si_id, body)
        elif path == "/v1/payment_intents":
            self._handle_create_payment_intent(body)
        else:
            self._json(404, {"error": {"message": f"Unhandled path: {path}"}})

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path.startswith("/v1/payment_intents/"):
            pi_id = path.split("/")[3]
            record = _store["payment_intents"].get(pi_id)
            if record:
                self._json(200, record)
            else:
                self._json(404, {"error": {"message": "No such payment_intent"}})
        else:
            self._json(404, {"error": {"message": "Not found"}})

    # ------------------------------------------------------------------

    def _handle_create_customer(self, body: dict):
        cus_id = f"cus_{uuid.uuid4().hex[:14]}"
        record = {"id": cus_id, "object": "customer", **body}
        _store["customers"][cus_id] = record
        self._json(200, record)

    def _handle_create_payment_method(self, body: dict):
        pm_id = f"pm_{uuid.uuid4().hex[:14]}"
        record = {"id": pm_id, "object": "payment_method", **body}
        _store["payment_methods"][pm_id] = record
        self._json(200, record)

    def _handle_attach_payment_method(self, pm_id: str, body: dict):
        record = _store["payment_methods"].get(pm_id, {"id": pm_id})
        record["customer"] = body.get("customer", "")
        _store["payment_methods"][pm_id] = record
        self._json(200, record)

    def _handle_create_setup_intent(self, body: dict):
        si_id = f"seti_{uuid.uuid4().hex[:14]}"
        confirm = body.get("confirm", False)
        record = {
            "id": si_id,
            "object": "setup_intent",
            "status": "succeeded" if confirm else "requires_confirmation",
            "customer": body.get("customer", ""),
            "payment_method": body.get("payment_method", ""),
            "payment_method_types": body.get("payment_method_types", ["sepa_debit"]),
        }
        _store["setup_intents"][si_id] = record
        self._json(200, record)
        if confirm:
            threading.Thread(
                target=_fire_webhook,
                args=("setup_intent.succeeded", {"object": record}),
                daemon=True,
            ).start()

    def _handle_confirm_setup_intent(self, si_id: str, body: dict):
        record = _store["setup_intents"].get(si_id, {"id": si_id})
        record["status"] = "succeeded"
        if "payment_method" in body:
            record["payment_method"] = body["payment_method"]
        _store["setup_intents"][si_id] = record
        self._json(200, record)
        threading.Thread(
            target=_fire_webhook,
            args=("setup_intent.succeeded", {"object": record}),
            daemon=True,
        ).start()

    def _handle_create_payment_intent(self, body: dict):
        pi_id = f"pi_{uuid.uuid4().hex[:14]}"
        amount = body.get("amount", 0)
        record = {
            "id": pi_id,
            "object": "payment_intent",
            "amount": amount,
            "amount_received": amount,
            "currency": body.get("currency", "eur"),
            "status": "processing",
            "customer": body.get("customer", ""),
            "payment_method": body.get("payment_method", ""),
            "metadata": body.get("metadata", {}),
        }
        _store["payment_intents"][pi_id] = record
        self._json(200, record)
        threading.Thread(
            target=_fire_webhook,
            args=("payment_intent.succeeded", {"object": record}),
            daemon=True,
        ).start()

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


# ---------------------------------------------------------------------------
# Webhook dispatcher
# ---------------------------------------------------------------------------

def _fire_webhook(event_type: str, data: dict, delay: float = 2.0):
    import urllib.request

    time.sleep(delay)

    ts = str(int(time.time()))
    event_payload = json.dumps({
        "id": f"evt_{uuid.uuid4().hex[:14]}",
        "object": "event",
        "type": event_type,
        "data": data,
    }).encode()

    # Stripe signature: t=<ts>,v1=<HMAC-SHA256(secret, "<ts>.<payload>")>
    signed_payload = f"{ts}.".encode() + event_payload
    mac = hmac.new(WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256).hexdigest()
    sig_header = f"t={ts},v1={mac}"

    req = urllib.request.Request(
        ERPNEXT_WEBHOOK_URL,
        data=event_payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": sig_header,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[mock-stripe] webhook {event_type} → ERPNext: {resp.status}")
    except Exception as exc:
        print(f"[mock-stripe] webhook {event_type} failed: {exc}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[mock-stripe] Mock Stripe API on :{port}")
    print(f"[mock-stripe] Webhook target: {ERPNEXT_WEBHOOK_URL}")
    server.serve_forever()

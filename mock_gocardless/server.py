"""
Mock GoCardless API server for cluster dev/CI.
Implements the subset of endpoints used by erpnext_sepa:
  POST /customers
  POST /customer_bank_accounts
  POST /mandates
  POST /payments
  GET  /payments/<id>

Always returns sandbox-style responses. On POST /payments it also fires
the webhook to erpnext_sepa.api.gocardless_webhook after a 2-second delay.
"""

import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer


WEBHOOK_TARGET = os.environ.get(
    "ERPNEXT_WEBHOOK_URL",
    "http://erpnext.erp.svc.cluster.local:8000/api/method/erpnext_sepa.api.gocardless_webhook",
)
WEBHOOK_SECRET = os.environ.get("GC_WEBHOOK_SECRET", "mock-secret-dev")


_store: dict = {"customers": {}, "bank_accounts": {}, "mandates": {}, "payments": {}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[mock-gc] {self.address_string()} {fmt % args}")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}

        if self.path == "/customers":
            obj_id = f"CU{uuid.uuid4().hex[:8].upper()}"
            data = body.get("customers", {})
            _store["customers"][obj_id] = {"id": obj_id, **data}
            self._json(201, {"customers": {"id": obj_id, **data}})

        elif self.path == "/customer_bank_accounts":
            obj_id = f"BA{uuid.uuid4().hex[:8].upper()}"
            data = body.get("customer_bank_accounts", {})
            _store["bank_accounts"][obj_id] = {"id": obj_id, **data}
            self._json(201, {"customer_bank_accounts": {"id": obj_id, **data}})

        elif self.path == "/mandates":
            obj_id = f"MD{uuid.uuid4().hex[:8].upper()}"
            data = body.get("mandates", {})
            record = {"id": obj_id, "status": "active", "scheme": data.get("scheme", "sepa_core"), **data}
            _store["mandates"][obj_id] = record
            self._json(201, {"mandates": record})

        elif self.path == "/payments":
            obj_id = f"PM{uuid.uuid4().hex[:8].upper()}"
            data = body.get("payments", {})
            record = {
                "id": obj_id,
                "status": "pending_submission",
                "amount": data.get("amount", 0),
                "currency": data.get("currency", "EUR"),
                "description": data.get("description", ""),
                "metadata": data.get("metadata", {}),
                "links": data.get("links", {}),
                "created_at": datetime.utcnow().isoformat() + "Z",
                "charge_date": date.today().isoformat(),
            }
            _store["payments"][obj_id] = record
            self._json(201, {"payments": record})
            # Fire paid_out webhook after 2 s
            threading.Thread(target=_fire_webhook, args=(obj_id,), daemon=True).start()

        else:
            self._json(404, {"error": {"message": "Not found"}})

    def do_GET(self):
        if self.path.startswith("/payments/"):
            obj_id = self.path.split("/")[-1]
            record = _store["payments"].get(obj_id)
            if record:
                self._json(200, {"payments": record})
            else:
                self._json(404, {"error": {"message": "Payment not found"}})
        else:
            self._json(404, {"error": {"message": "Not found"}})

    def _json(self, code: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _fire_webhook(payment_id: str):
    """Send a payments.paid_out webhook to ERPNext after a short delay."""
    import urllib.request

    time.sleep(2)
    payment = _store["payments"].get(payment_id, {})
    _store["payments"][payment_id]["status"] = "paid_out"

    payload = json.dumps({
        "events": [
            {
                "id": f"EV{uuid.uuid4().hex[:8].upper()}",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "resource_type": "payments",
                "action": "paid_out",
                "links": {"payment": payment_id},
                "amount": payment.get("amount", 0),
                "metadata": payment.get("metadata", {}),
            }
        ]
    }).encode()

    sig = hmac.new(WEBHOOK_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        WEBHOOK_TARGET,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Webhook-Signature": sig,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"[mock-gc] webhook → ERPNext: {resp.status} for payment {payment_id}")
    except Exception as exc:
        print(f"[mock-gc] webhook failed for {payment_id}: {exc}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[mock-gc] Mock GoCardless API listening on :{port}")
    server.serve_forever()

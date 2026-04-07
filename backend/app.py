import json
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from algosdk.v2client import algod
from algosdk import mnemonic, account, transaction


ROOT_DIR = Path(__file__).resolve().parent.parent
STORAGE_PATH = Path(__file__).resolve().parent / "storage.json"
HOST = "127.0.0.1"
PORT = 8000

# 🔑 Blockchain setup
sender_mnemonic = "furnace ladder wet girl swap thank else inside episode walk defense gasp clarify permit term power horse ordinary stamp hybrid monkey tree segment above lion"
sender_private_key = mnemonic.to_private_key(sender_mnemonic)
sender_address = account.address_from_private_key(sender_private_key)

# ✅ Public Algonode testnet — no local node needed
algod_client = algod.AlgodClient(
    "",
    "https://testnet-api.algonode.cloud"
)

DEFAULT_STATE = {
    "spend_cap": 40,
    "spent": 0,
    "receipts": [],
}

# ✅ payment_address uses sender_address (real testnet address) for demo
# Replace with actual vendor addresses when available
SERVICES = [
    {
        "id": "weather-oracle",
        "name": "Weather Oracle API",
        "description": "Localized planning data for routing, field ops, and purchase timing agents.",
        "price": 1,
        "category": "Data feed",
        "payment_address": sender_address,
        "response_preview": "Forecast confidence 94%, precipitation risk low, wind volatility moderate.",
        "latency_target": "2.1s avg",
        "settlement_mode": "ALGO transfer",
    },
    {
        "id": "identity-check",
        "name": "Identity Check Gateway",
        "description": "KYC and risk screening for high-value autonomous workflows.",
        "price": 1,
        "category": "Compliance",
        "payment_address": sender_address,
        "response_preview": "Counterparty verified with medium-risk jurisdiction advisory.",
        "latency_target": "3.4s avg",
        "settlement_mode": "ALGO transfer",
    },
    {
        "id": "route-engine",
        "name": "Route Engine",
        "description": "Optimization service for logistics agents and delivery decision loops.",
        "price": 1,
        "category": "Compute",
        "payment_address": sender_address,
        "response_preview": "Optimal route reduced travel cost estimate by 11%.",
        "latency_target": "1.8s avg",
        "settlement_mode": "ASA-ready",
    },
    {
        "id": "market-signal",
        "name": "Market Signal Stream",
        "description": "Short-horizon pricing and sentiment intelligence for trading copilots.",
        "price": 1,
        "category": "Signal",
        "payment_address": sender_address,
        "response_preview": "Momentum positive across 3 tracked sectors with moderate confidence.",
        "latency_target": "2.8s avg",
        "settlement_mode": "ALGO transfer",
    },
]


def load_env_file() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_state() -> dict[str, Any]:
    if not STORAGE_PATH.exists():
        save_state(DEFAULT_STATE)
        return clone_default_state()
    try:
        data = json.loads(STORAGE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return clone_default_state()
    return {
        "spend_cap": int(data.get("spend_cap", DEFAULT_STATE["spend_cap"])),
        "spent": int(data.get("spent", 0)),
        "receipts": list(data.get("receipts", [])),
    }


def save_state(state: dict[str, Any]) -> None:
    STORAGE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def clone_default_state() -> dict[str, Any]:
    return {
        "spend_cap": DEFAULT_STATE["spend_cap"],
        "spent": DEFAULT_STATE["spent"],
        "receipts": [],
    }


def build_config() -> dict[str, Any]:
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    return {
        "network": os.getenv("ALGOD_NETWORK", "testnet"),
        "algod_server": os.getenv("ALGOD_SERVER", "https://testnet-api.algonode.cloud"),
        "indexer_server": os.getenv("INDEXER_SERVER", "https://testnet-idx.algonode.cloud"),
        "payment_wallet": sender_address,
        "pinata_gateway": os.getenv("PINATA_GATEWAY", "https://gateway.pinata.cloud/ipfs"),
        "gemini_enabled": bool(gemini_key),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"),
    }


def find_service(service_id: str) -> dict[str, Any] | None:
    return next((s for s in SERVICES if s["id"] == service_id), None)


def generate_tx_id() -> str:
    tail = str(int(time.time() * 1000))[-6:]
    random_part = "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
    return f"ALGO-{random_part}-{tail}"


def build_receipt(service: dict[str, Any], status: str, tx_id: str, response: str) -> dict[str, Any]:
    return {
        "service_name": service["name"],
        "cost": service["price"],
        "tx_id": tx_id,
        "status": status,
        "response": response,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def send_algo_payment(receiver: str, amount_algo: int) -> str:
    """Send ALGO payment and return transaction ID."""
    params = algod_client.suggested_params()
    txn = transaction.PaymentTxn(
        sender=sender_address,
        sp=params,
        receiver=receiver,
        amt=amount_algo * 1_000_000  # convert ALGO to microALGOs
    )
    signed_txn = txn.sign(sender_private_key)
    return algod_client.send_transaction(signed_txn)


def generate_brief(objective: str, service: dict[str, Any] | None) -> str:
    objective = objective.strip()
    if not objective:
        return "Provide an objective so the buyer agent can prepare a purchase brief."

    service_context = (
        f"Target service: {service['name']} ({service['category']}, {service['price']} ALGO). "
        if service
        else "Target service: any matching registry listing. "
    )
    prompt = (
        "You are drafting a machine-readable purchase brief for an autonomous service buyer on Algorand. "
        "Return a concise operator-friendly paragraph followed by a compact intent tag. "
        f"{service_context}"
        f"Objective: {objective}"
    )

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    if not gemini_key:
        return (
            f"Buyer brief: Acquire a service that satisfies '{objective}' while respecting spend caps, "
            "waiting for on-chain confirmation, and logging the receipt for audit. "
            f"Intent tag: objective={objective[:40]} | service={service['id'] if service else 'auto-select'} | mode=policy-checked."
        )

    endpoint = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent"
        f"?key={gemini_key}"
    )
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}]
    }).encode("utf-8")

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        return f"Gemini request failed, so a local fallback brief was used instead. Details: {exc}"

    candidates = payload.get("candidates", [])
    if not candidates:
        return "Gemini returned no candidates. Check the API key, model name, or quota."

    parts = candidates[0].get("content", {}).get("parts", [])
    texts = [part.get("text", "").strip() for part in parts if part.get("text")]
    return "\n".join(texts) if texts else "Gemini returned an empty completion."


class Handler(BaseHTTPRequestHandler):

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/api/config":
            self._send_json(200, build_config())
            return
        if self.path == "/api/services":
            self._send_json(200, {"services": SERVICES})
            return
        if self.path == "/api/state":
            self._send_json(200, load_state())
            return
        self._serve_static()

    def do_POST(self) -> None:
        if self.path == "/api/policy":
            self._handle_policy()
            return
        if self.path == "/api/purchase":
            self._handle_purchase()
            return
        if self.path == "/api/receipts/clear":
            self._handle_clear_receipts()
            return
        if self.path == "/api/gemini/brief":
            self._handle_gemini_brief()
            return
        if self.path == "/pay":
            self._handle_payment()
            return
        self._send_json(404, {"error": "Route not found."})

    def _handle_policy(self) -> None:
        payload = self._read_json_body()
        try:
            spend_cap = int(payload.get("spend_cap", 0))
        except (TypeError, ValueError):
            spend_cap = 0
        if spend_cap <= 0:
            self._send_json(400, {"error": "Spend cap must be greater than zero."})
            return
        state = load_state()
        state["spend_cap"] = spend_cap
        save_state(state)
        self._send_json(200, {
            "message": f"Spend policy saved with cap {spend_cap} ALGO.",
            "state": state,
        })

    def _handle_purchase(self) -> None:
        """Full purchase flow: policy check → blockchain payment → receipt."""
        payload = self._read_json_body()
        service = find_service(str(payload.get("service_id", "")))

        if not service:
            self._send_json(404, {"error": "Service not found in the registry."})
            return

        state = load_state()

        # Policy check
        if state["spent"] + service["price"] > state["spend_cap"]:
            self._send_json(402, {
                "error": "Spend cap exceeded.",
                "summary": {
                    "title": "Policy blocked",
                    "copy": f"Purchasing {service['name']} would exceed your cap of {state['spend_cap']} ALGO.",
                    "tone": "blocked"
                },
                "timeline": [
                    {"step": "Policy", "detail": f"Blocked: projected spend exceeds cap of {state['spend_cap']} ALGO."}
                ]
            })
            return

        # Send real blockchain payment
        try:
            txid = send_algo_payment(service["payment_address"], service["price"])
        except Exception as e:
            print(f"🔥 Purchase payment error: {e}")
            self._send_json(500, {
                "error": f"Blockchain payment failed: {str(e)}",
                "summary": {
                    "title": "Payment failed",
                    "copy": str(e),
                    "tone": "blocked"
                },
                "timeline": [
                    {"step": "Payment", "detail": f"Failed: {str(e)}"}
                ]
            })
            return

        # Save receipt and update state
        receipt = build_receipt(service, "Confirmed", txid, service["response_preview"])
        state["spent"] += service["price"]
        state["receipts"].insert(0, receipt)
        save_state(state)

        self._send_json(200, {
            "message": "Purchase complete.",
            "tx_id": txid,
            "receipt": receipt,
            "state": state,
            "summary": {
                "title": "Payment confirmed ✅",
                "copy": f"{service['name']} purchased. Tx: {txid[:16]}...",
                "tone": "active"
            },
            "timeline": [
                {"step": "Discover", "detail": f"Selected {service['name']} — {service['price']} ALGO."},
                {"step": "Policy", "detail": f"Cap OK — {state['spent']} of {state['spend_cap']} ALGO used."},
                {"step": "Payment", "detail": f"Sent {service['price']} ALGO on Algorand testnet."},
                {"step": "Confirm", "detail": f"Transaction ID: {txid}"},
                {"step": "Consume", "detail": service["response_preview"]},
                {"step": "Receipt", "detail": "Logged to persistent audit trail."}
            ]
        })

    def _handle_payment(self) -> None:
        """Direct /pay endpoint — sends ALGO to any given address."""
        print("✅ /pay endpoint called")
        try:
            payload = self._read_json_body()
            receiver = payload.get("address")

            if not receiver:
                self._send_json(400, {"error": "Missing 'address' in request body."})
                return

            params = algod_client.suggested_params()
            txn = transaction.PaymentTxn(
                sender=sender_address,
                sp=params,
                receiver=receiver,
                amt=1_000_000  # 1 ALGO in microALGOs
            )
            signed_txn = txn.sign(sender_private_key)
            txid = algod_client.send_transaction(signed_txn)

            print(f"✅ Transaction sent: {txid}")
            self._send_json(200, {"status": "success", "txId": txid})

        except Exception as e:
            print(f"🔥 PAYMENT ERROR: {e}")
            self._send_json(500, {"status": "error", "message": str(e)})

    def _handle_clear_receipts(self) -> None:
        state = clone_default_state()
        save_state(state)
        self._send_json(200, {
            "message": "Receipt log cleared and spend totals reset.",
            "state": state,
        })

    def _handle_gemini_brief(self) -> None:
        payload = self._read_json_body()
        objective = str(payload.get("objective", ""))
        service = find_service(str(payload.get("service_id", ""))) if payload.get("service_id") else None
        brief = generate_brief(objective, service)
        self._send_json(200, {"brief": brief})

    def _serve_static(self) -> None:
        path = self.path
        if path in ("/", ""):
            target = ROOT_DIR / "index.html"
        else:
            target = (ROOT_DIR / path.lstrip("/")).resolve()

        if (
            not str(target).startswith(str(ROOT_DIR.resolve()))
            or not target.exists()
            or not target.is_file()
        ):
            self._send_json(404, {"error": "Static file not found."})
            return

        content_type = "text/plain; charset=utf-8"
        if target.suffix == ".html":
            content_type = "text/html; charset=utf-8"
        elif target.suffix == ".css":
            content_type = "text/css; charset=utf-8"
        elif target.suffix == ".js":
            content_type = "application/javascript; charset=utf-8"

        self.send_response(200)
        self._send_common_headers(content_type)
        self.end_headers()
        self.wfile.write(target.read_bytes())

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self._send_common_headers("application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def _send_common_headers(self, content_type: str = "application/json; charset=utf-8") -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    load_env_file()
    save_state(load_state())
    print(f"✅ Sender address: {sender_address}")
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"✅ Serving Agentic Service Buyer on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()

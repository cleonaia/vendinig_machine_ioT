"""Loopback-only administration service for the isolated vending lab."""
from __future__ import annotations

import hmac
import json
import os
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from app.services.fleet_manager import FleetError, FleetManager

DB_PATH = Path(os.environ.get("VENDING_DB", "vending-lab.sqlite3"))
PRODUCTS = {"water": ("Water", 150), "snack": ("Snack", 225)}


def valid_bearer(header: str, token: str) -> bool:
    return hmac.compare_digest(header, f"Bearer {token}")


def authenticate_bearer(header: str, credentials: dict[str, str]) -> str | None:
    matched_role = None
    for role, token in credentials.items():
        if hmac.compare_digest(header, f"Bearer {token}"):
            matched_role = role
    return matched_role


def role_can_execute(role: str, capability: str) -> bool:
    return role == "admin" or (role == "operator" and capability in {"diagnostics.run", "connection.recover"})


def strict_json_loads(payload: bytes) -> object:
    def reject_constant(value: str):
        raise ValueError(f"invalid JSON constant: {value}")

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    return json.loads(payload, parse_constant=reject_constant, object_pairs_hook=reject_duplicate_keys)


def parse_stock_update(body: object) -> tuple[str, int]:
    if not isinstance(body, dict) or set(body) != {"product_id", "stock"}:
        raise ValueError("expected product_id and stock only")
    product_id, stock = body["product_id"], body["stock"]
    if not isinstance(product_id, str) or product_id not in PRODUCTS:
        raise ValueError("unknown product_id")
    if type(stock) is not int or not 0 <= stock <= 10000:
        raise ValueError("stock must be an integer from 0 to 10000")
    return product_id, stock


def simulated_status() -> dict[str, object]:
    return {"machine_id": "lab-vending-01", "connection": "simulated", "availability": "simulated", "temperature_c": 5.2, "last_communication": None, "data_origin": "local_simulator", "hardware_connected": False}


class LabStore:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        return db

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS inventory (product_id TEXT PRIMARY KEY, name TEXT NOT NULL, price_minor INTEGER NOT NULL, stock INTEGER NOT NULL CHECK(stock >= 0), source TEXT NOT NULL DEFAULT 'manual_simulation')")
            db.execute("CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, action TEXT NOT NULL, product_id TEXT, details TEXT NOT NULL)")
            for product_id, (name, price) in PRODUCTS.items():
                db.execute("INSERT OR IGNORE INTO inventory(product_id,name,price_minor,stock) VALUES(?,?,?,10)", (product_id, name, price))

    def inventory(self) -> list[dict[str, object]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT product_id,name,price_minor,stock,source FROM inventory ORDER BY product_id")]

    def update_stock(self, product_id: str, stock: int) -> dict[str, object] | None:
        if product_id not in PRODUCTS or type(stock) is not int or not 0 <= stock <= 10000:
            raise ValueError("product_id must be known and stock an integer from 0 to 10000")
        now = datetime.now(timezone.utc).isoformat()
        with self.connect() as db:
            cursor = db.execute("UPDATE inventory SET stock=?,source='manual_simulation' WHERE product_id=?", (stock, product_id))
            if cursor.rowcount != 1:
                return None
            db.execute("INSERT INTO audit(at,action,product_id,details) VALUES(?,?,?,?)", (now, "inventory.stock.set", product_id, json.dumps({"stock": stock})))
            return dict(db.execute("SELECT product_id,name,price_minor,stock,source FROM inventory WHERE product_id=?", (product_id,)).fetchone())

    def events(self) -> list[dict[str, object]]:
        with self.connect() as db:
            return [dict(row) for row in db.execute("SELECT id,at,action,product_id,details FROM audit ORDER BY id DESC LIMIT 100")]


def make_handler(store: LabStore, token: str | dict[str, str], fleet_manager: FleetManager | None = None):
    fleet = fleet_manager or FleetManager(store.path)
    credentials = {"admin": token} if isinstance(token, str) else dict(token)

    class Handler(BaseHTTPRequestHandler):
        server_version = "VendingLab/1.0"

        def send_json(self, status: HTTPStatus, body: object) -> None:
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self) -> bool:
            role = authenticate_bearer(self.headers.get("Authorization", ""), credentials)
            if role is None:
                fleet.record_access("anonymous", urlparse(self.path).path, "authentication_denied")
                self.send_json(HTTPStatus.UNAUTHORIZED, {"error": "authentication_required"})
                return False
            self.role = role
            return True

        def require_role(self, roles: set[str]) -> bool:
            if self.role in roles:
                return True
            fleet.record_access(f"local-{self.role}", urlparse(self.path).path, "role_denied")
            self.send_json(HTTPStatus.FORBIDDEN, {"error": "role_not_permitted"})
            return False

        def read_body(self) -> object:
            length = int(self.headers.get("Content-Length", "0"))
            if not 1 <= length <= 4096:
                raise ValueError("body size must be 1 to 4096 bytes")
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError("Content-Type must be application/json")
            return strict_json_loads(self.rfile.read(length))

        def route_error(self, exc: Exception) -> None:
            if isinstance(exc, FleetError):
                self.send_json(HTTPStatus(exc.status_code), {"error": exc.code})
            elif isinstance(exc, (ValueError, TypeError, json.JSONDecodeError)):
                self.send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_request", "detail": str(exc)})
            else:
                self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "internal_error"})

        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if not self.authorized():
                return
            try:
                if route == "/":
                    page = (Path(__file__).parent / "admin.html").read_bytes()
                    self.send_response(HTTPStatus.OK)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(page)))
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(page)
                elif route == "/api/session":
                    self.send_json(HTTPStatus.OK, {"role": self.role})
                elif route == "/api/adapters":
                    self.send_json(HTTPStatus.OK, {"items": fleet.adapters()})
                elif route == "/api/machines":
                    items = fleet.machines()
                    origin = "local_simulator" if all(item["simulated"] for item in items) else "mixed"
                    self.send_json(HTTPStatus.OK, {"items": items, "data_origin": origin})
                elif route == "/api/commands":
                    self.send_json(HTTPStatus.OK, {"items": fleet.command_history()})
                elif route == "/api/audit":
                    if not self.require_role({"admin"}):
                        return
                    self.send_json(HTTPStatus.OK, {"items": fleet.access_history()})
                elif route.startswith("/api/machines/"):
                    parts = route.strip("/").split("/")
                    if len(parts) == 3 and parts[2] == "capabilities":
                        result = {"items": fleet.capabilities(parts[1])}
                    elif len(parts) == 3 and parts[2] == "commands":
                        result = {"items": fleet.command_history(parts[1])}
                    elif len(parts) == 3 and parts[2] in {"status", "inventory", "diagnostics", "telemetry", "alarms", "sales", "payment"}:
                        cap = {"status": "status.read", "inventory": "inventory.read", "diagnostics": "diagnostics.read", "telemetry": "telemetry.read", "alarms": "alarms.read", "sales": "sales.read", "payment": "payment.status"}[parts[2]]
                        result = {"item": fleet.resource(parts[1], cap)}
                    elif len(parts) == 2:
                        result = {"item": fleet.machine(parts[1])}
                    else:
                        self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
                        return
                    self.send_json(HTTPStatus.OK, result)
                elif route == "/api/status":
                    self.send_json(HTTPStatus.OK, simulated_status())
                elif route == "/api/inventory":
                    self.send_json(HTTPStatus.OK, {"items": store.inventory(), "data_origin": "local_database_manual_simulation"})
                elif route == "/api/events":
                    self.send_json(HTTPStatus.OK, {"items": store.events(), "data_origin": "local_administration_audit"})
                else:
                    self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            except Exception as exc:
                self.route_error(exc)

        def do_POST(self) -> None:
            if not self.authorized():
                return
            try:
                route = urlparse(self.path).path
                body = self.read_body()
                if route == "/api/machines":
                    if not self.require_role({"admin"}):
                        return
                    item = fleet.register_machine(body)
                    fleet.record_access(f"local-{self.role}", f"machine.register:{item['machine_id']}", "accepted")
                    self.send_json(HTTPStatus.CREATED, {"item": item})
                elif route.startswith("/api/machines/") and route.endswith("/commands"):
                    if not self.require_role({"admin", "operator"}):
                        return
                    machine_id = route.strip("/").split("/")[2]
                    if not isinstance(body, dict) or not role_can_execute(self.role, body.get("capability", "")):
                        fleet.record_access(f"local-{self.role}", route, "capability_denied")
                        self.send_json(HTTPStatus.FORBIDDEN, {"error": "capability_not_permitted_for_role"})
                        return
                    self.send_json(HTTPStatus.OK, {"item": fleet.run_command(machine_id, body, actor=f"local-{self.role}")})
                elif route == "/api/inventory":
                    if not self.require_role({"admin"}):
                        return
                    product_id, stock = parse_stock_update(body)
                    item = store.update_stock(product_id, stock)
                    if item is None:
                        self.send_json(HTTPStatus.NOT_FOUND, {"error": "unknown_product"})
                    else:
                        self.send_json(HTTPStatus.OK, {"item": item, "result": "local_simulation_updated"})
                else:
                    self.send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            except Exception as exc:
                self.route_error(exc)

    return Handler


def main() -> None:
    credentials = {role: os.environ[key] for role, key in (
        ("admin", "VENDING_ADMIN_TOKEN"), ("operator", "VENDING_OPERATOR_TOKEN"), ("viewer", "VENDING_VIEWER_TOKEN"))
                   if os.environ.get(key)}
    if "admin" not in credentials or any(len(token) < 32 for token in credentials.values()):
        raise SystemExit("Set a distinct VENDING_ADMIN_TOKEN of at least 32 characters; operator/viewer tokens are optional")
    if len(set(credentials.values())) != len(credentials):
        raise SystemExit("Each configured role must use a distinct token")
    host = os.environ.get("VENDING_HOST", "127.0.0.1")
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise SystemExit("The lab console binds only to loopback; remote exposure is disabled")
    port = int(os.environ.get("VENDING_PORT", "8080"))
    server = ThreadingHTTPServer((host, port), make_handler(LabStore(), credentials))
    print(f"Vending lab console on http://{host}:{port} (simulator only)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

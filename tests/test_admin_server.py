import tempfile
import unittest
import socket
from pathlib import Path

from app.admin_server import LabStore, authenticate_bearer, make_handler, parse_stock_update, role_can_execute, simulated_status, strict_json_loads, valid_bearer
from app.services.fleet_manager import FleetManager


class AdminApiComponentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = LabStore(Path(self.temp.name) / "test.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def test_bearer_validation(self):
        self.assertTrue(valid_bearer("Bearer " + "a" * 40, "a" * 40))
        self.assertFalse(valid_bearer("Bearer wrong", "a" * 40))
        self.assertFalse(valid_bearer("", "a" * 40))

    def test_role_tokens_identify_one_configured_role(self):
        credentials = {"admin": "a" * 40, "operator": "b" * 40, "viewer": "c" * 40}
        self.assertEqual(authenticate_bearer("Bearer " + "b" * 40, credentials), "operator")
        self.assertEqual(authenticate_bearer("Bearer " + "c" * 40, credentials), "viewer")
        self.assertIsNone(authenticate_bearer("Bearer wrong", credentials))

    def test_command_permissions_are_role_and_capability_scoped(self):
        self.assertTrue(role_can_execute("admin", "vend.simulate"))
        self.assertTrue(role_can_execute("operator", "diagnostics.run"))
        self.assertFalse(role_can_execute("operator", "vend.simulate"))
        self.assertFalse(role_can_execute("viewer", "diagnostics.run"))

    def test_strict_json_rejects_ambiguous_or_nonstandard_values(self):
        for payload in (b'{"stock":1,"stock":2}', b'{"stock":NaN}'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                strict_json_loads(payload)


class InProcessHttpApiTests(unittest.TestCase):
    class FakeServer:
        server_name = "localhost"
        server_port = 8080

        def log_request(self, code="-", size="-"):
            pass

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        db_path = Path(self.temp.name) / "http.sqlite3"
        self.store = LabStore(db_path)
        self.fleet = FleetManager(db_path)

    def tearDown(self):
        self.temp.cleanup()

    def request(self, method, path, role, body=None):
        payload = b"" if body is None else __import__("json").dumps(body).encode()
        credentials = {"admin": "a" * 40, "operator": "b" * 40, "viewer": "c" * 40}
        headers = [f"{method} {path} HTTP/1.0", f"Authorization: Bearer {credentials[role]}", "Connection: close"]
        if body is not None:
            headers += ["Content-Type: application/json", f"Content-Length: {len(payload)}"]
        request_bytes = ("\r\n".join(headers) + "\r\n\r\n").encode() + payload
        server_sock, client_sock = socket.socketpair()
        try:
            client_sock.sendall(request_bytes)
            client_sock.shutdown(socket.SHUT_WR)
            handler = make_handler(self.store, credentials, self.fleet)
            handler.log_message = lambda self, *args: None
            handler(server_sock, ("local", 0), self.FakeServer())
            response = bytearray()
            while b"\r\n\r\n" not in response:
                chunk = client_sock.recv(65536)
                if not chunk:
                    break
                response.extend(chunk)
            head, content = bytes(response).split(b"\r\n\r\n", 1)
            content_length = next(int(line.split(b":", 1)[1]) for line in head.split(b"\r\n") if line.lower().startswith(b"content-length:"))
            while len(content) < content_length:
                content += client_sock.recv(65536)
            status = int(head.split(b"\r\n", 1)[0].split()[1])
            return status, __import__("json").loads(content) if content else None
        finally:
            server_sock.close()
            client_sock.close()

    def test_http_fleet_status_and_role_denial(self):
        status, data = self.request("GET", "/api/machines", "viewer")
        self.assertEqual(status, 200)
        self.assertEqual(len(data["items"]), 2)
        status, data = self.request("POST", "/api/machines", "operator", {"machine_id": "new-machine", "name": "Denied", "adapter_id": "simulation.compact"})
        self.assertEqual(status, 403)
        self.assertEqual(data["error"], "role_not_permitted")

    def test_http_admin_registers_machine_and_operator_cannot_vend(self):
        status, data = self.request("POST", "/api/machines", "admin", {"machine_id": "new-machine", "name": "New", "adapter_id": "simulation.connected"})
        self.assertEqual(status, 201)
        self.assertTrue(data["item"]["simulated"])
        status, data = self.request("POST", "/api/machines/new-machine/commands", "operator", {"request_id": "01234567-89ab-cdef-0123-456789abcdef", "capability": "vend.simulate", "parameters": {"product_id": "water"}})
        self.assertEqual(status, 403)
        self.assertEqual(data["error"], "capability_not_permitted_for_role")

    def test_http_command_response_is_simulated_and_duplicate_is_not_reexecuted(self):
        payload = {"request_id": "01234567-89ab-cdef-0123-456789abcdef", "capability": "vend.simulate", "parameters": {"product_id": "water"}}
        status, first = self.request("POST", "/api/machines/lab-connected-01/commands", "admin", payload)
        self.assertEqual(status, 200)
        self.assertEqual(first["item"]["status"], "confirmed")
        self.assertTrue(first["item"]["simulated"])
        self.assertTrue(first["item"]["verified"])
        status, duplicate = self.request("POST", "/api/machines/lab-connected-01/commands", "admin", payload)
        self.assertEqual(status, 200)
        self.assertTrue(duplicate["item"]["duplicate"])
        self.assertEqual(len(self.fleet.command_history("lab-connected-01")), 1)
        water = next(item for item in self.fleet.resource("lab-connected-01", "inventory.read") if item["product_id"] == "water")
        self.assertEqual(water["stock"], 9)

    def test_status_data_is_explicitly_simulated(self):
        status = simulated_status()
        self.assertEqual(status["connection"], "simulated")
        self.assertFalse(status["hardware_connected"])

    def test_manual_stock_update_is_persisted_and_audited(self):
        product_id, stock = parse_stock_update({"product_id": "water", "stock": 3})
        item = self.store.update_stock(product_id, stock)
        self.assertEqual(item["stock"], 3)
        self.assertEqual(item["source"], "manual_simulation")
        self.assertEqual(self.store.events()[0]["action"], "inventory.stock.set")

    def test_invalid_stock_and_extra_fields_rejected(self):
        for body in (
            {"product_id": "water", "stock": -1},
            {"product_id": "water", "stock": True},
            {"product_id": "unknown", "stock": 2},
            {"product_id": "water", "stock": 2, "price": 0},
        ):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse_stock_update(body)


if __name__ == "__main__":
    unittest.main()

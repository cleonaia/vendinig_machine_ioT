"""Deterministic, in-memory attack/defense exercises for a fictional vending machine."""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field

SECRET = b"training-only-key"
CATALOG = {"water": 150, "snack": 225}


@dataclass(frozen=True)
class Controls:
    validate_order: bool = True
    verify_signature: bool = True
    prevent_replay: bool = True
    recover_safely: bool = True


@dataclass
class Machine:
    controls: Controls
    used_payments: set[str] = field(default_factory=set)
    dispensed: list[str] = field(default_factory=list)
    unauthorized_dispenses: int = 0
    events: list[str] = field(default_factory=list)

    def accept(self, message: dict[str, object]) -> bool:
        order = str(message.get("order", ""))
        payment_id = str(message.get("payment_id", ""))
        amount = message.get("amount")
        signature = str(message.get("signature", ""))

        valid_order = order in CATALOG and type(amount) is int and amount == CATALOG[order]
        valid_signature = hmac.compare_digest(signature, sign(order, amount, payment_id))
        fresh_payment = payment_id not in self.used_payments
        if self.controls.validate_order and not valid_order:
            self.events.append("order_rejected")
            return False
        if self.controls.verify_signature and not valid_signature:
            self.events.append("signature_rejected")
            return False
        if self.controls.prevent_replay and not fresh_payment:
            self.events.append("replay_rejected")
            return False
        if not payment_id:
            self.events.append("missing_payment_rejected")
            return False

        self.used_payments.add(payment_id)
        self.dispensed.append(order)
        if not (valid_order and valid_signature and fresh_payment and payment_id):
            self.unauthorized_dispenses += 1
        self.events.append("dispensed")
        return True

    def disconnect(self) -> None:
        # A simulated power interruption must not create an unpaid pending vend.
        if self.controls.recover_safely:
            self.events.append("disconnect_safe_abort")
        else:
            self.dispensed.append("unknown")
            self.unauthorized_dispenses += 1
            self.events.append("disconnect_unsafe_vend")


def sign(order: str, amount: object, payment_id: str) -> str:
    payload = json.dumps([order, amount, payment_id], separators=(",", ":"))
    return hmac.new(SECRET, payload.encode(), hashlib.sha256).hexdigest()


def paid_message(order: str, payment_id: str) -> dict[str, object]:
    amount = CATALOG[order]
    return {"order": order, "amount": amount, "payment_id": payment_id,
            "signature": sign(order, amount, payment_id)}


def run_scenario(name: str, controls: Controls) -> dict[str, object]:
    machine = Machine(controls)
    attempts: list[dict[str, object]] = []

    def attempt(label: str, message: dict[str, object]) -> None:
        attempts.append({"step": label, "accepted": machine.accept(message)})

    if name == "normal":
        attempt("valid_paid_order", paid_message("water", "pay-001"))
    elif name == "replay":
        message = paid_message("water", "pay-002")
        attempt("first_delivery", message)
        attempt("repeated_delivery", message)
    elif name == "tamper":
        message = paid_message("snack", "pay-003")
        message["amount"] = 1
        attempt("amount_changed_after_signing", message)
    elif name == "invalid-order":
        message = paid_message("water", "pay-004")
        message["order"] = "admin"
        attempt("unknown_product", message)
    elif name == "disconnect":
        machine.disconnect()
    elif name == "chain":
        replay = paid_message("water", "pay-005")
        attempt("replay_chain_first_delivery", replay)
        attempt("replay_chain_duplicate", replay)
        forged = paid_message("snack", "pay-006")
        forged["amount"] = 0
        attempt("tampered_chain_message", forged)
        attempt("unsigned_chain_message", {"order": "snack", "amount": 0,
                                             "payment_id": "pay-007", "signature": ""})
    else:
        raise ValueError(f"Unknown scenario: {name}")

    return {"scenario": name, "objective": "dispense_without_valid_payment",
            "objective_achieved": machine.unauthorized_dispenses > 0, "attempts": attempts,
            "dispensed": machine.dispensed, "events": machine.events,
            "controls": {key: getattr(controls, key) for key in Controls.__dataclass_fields__}}

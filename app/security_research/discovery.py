"""Explicit-scope TCP discovery with conservative service identification.

Only private or loopback IPv4 ranges are accepted. Probes are limited to a
small allowlist of common IoT management ports and perform TCP connect only.
An open port is a service hint, never proof of protocol or device identity.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

ALLOWED_PORTS = {80, 443, 1883, 8883, 502, 8080, 8443}
MAX_ADDRESSES = 64
AUTHORIZED_RANGES = tuple(ipaddress.ip_network(value) for value in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))


@dataclass(frozen=True)
class ServiceObservation:
    address: str
    port: int
    service_hint: str
    protocol: str
    confidence: float
    evidence: str
    observed_at: str
    simulated: bool = False

    def to_dict(self):
        return asdict(self)


def parse_authorized_scope(scope: str) -> tuple[ipaddress.IPv4Network, ...]:
    """Parse operator-provided CIDRs and reject public, IPv6, or broad scope."""
    if not isinstance(scope, str) or not scope.strip():
        raise ValueError("an explicit authorized IPv4 scope is required")
    networks = []
    for raw in scope.split(","):
        network = ipaddress.ip_network(raw.strip(), strict=False)
        if not isinstance(network, ipaddress.IPv4Network):
            raise ValueError("only IPv4 lab scopes are supported")
        if not any(network.subnet_of(allowed) for allowed in AUTHORIZED_RANGES):
            raise ValueError("scope must be loopback or RFC1918 private IPv4")
        if network.num_addresses > MAX_ADDRESSES:
            raise ValueError(f"each scope is limited to {MAX_ADDRESSES} addresses")
        networks.append(network)
    if not networks:
        raise ValueError("empty authorized scope")
    return tuple(networks)


def identify_hint(port: int) -> tuple[str, str, float]:
    mapping = {
        80: ("HTTP management candidate", "HTTP", 0.25),
        443: ("HTTPS management candidate", "HTTPS/TLS", 0.25),
        1883: ("MQTT candidate (unencrypted port)", "MQTT", 0.25),
        8883: ("MQTT over TLS candidate", "MQTT/TLS", 0.25),
        502: ("Modbus TCP candidate", "Modbus/TCP", 0.2),
        8080: ("HTTP alternate-port candidate", "HTTP", 0.2),
        8443: ("HTTPS alternate-port candidate", "HTTPS/TLS", 0.2),
    }
    return mapping.get(port, ("Unknown TCP service", "unknown", 0.05))


def discover(scope: str, ports: Iterable[int] = (80, 443, 1883, 8883, 502, 8080, 8443),
             timeout: float = 0.15) -> list[ServiceObservation]:
    """Perform bounded TCP-connect discovery inside explicit private lab CIDRs."""
    networks = parse_authorized_scope(scope)
    checked_ports = tuple(dict.fromkeys(ports))
    if not checked_ports or any(type(port) is not int or port not in ALLOWED_PORTS for port in checked_ports):
        raise ValueError("ports must be selected from the documented low-impact allowlist")
    if not 0.01 <= timeout <= 1.0:
        raise ValueError("timeout must be from 0.01 to 1.0 seconds")
    targets = [str(address) for network in networks for address in network.hosts()]
    if all(network.prefixlen == 32 for network in networks):
        targets += [str(network.network_address) for network in networks]
    if len(set(targets)) > MAX_ADDRESSES:
        raise ValueError(f"combined scope is limited to {MAX_ADDRESSES} addresses")
    results = []
    for address in dict.fromkeys(targets):
        for port in checked_ports:
            try:
                with socket.create_connection((address, port), timeout=timeout):
                    hint, protocol, confidence = identify_hint(port)
                    results.append(ServiceObservation(
                        address, port, hint, protocol, confidence,
                        f"TCP connection accepted; port-number heuristic only; no protocol handshake performed",
                        datetime.now(timezone.utc).isoformat()))
            except OSError:
                continue
    return results

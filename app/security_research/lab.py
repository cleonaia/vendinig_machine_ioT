"""Synthetic controller profiles for repeatable defensive assessments."""
from __future__ import annotations

from copy import deepcopy

_profiles = [
    {"profile_id": "iot-mqtt-hardened", "device_family": "generic IoT telemetry node",
     "manufacturer": None, "model": None, "protocol_claim": "MQTT 5.0 fixture; not a vending controller",
     "expected_findings": [],
     "mqtt": {"present": True, "tls": True, "authentication": "credentials", "topic_acl": "least_privilege", "strict_schema": True}},
    {"profile_id": "iot-mqtt-insecure", "device_family": "generic IoT telemetry node",
     "manufacturer": None, "model": None, "protocol_claim": "MQTT fixture with deliberately weak policy",
     "expected_findings": ["IOT-MQTT-01", "IOT-MQTT-02", "IOT-MQTT-03", "IOT-MQTT-04"],
     "mqtt": {"present": True, "tls": False, "authentication": "anonymous", "topic_acl": "wildcard", "strict_schema": False}},
    {"profile_id": "vending-api-hardened-example", "device_family": "unattributed vending API fixture",
     "manufacturer": None, "model": None, "protocol_claim": "HTTP API policy fixture; no physical model compatibility claimed",
     "expected_findings": [],
     "http": {"present": True, "tls": True, "authentication": "required", "authorization": "role_and_machine_scoped", "strict_validation": True, "sensitive_data_exposed": False}},
    {"profile_id": "vending-api-insecure", "device_family": "unattributed vending API fixture",
     "manufacturer": None, "model": None, "protocol_claim": "HTTP API fixture with intentionally unsafe control settings",
     "expected_findings": ["IOT-HTTP-01", "IOT-HTTP-02", "IOT-HTTP-03", "IOT-HTTP-04", "IOT-HTTP-05"],
     "http": {"present": True, "tls": False, "authentication": "none", "authorization": "none", "strict_validation": False, "sensitive_data_exposed": True}},
    {"profile_id": "generic-mdb-gateway-unknown", "device_family": "generic vending gateway concept",
     "manufacturer": None, "model": None, "protocol_claim": "MDB/ICP requires a vendor gateway and documented interface; unsupported fixture",
     "expected_findings": [],
     "mqtt": {"present": False}, "http": {"present": False}, "unsupported_protocols": ["MDB/ICP raw peripheral bus"]},
]
LAB_PROFILES = {profile["profile_id"]: profile for profile in _profiles}


def run_profile(profile_id: str) -> dict:
    """Return expected-vs-observed results from a deterministic synthetic fixture."""
    if profile_id not in LAB_PROFILES:
        raise KeyError("unknown laboratory profile")
    profile = deepcopy(LAB_PROFILES[profile_id])
    from app.security_research.assessment import assess_profile
    assessment = assess_profile(profile)
    expected_ids = set(profile.get("expected_findings", ()))
    actual_ids = {finding.finding_id for finding in assessment.findings}
    return {"profile": profile, "simulated": True, "expected_finding_ids": sorted(expected_ids),
            "actual_finding_ids": sorted(actual_ids), "expectations_met": expected_ids == actual_ids,
            "assessment": assessment.to_dict(),
            "limitations": ["All device and control observations are synthetic fixtures.",
                            "No manufacturer or physical vending-machine compatibility is implied."]}

"""Deterministic control reviews for known MQTT and HTTP/API observations."""
from __future__ import annotations

from app.security_research.models import Assessment, Evidence, Finding


def assess_profile(profile: dict) -> Assessment:
    """Evaluate supplied test observations; this is not automatic device fingerprinting."""
    assessment = Assessment(profile["profile_id"], profile["profile_id"], True)
    simulated = True

    def check(check_id, passed, evidence, finding=None):
        assessment.checks[check_id] = {"expected": not passed if finding else True,
                                       "actual": "pass" if passed else "fail",
                                       "evidence": evidence, "simulated": simulated}
        if finding and not passed:
            assessment.findings.append(Finding(
                finding_id=finding[0], title=finding[1], severity=finding[2], impact=finding[3],
                evidence=(Evidence("laboratory_fixture", evidence, simulated=True),),
                false_positive_notes=finding[4], mitigation=finding[5]))

    mqtt = profile.get("mqtt", {})
    if mqtt.get("present"):
        check("mqtt_transport_encryption", mqtt.get("tls") is True,
              f"mqtt.tls={mqtt.get('tls')!r}", ("IOT-MQTT-01", "MQTT transport is not encrypted", "high",
              "Network observers may read telemetry and forge or replay messages if other controls are also weak.",
              "The fixture records TLS disabled; a live assessment must inspect the actual listener and certificate.",
              "Use TLS with certificate validation; restrict broker access to the device and management identities."))
        check("mqtt_authentication", mqtt.get("authentication") == "credentials",
              f"mqtt.authentication={mqtt.get('authentication')!r}", ("IOT-MQTT-02", "MQTT authentication is absent or weak", "high",
              "Unauthenticated clients may access topics permitted by broker policy.",
              "Anonymous access to one broker does not establish topic permissions or impact without ACL evidence.",
              "Require unique credentials or certificates and enforce per-device topic ACLs."))
        check("mqtt_topic_acl", mqtt.get("topic_acl") == "least_privilege",
              f"mqtt.topic_acl={mqtt.get('topic_acl')!r}", ("IOT-MQTT-03", "MQTT topic permissions are overly broad", "high",
              "A compromised identity may read or publish outside its device topics.",
              "Confirm effective ACLs with authorized identities; configuration labels can be inaccurate.",
              "Apply per-device least-privilege ACLs; prohibit wildcard access for device accounts."))
        check("mqtt_message_validation", mqtt.get("strict_schema") is True,
              f"mqtt.strict_schema={mqtt.get('strict_schema')!r}", ("IOT-MQTT-04", "MQTT message validation is insufficient", "medium",
              "Malformed, oversized, replayed, or uncorrelated messages may corrupt state or trigger unsafe logic.",
              "A schema flag alone does not prove code validates payloads; inspect tests and implementation.",
              "Validate bounded versioned schemas, identity, replay keys, correlation and command allowlists."))

    http = profile.get("http", {})
    if http.get("present"):
        check("http_tls", http.get("tls") is True,
              f"http.tls={http.get('tls')!r}", ("IOT-HTTP-01", "HTTP management traffic lacks TLS", "high",
              "Credentials and management data may be observed or altered in transit.",
              "Only assess the management listener and its real TLS termination point.",
              "Use HTTPS with certificate validation; do not send bearer tokens over cleartext HTTP."))
        check("http_authentication", http.get("authentication") == "required",
              f"http.authentication={http.get('authentication')!r}", ("IOT-HTTP-02", "HTTP API does not require authentication", "critical",
              "Unauthenticated users may read or change management data, depending on endpoint permissions.",
              "An unauthenticated root page may be intentional; verify protected API routes separately.",
              "Require authentication on every sensitive route and reject missing or invalid credentials."))
        check("http_authorization", http.get("authorization") == "role_and_machine_scoped",
              f"http.authorization={http.get('authorization')!r}", ("IOT-HTTP-03", "API authorization is not sufficiently scoped", "high",
              "Users may perform operations or access machines beyond their assigned role and scope.",
              "Fixture policy does not establish runtime enforcement; exercise each role and resource boundary.",
              "Enforce capability- and machine-scoped authorization on every read and write route."))
        check("http_input_validation", http.get("strict_validation") is True,
              f"http.strict_validation={http.get('strict_validation')!r}", ("IOT-HTTP-04", "API input validation is insufficient", "medium",
              "Malformed or ambiguous inputs may cause inconsistent state or unsafe downstream operations.",
              "A profile flag needs corroborating negative tests against the concrete API.",
              "Reject unknown fields, duplicate JSON keys, invalid types, oversized bodies and non-finite values."))
        check("http_data_exposure", http.get("sensitive_data_exposed") is False,
              f"http.sensitive_data_exposed={http.get('sensitive_data_exposed')!r}", ("IOT-HTTP-05", "Sensitive data may be exposed by the API", "high",
              "Tokens, payment data, or internal configuration in responses can enable account or device compromise.",
              "Fixture evidence is synthetic; verify real response bodies and redact secrets before collection.",
              "Minimize responses, redact secrets, disable caching for private data, and never store card authentication data."))
    return assessment

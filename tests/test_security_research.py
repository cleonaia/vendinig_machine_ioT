from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.security_research.assessment import assess_profile
from app.security_research.discovery import discover, identify_hint, parse_authorized_scope
from app.security_research.lab import LAB_PROFILES, run_profile
from app.security_research.report import write_markdown, write_report


class DiscoveryTests(unittest.TestCase):
    def test_scope_requires_explicit_small_private_ipv4(self):
        self.assertEqual(str(parse_authorized_scope("127.0.0.1/32")[0]), "127.0.0.1/32")
        for scope in ("", "8.8.8.8/32", "10.0.0.0/8", "169.254.1.1/32", "::1/128"):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                parse_authorized_scope(scope)

    def test_port_hint_is_low_confidence_and_not_identity(self):
        hint, protocol, confidence = identify_hint(1883)
        self.assertEqual(protocol, "MQTT")
        self.assertLess(confidence, 0.5)
        self.assertIn("candidate", hint)

    def test_discovery_records_tcp_evidence_and_rejects_unapproved_ports(self):
        class OpenSocket:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
        with patch("app.security_research.discovery.socket.create_connection", return_value=OpenSocket()):
            result = discover("127.0.0.1/32", ports=(1883,))
        self.assertEqual(len(result), 1)
        self.assertIn("TCP connection accepted", result[0].evidence)
        self.assertFalse(result[0].simulated)
        with self.assertRaises(ValueError):
            discover("127.0.0.1/32", ports=(23,))


class SecurityAssessmentTests(unittest.TestCase):
    def test_every_fixture_matches_independent_expected_findings(self):
        for profile_id in LAB_PROFILES:
            with self.subTest(profile=profile_id):
                result = run_profile(profile_id)
                self.assertTrue(result["simulated"])
                self.assertTrue(result["expectations_met"])
                self.assertEqual(result["expected_finding_ids"], result["actual_finding_ids"])
                for finding in result["assessment"]["findings"]:
                    self.assertTrue(all(evidence["simulated"] for evidence in finding["evidence"]))

    def test_hardened_profile_has_no_findings_and_insecure_profile_has_evidence_and_mitigations(self):
        secure = run_profile("iot-mqtt-hardened")["assessment"]
        insecure = run_profile("iot-mqtt-insecure")["assessment"]
        self.assertEqual(secure["findings"], [])
        self.assertEqual(len(insecure["findings"]), 4)
        self.assertTrue(all(item["evidence"] and item["false_positive_notes"] and item["mitigation"]
                            for item in insecure["findings"]))

    def test_reports_are_reproducible_and_include_limitations(self):
        result = run_profile("vending-api-insecure")
        with tempfile.TemporaryDirectory() as tmp:
            json_path = write_report(result, Path(tmp) / "out" / "report.json")
            md_path = write_markdown(result, Path(tmp) / "out" / "report.md")
            self.assertIn('"expectations_met": true', json_path.read_text())
            markdown = md_path.read_text()
            self.assertIn("False-positive considerations", markdown)
            self.assertIn("synthetic fixtures", markdown)


if __name__ == "__main__":
    unittest.main()

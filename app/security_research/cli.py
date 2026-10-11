"""Command line entry point for authorized discovery and synthetic lab runs."""
from __future__ import annotations

import argparse
import json

from app.security_research.discovery import discover
from app.security_research.lab import LAB_PROFILES, run_profile
from app.security_research.report import write_markdown, write_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    lab = sub.add_parser("lab", help="assess one deterministic synthetic profile")
    lab.add_argument("--profile", choices=sorted(LAB_PROFILES), required=True)
    lab.add_argument("--json", dest="json_path")
    lab.add_argument("--markdown", dest="markdown_path")
    scan = sub.add_parser("discover", help="bounded TCP discovery inside authorized private IPv4 scope")
    scan.add_argument("--authorized-scope", required=True, help="operator-authorized RFC1918/loopback CIDR(s), comma separated")
    scan.add_argument("--ports", default="80,443,1883,8883,502,8080,8443")
    args = parser.parse_args(argv)
    if args.command == "lab":
        result = run_profile(args.profile)
        print(json.dumps(result, indent=2, sort_keys=True))
        if args.json_path:
            write_report(result, args.json_path)
        if args.markdown_path:
            write_markdown(result, args.markdown_path)
        return 0 if result["expectations_met"] else 1
    ports = [int(item.strip()) for item in args.ports.split(",") if item.strip()]
    observations = [item.to_dict() for item in discover(args.authorized_scope, ports)]
    print(json.dumps({"authorized_scope": args.authorized_scope, "simulated": False,
                      "observations": observations,
                      "limitations": ["TCP connect only; no protocol handshake or authentication attempt.",
                                      "Port-number hints are low-confidence and do not establish device identity."]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run the local vending-machine security lab scenarios."""

from __future__ import annotations

import argparse
import json

from scenarios.lab import Controls, run_scenario

SCENARIOS = ("normal", "replay", "tamper", "invalid-order", "disconnect", "chain")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default=None,
                        help="scenario to run (default: run all)")
    parser.add_argument("--profile", choices=("hardened", "vulnerable"),
                        default="hardened", help="simulated control configuration")
    parser.add_argument("--json", action="store_true", help="print JSON results")
    args = parser.parse_args()

    controls = Controls() if args.profile == "hardened" else Controls(False, False, False, False)
    names = [args.scenario] if args.scenario else list(SCENARIOS)
    results = [run_scenario(name, controls) for name in names]
    if args.json:
        print(json.dumps(results, indent=2))
        return
    for result in results:
        outcome = "OBJETIVO ALCANZADO" if result["objective_achieved"] else "bloqueado"
        print(f"[{result['scenario']}] {outcome}")
        print(f"  intentos: {len(result['attempts'])}; dispensados: {result['dispensed']}")
        print(f"  eventos: {', '.join(result['events']) or 'ninguno'}")


if __name__ == "__main__":
    main()

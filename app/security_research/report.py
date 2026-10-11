"""Human-readable and JSON export of reproducible assessment records."""
from __future__ import annotations

import json
from pathlib import Path


def write_report(result: dict, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def render_markdown(result: dict) -> str:
    assessment = result["assessment"]
    lines = [f"# Security assessment: {assessment['subject_id']}", "",
             f"- Profile: `{assessment['profile']}`", f"- Simulated: `{str(result['simulated']).lower()}`",
             f"- Expectations met: `{str(result['expectations_met']).lower()}`", "",
             "## Findings", ""]
    if not assessment["findings"]:
        lines.append("No findings in the evaluated controls.")
    for finding in assessment["findings"]:
        lines += [f"### {finding['finding_id']} — {finding['title']}", "",
                  f"- Severity: **{finding['severity']}**", f"- Impact: {finding['impact']}",
                  f"- Evidence: {', '.join(item['observation'] for item in finding['evidence'])}",
                  f"- False-positive considerations: {finding['false_positive_notes']}",
                  f"- Mitigation: {finding['mitigation']}", ""]
    lines += ["## Check results", "", "| Check | Result | Evidence |", "|---|---|---|"]
    for name, check in assessment["checks"].items():
        lines.append(f"| {name} | {check['actual']} | {check['evidence']} |")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in result.get("limitations", []))
    return "\n".join(lines) + "\n"


def write_markdown(result: dict, destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_markdown(result), encoding="utf-8")
    return path

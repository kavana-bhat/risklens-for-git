"""
ci_comment.py  (NEW)

Analyses a whole pull request (base...head) and writes a Markdown comment:
risk level, why, test results and the test-gap plan.

    python ci_comment.py --repo . --base origin/main --head HEAD --out risk-comment.md
    python ci_comment.py ... --fail-on HIGH      # exit code 1 when risk is HIGH

Used by .github/workflows/risk-check.yml
"""

import argparse
import sys

from analysis import analyze
from gap_detector import build_plan, build_skeletons

ICON = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟢"}
ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def short(node_id):
    path, name = node_id.split("::", 1)
    return f"`{path}` › `{name}`"


def build_comment(result):
    f, d, t, s = (result[k] for k in ("features", "details", "tests", "score"))
    level = s["level"]
    lines = [f"## {ICON.get(level, '⚪')} Change risk: **{level}**", ""]

    if s["model"] == "v2":
        lines.append(
            f"Model risk score **{s['score'] * 100:.1f}%** "
            f"(typical change in training data: {s['base_rate'] * 100:.1f}%). "
            "Bands are relative: HIGH ≈ riskiest 15% of code-changing commits.")
    lines += [
        "",
        "| files | +lines | -lines | functions changed | blast radius | untested |",
        "|---|---|---|---|---|---|",
        f"| {f['files_changed']} | {f['insertions']} | {f['deletions']} | "
        f"{f['functions_changed']} | {f['blast_radius']} | {f['untested_blast']} |",
        "",
    ]

    reasons = []
    if t["failures"]:
        reasons.append(f"{t['failures']} relevant test(s) failed")
    for feat, value, delta in s["contributions"]:
        sign = "+" if delta > 0 else "−"
        reasons.append(f"`{feat}` = {value} ({sign}{abs(delta) * 100:.1f} pts)")
    for note in s["notes"]:
        reasons.append(note)
    if reasons:
        lines += ["**Why**"] + [f"- {r}" for r in reasons] + [""]

    if t["selected"]:
        lines.append(f"**Tests run** ({t['passed']} passed, {t['failed']} failed)")
        for e in t["details"]:
            mark = "✅" if e["status"] == "passed" else "❌"
            lines.append(f"- {mark} `{e['file']}`")
        lines.append("")

    untested = d["untested"]
    if untested:
        plan = build_plan(d)
        changed = set(d["changed_ids"])
        lines.append(f"**Test gap: {len(untested)} of {f['blast_radius']} "
                     "functions in the blast radius have no test reaching them**")
        for n in untested[:10]:
            tag = "changed" if n in changed else "dependent"
            lines.append(f"- {short(n)} _({tag})_")
        if len(untested) > 10:
            lines.append(f"- … and {len(untested) - 10} more")
        if plan["direct"]:
            lines.append(
                f"\nUnit tests for the {len(plan['direct'])} changed function(s) "
                f"would make {plan['reached_by_direct']} of "
                f"{plan['untested_total']} test-reachable.")
        stubs = build_skeletons(d, limit=3)
        if stubs:
            lines += ["", "<details><summary>Suggested test stubs</summary>", ""]
            for st in stubs:
                lines += [f"`{st['file']}`", "```python", st["code"], "```"]
            lines.append("</details>")
    elif f["blast_radius"]:
        lines.append("✅ Every function in the blast radius is reachable from a test.")

    lines += ["", "<sub>Static analysis: “reachable” means a call path exists, "
              "not that assertions are meaningful.</sub>"]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--out", default="risk-comment.md")
    ap.add_argument("--fail-on", choices=["MEDIUM", "HIGH"])
    ap.add_argument("--no-tests", action="store_true")
    a = ap.parse_args()

    result = analyze(a.repo, a.head, run_test_suite=not a.no_tests, base_ref=a.base)
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(build_comment(result))
    level = result["score"]["level"]
    print(f"Risk: {level}  -> {a.out}")
    if a.fail_on and ORDER[level] >= ORDER[a.fail_on]:
        sys.exit(1)


if __name__ == "__main__":
    main()

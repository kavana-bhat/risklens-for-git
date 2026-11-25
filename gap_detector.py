"""
gap_detector.py  (NEW)

Test-gap detection with an actionable plan.

Other tools stop at "this change is risky". This module answers
"what should I do about it?":

  1. UNTESTED BLAST RADIUS - functions that the change touches, or that
     (transitively) call something it touches, which NO test can reach.
  2. TEST PLAN - the smallest set of tests that would close the gap,
     computed exactly on the call graph (not guessed by a model):
        direct   : unit tests for the changed-but-untested functions
        shortcut : the fewest entry points a single test could call to
                   reach every untested function (greedy set cover)
  3. SKELETONS - ready-to-fill pytest stubs for the direct tests.

Everything here is static analysis: "reachable from a test" means a call
path exists in the code, not that assertions are meaningful.
"""

import posixpath

from callgraph import MODULE_UNIT, is_test_file


def _reach_into(graph, node, targets):
    return graph._reach([node], reverse=False) & targets


def build_plan(details, max_shortcuts=5):
    graph = details["graph"]
    untested = set(details["untested"])
    changed_untested = sorted(details["untested_changed"])

    # --- direct plan: a unit test per changed-but-untested function ----
    direct = [n for n in changed_untested
              if graph.nodes[n]["qual"] != MODULE_UNIT]
    covered_by_direct = set()
    for n in direct:
        covered_by_direct |= _reach_into(graph, n, untested)
    residual_after_direct = untested - covered_by_direct

    # --- shortcut: greedy set cover over the untested functions --------
    reach = {n: _reach_into(graph, n, untested) for n in untested}
    remaining, shortcut = set(untested), []
    while remaining and len(shortcut) < max_shortcuts:
        best = max(
            reach,
            key=lambda n: (len(reach[n] & remaining),
                           n in details["changed_ids"], n))
        gain = reach[best] & remaining
        if not gain:
            break
        shortcut.append({"entry": best, "newly_reached": sorted(gain)})
        remaining -= gain

    return {
        "untested_total": len(untested),
        "direct": direct,
        "reached_by_direct": len(covered_by_direct),
        "residual_after_direct": sorted(residual_after_direct),
        "shortcut": shortcut,
        "shortcut_complete": not remaining,
    }


# ------------------------------------------------------------------
# Pytest skeletons
# ------------------------------------------------------------------

def _test_location(graph, module_path):
    folder = posixpath.dirname(module_path)
    test_dirs = {posixpath.dirname(p) for p in graph.files if is_test_file(p)}
    if folder in test_dirs:
        target_dir = folder
    elif any(d == "tests" or d.endswith("/tests") for d in test_dirs):
        target_dir = sorted(d for d in test_dirs
                            if d == "tests" or d.endswith("/tests"))[0]
    else:
        target_dir = folder
    name = "test_" + posixpath.basename(module_path)
    return posixpath.join(target_dir, name) if target_dir else name


def skeleton(graph, node_id):
    meta = graph.nodes[node_id]
    path, qual = meta["path"], meta["qual"]
    args = [a for a in meta["args"] if a not in ("self", "cls")]
    module = graph.import_name(path)
    call_args = ", ".join(f"{a}=..." for a in args)
    test_file = _test_location(graph, path)

    if "." in qual:
        cls, method = qual.rsplit(".", 1)
        cls_name = cls.split(".")[-1]
        imp = f"from {module} import {cls_name}"
        body = (f"    obj = {cls_name}()   # TODO: constructor arguments\n"
                f"    result = obj.{method}({call_args})   # TODO: realistic input\n")
        name = f"test_{cls_name.lower()}_{method}"
    else:
        imp = f"from {module} import {qual}"
        body = f"    result = {qual}({call_args})   # TODO: realistic input\n"
        name = f"test_{qual}"

    code = (f"{imp}\n\n\ndef {name}():\n{body}"
            f"    assert result == ...   # TODO: expected value\n")
    return {"target": node_id, "file": test_file,
            "exists": test_file in graph.files, "code": code}


def build_skeletons(details, limit=5):
    graph = details["graph"]
    plan = build_plan(details)
    return [skeleton(graph, n) for n in plan["direct"][:limit]]


# ------------------------------------------------------------------
# Console report (used by main.py)
# ------------------------------------------------------------------

def _short(node_id):
    return node_id.replace("::", " :: ")


def print_gap_report(details, features):
    graph = details["graph"]
    blast, untested = details["blast"], details["untested"]

    print("\n==========================================")
    print("          TEST GAP ANALYSIS")
    print("==========================================")

    if not blast:
        print("\nNo changed Python functions - nothing to check.")
        print("==========================================")
        return

    tested = len(blast) - len(untested)
    print(f"\nBlast radius : {len(blast)} functions "
          f"(changed + everything that calls them)")
    print(f"Test-reachable: {tested}")
    print(f"UNTESTED      : {len(untested)}")

    if details["tests_hit"]:
        files = sorted({graph.nodes[t]["path"] for t in details["tests_hit"]})
        print("\nTests that already exercise the changed code:")
        for f in files:
            print("  ✓", f)

    if not untested:
        print("\n✓ Every function in the blast radius is reachable from a test.")
        print("==========================================")
        return

    changed = set(details["changed_ids"])
    print("\nUntested functions in the blast radius:")
    for n in untested[:12]:
        tag = "CHANGED  " if n in changed else "dependent"
        print(f"  ✗ [{tag}] {_short(n)}")
    if len(untested) > 12:
        print(f"  ... and {len(untested) - 12} more")

    plan = build_plan(details)
    print("\nHOW TO CLOSE THE GAP")
    print("--------------------")
    if plan["direct"]:
        print(f"Option A - unit tests for the {len(plan['direct'])} changed "
              f"function(s):")
        for n in plan["direct"][:8]:
            print("   •", _short(n))
        left = len(plan["residual_after_direct"])
        print(f"   -> makes {plan['reached_by_direct']} of "
              f"{plan['untested_total']} untested functions test-reachable"
              + (f" ({left} would remain)" if left else " (gap fully closed)"))
    if plan["shortcut"]:
        n = len(plan["shortcut"])
        label = "fewest" if plan["shortcut_complete"] else "first"
        print(f"Option B - {label} {n} test entry point(s) that reach the rest:")
        for step in plan["shortcut"]:
            print(f"   • call {_short(step['entry'])} "
                  f"(reaches {len(step['newly_reached'])} more)")

    stubs = build_skeletons(details, limit=3)
    if stubs:
        print("\nSUGGESTED TEST STUBS")
        print("--------------------")
        for s in stubs:
            verb = "add to existing" if s["exists"] else "create"
            print(f"# {verb}: {s['file']}")
            print(s["code"])
    print("==========================================")

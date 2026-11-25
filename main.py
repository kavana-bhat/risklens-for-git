"""
main.py  (MODIFIED)

Same interactive flow as before (pick a repo, pick a commit, get a report).
What changed:
  * the diff / dependency / function / feature logic now lives in
    commit_features.py + callgraph.py (shared with training, so the model is
    trained on exactly what it is asked to predict)
  * dependency graph is built automatically from the whole repo at that
    commit (before: hard-coded to the "sample-project" folder)
  * tests are chosen by call graph AND by name, and run against the
    analysed commit, not the working folder
  * new TEST GAP ANALYSIS section
  * non-interactive mode:  python main.py --repo . --commit HEAD
"""

import argparse

from git import Repo

from analysis import analyze
from gap_detector import print_gap_report
from risk_explanation import explain_risk
from risk_report import print_risk_report
from save_report import save_analysis


def parse_args():
    ap = argparse.ArgumentParser(description="Code Change Risk Analyzer")
    ap.add_argument("--repo", help="path to the Git repository")
    ap.add_argument("--commit", help="commit id / ref to analyse")
    ap.add_argument("--no-tests", action="store_true",
                    help="skip running the selected tests")
    return ap.parse_args()


def main():
    args = parse_args()

    # =================================
    # PROGRAM HEADER
    # =================================

    print("===================================")
    print("     CODE CHANGE RISK ANALYZER")
    print("===================================")

    # =================================
    # 1. OPEN GIT REPOSITORY
    # =================================

    repo_path = args.repo or input("\nEnter Git repository path: ").strip()

    try:
        repo = Repo(repo_path)
    except Exception as error:
        print("\nCould not open repository.")
        print("Error:", error)
        return

    # =================================
    # 2. SHOW AVAILABLE COMMITS
    # =================================

    if not args.commit:
        print("\nAVAILABLE COMMITS")
        print("-----------------")
        for commit_item in repo.iter_commits(max_count=30):
            print(commit_item.hexsha[:7], "-",
                  commit_item.message.strip().split("\n")[0])

    # =================================
    # 3. SELECT COMMIT
    # =================================

    commit_id = args.commit or input("\nEnter commit ID to analyze: ").strip()

    try:
        result = analyze(repo_path, commit_id, run_test_suite=not args.no_tests)
    except Exception as error:
        print("\nCould not analyse this commit.")
        print("Error:", error)
        return

    commit = result["commit"]
    f = result["features"]
    d = result["details"]
    t = result["tests"]
    s = result["score"]

    # =================================
    # 4-11. CHANGE, DEPENDENCY, IMPACT AND FUNCTION ANALYSIS
    # =================================

    print("\nCHANGE ANALYSIS")
    print("---------------")
    print("Commit:", commit.hexsha[:7], "-",
          commit.message.strip().split("\n")[0])
    print("Files changed:", f["files_changed"],
          "| +", f["insertions"], "| -", f["deletions"])

    print("\nCHANGED FUNCTIONS")
    print("-----------------")
    if d["changed"]:
        for path, groups in d["changed"].items():
            for kind in ("added", "modified", "removed"):
                for name in groups[kind]:
                    print(f"  {kind:9s} {path} :: {name}")
    else:
        print("- No Python function changes")

    print("\nIMPACT ANALYSIS")
    print("---------------")
    print("Affected files:", f["affected_files"])
    for path in d["affected_files"]:
        print("  -", path)
    print("Function blast radius:", f["blast_radius"])

    if d["unparsable"]:
        print("\n⚠ Could not parse (syntax error), ignored in the graph:")
        for path in d["unparsable"]:
            print("  -", path)

    # =================================
    # 12-15. TEST SELECTION, EXECUTION, SUMMARY
    # =================================

    print("\nRELEVANT TEST SELECTION")
    print("-----------------------")
    if t["selected"]:
        for test in t["selected"]:
            print("✓", test, f"({t['reason'].get(test, '')})")
    else:
        print("- No directly related tests found")

    print("\nTEST EXECUTION (on the analysed commit)")
    print("---------------------------------------")
    for entry in t["details"]:
        mark = "✓" if entry["status"] == "passed" else "✗"
        print(mark, entry["file"], "-", entry["status"].upper())

    print("\nTEST SUMMARY")
    print("------------")
    print("Relevant tests:", t["relevant"])
    print("Passed:", t["passed"])
    print("Failed:", t["failed"])

    # =================================
    # 16. ML RISK PREDICTION
    # =================================

    extra = dict(f, model=s["model"], base_rate=s.get("base_rate", 0))

    # =================================
    # 17. FINAL RISK REPORT
    # =================================

    print_risk_report(
        commit.hexsha[:7], commit.message.strip(),
        f["files_changed"], f["insertions"], f["deletions"],
        f["affected_files"], f["functions_changed"],
        t["failures"], s["level"], s["score"], extra=extra,
    )

    # =================================
    # 18. RISK EXPLANATION
    # =================================

    explain_risk(
        s["level"], f["files_changed"], f["insertions"], f["deletions"],
        f["affected_files"], f["functions_changed"], t["failures"],
        contributions=s["contributions"], notes=s["notes"],
    )

    # =================================
    # 18b. TEST GAP ANALYSIS  (NEW)
    # =================================

    print_gap_report(d, f)

    # =================================
    # 19. SAVE ANALYSIS
    # =================================

    save_analysis(
        commit.hexsha[:7], commit.message.strip().split("\n")[0],
        f["files_changed"], f["insertions"], f["deletions"],
        f["affected_files"], f["functions_changed"], t["failures"],
        s["level"], s["score"], extra=extra,
    )

    print("\n===================================")
    print("          ANALYSIS COMPLETE")
    print("===================================")


if __name__ == "__main__":
    main()

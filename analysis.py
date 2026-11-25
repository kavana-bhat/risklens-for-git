"""
analysis.py  (NEW)

The whole pipeline as one function, so the interactive CLI (main.py), the
CI bot (ci_comment.py) and tests all share exactly the same logic.

    commit -> features -> test selection -> test run -> risk score
"""

from git import Repo

from commit_features import extract_features
from ml_model import score_change
from snapshot_runner import run_tests, select_tests


def analyze(repo_path, commit_ref="HEAD", run_test_suite=True, base_ref=None):
    """
    base_ref (optional): analyse everything between merge-base(base, commit)
    and commit - i.e. a whole pull request - instead of a single commit.
    """
    repo = Repo(repo_path)
    commit = repo.commit(commit_ref)
    parent = None
    if base_ref:
        bases = repo.merge_base(repo.commit(base_ref), commit)
        if not bases:
            raise ValueError("No common ancestor with " + base_ref)
        parent = bases[0]
    elif not commit.parents:
        raise ValueError("This commit has no parent, so there is no change to analyse.")

    features, details = extract_features(repo, commit, parent=parent)

    tests = {"relevant": 0, "passed": 0, "failed": 0, "failures": 0, "details": []}
    selected, reason = select_tests(
        details, details["changed_files"], details["affected_files"])
    if run_test_suite:
        tests = run_tests(repo, commit, selected)
    tests["selected"] = selected
    tests["reason"] = reason

    score = score_change(features, test_failures=tests["failures"])
    return {
        "repo": repo,
        "commit": commit,
        "features": features,
        "details": details,
        "tests": tests,
        "score": score,
    }


from git import Repo

from analysis import analyze
from ci_comment import build_comment
from commit_features import ALL_FEATURES, extract_features
from gap_detector import build_plan, build_skeletons


def test_features_for_the_coupon_commit(demo_repo):
    repo = Repo(demo_repo)
    feats, details = extract_features(repo, repo.head.commit)
    assert set(feats) == set(ALL_FEATURES)              # same schema as training data
    assert feats["blast_radius"] == 6
    assert feats["untested_changed"] == 3
    assert "tests/test_checkout.py::test_checkout_simple" in details["tests_hit"]


def test_plan_closes_the_gap_exactly(demo_repo):
    repo = Repo(demo_repo)
    _, details = extract_features(repo, repo.head.commit)
    plan = build_plan(details)
    assert len(plan["direct"]) == 3
    assert plan["residual_after_direct"] == []          # unit tests would close it fully
    assert plan["shortcut_complete"] and len(plan["shortcut"]) == 1


def test_generated_stubs_are_valid_python(demo_repo):
    repo = Repo(demo_repo)
    _, details = extract_features(repo, repo.head.commit)
    stubs = build_skeletons(details)
    assert stubs
    for s in stubs:
        compile(s["code"], s["file"], "exec")           # raises on bad syntax


def test_covering_the_gap_removes_it(demo_repo, tmp_path):
    """Add the suggested direct tests for real and re-run the analysis."""
    import shutil
    import subprocess
    work = tmp_path / "copy"
    shutil.copytree(demo_repo, work)
    (work / "tests" / "test_coupon.py").write_text(
        "from shop.checkout import checkout_with_coupon\n"
        "def test_cwc():\n    assert checkout_with_coupon([100], 'SAVE10')\n")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-qm", "Add coupon tests"], cwd=work, check=True)
    repo = Repo(str(work))
    # analyse the earlier coupon commit's changes, but with the new tests present
    feats, details = extract_features(repo, repo.head.commit, parent=repo.commit("HEAD~2"))
    assert feats["untested_blast"] == 0


def test_end_to_end_and_pr_comment(demo_repo):
    result = analyze(demo_repo, "HEAD", base_ref="HEAD~2")
    assert result["score"]["level"] in {"LOW", "MEDIUM", "HIGH"}
    assert result["tests"]["failures"] == 0
    md = build_comment(result)
    assert "Test gap" in md and "apply_coupon" in md


def test_failing_test_forces_high(demo_repo, tmp_path):
    import shutil
    import subprocess
    work = tmp_path / "failing"
    shutil.copytree(demo_repo, work)
    (work / "tests" / "test_checkout.py").write_text(
        "from shop.checkout import checkout\n"
        "def test_checkout_simple():\n    assert checkout([100])['status'] == 'nope'\n")
    subprocess.run(["git", "add", "-A"], cwd=work, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit",
                    "-qm", "Break a test"], cwd=work, check=True)
    result = analyze(str(work), "HEAD")
    assert result["tests"]["failures"] >= 1
    assert result["score"]["level"] == "HIGH"

import subprocess

from git import Repo

from mine_history import inducing_commits, is_fix_commit


def run(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   cwd=cwd, check=True, capture_output=True)


def test_szz_blames_the_commit_that_wrote_the_buggy_line(tmp_path):
    run(tmp_path, "init", "-q")
    (tmp_path / "calc.py").write_text("def div(a, b):\n    return a / b\n\n\ndef keep():\n    return 1\n")
    run(tmp_path, "add", "-A"); run(tmp_path, "commit", "-qm", "Add calc")

    (tmp_path / "calc.py").write_text("def div(a, b):\n    return a // b\n\n\ndef keep():\n    return 1\n")
    run(tmp_path, "add", "-A"); run(tmp_path, "commit", "-qm", "Use integer division")
    buggy = Repo(str(tmp_path)).head.commit.hexsha

    (tmp_path / "calc.py").write_text("def div(a, b):\n    return a / b\n\n\ndef keep():\n    return 1\n")
    run(tmp_path, "add", "-A"); run(tmp_path, "commit", "-qm", "Fix wrong division result")

    repo = Repo(str(tmp_path))
    fix = repo.head.commit
    assert is_fix_commit(fix)
    assert inducing_commits(repo, fix) == {buggy}


def test_fix_detection_ignores_docs_and_typos():
    class C:  # minimal stand-in for a commit
        def __init__(self, m): self.message = m
    assert is_fix_commit(C("Fix crash when input is empty"))
    assert not is_fix_commit(C("Fix typo in docs"))
    assert not is_fix_commit(C("Add new feature"))

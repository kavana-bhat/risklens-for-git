"""
mine_history.py  (NEW - replaces the heuristic collect_history.py)

Builds a training set from the REAL history of any Git repository.

Old approach (collect_history.py): the "risk" label was a formula over
files+insertions+deletions, so the model only re-learned that formula.

New approach: SZZ-lite labelling (the standard idea in defect-prediction
research, Sliwerski/Zimmermann/Zeller):
  1. find bug-fix commits (message says fix/bug/crash/regression/...)
  2. for each line the fix deleted or changed, `git blame` the parent
  3. the commit that introduced that line is "defect-inducing"  -> label 1

Features come from commit_features.extract_features(), exactly as at
prediction time.

Usage:
    python mine_history.py <repo_path> [--max-commits 700] [--out mined_training_data.csv]
Run it on several repos; rows are appended to the same CSV.
"""

import argparse
import csv
import os
import re
import sys
import time

from git import Repo

from callgraph import is_ignored, is_test_file
from commit_features import ALL_FEATURES, extract_features

FIX_RE = re.compile(
    r"\b(fix(es|ed)?|bug(fix)?|hotfix|crash(es)?|regress(ion|ed)?|"
    r"revert|incorrect(ly)?|broken|wrong)\b", re.I)
NOT_A_CODE_FIX_RE = re.compile(
    r"\b(typo|docs?|documentation|changelog|readme|ci|lint|format(ting)?|"
    r"pre-commit|release|bump|version)\b", re.I)
HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
SHA_RE = re.compile(r"^([0-9a-f]{40}) \d+ \d+")

MAX_RANGES_PER_FILE = 25
HOLDOUT_FRACTION = 0.08   # newest commits have had no time to be "fixed" yet


def is_fix_commit(commit):
    msg = commit.message.strip().split("\n")[0]
    return bool(FIX_RE.search(msg)) and not NOT_A_CODE_FIX_RE.search(msg)


def inducing_commits(repo, fix):
    """SZZ-lite: shas that introduced lines the fix commit removed/changed."""
    parent = fix.parents[0]
    blamed = set()
    for item in parent.diff(fix, M=True):
        path = item.a_path
        if (not path or not item.b_path or not path.endswith(".py")
                or is_test_file(path) or is_ignored(path)):
            continue
        try:
            patch = repo.git.diff(
                parent.hexsha, fix.hexsha, "-U0", "-M", "--", item.b_path)
        except Exception:
            continue
        ranges = []
        for line in patch.splitlines():
            m = HUNK_RE.match(line)
            if m:
                start = int(m.group(1))
                length = int(m.group(2)) if m.group(2) is not None else 1
                if length > 0:                 # pure insertions have no old lines
                    ranges.append((start, start + length - 1))
        for lo, hi in ranges[:MAX_RANGES_PER_FILE]:
            try:
                out = repo.git.blame(
                    "-w", "--line-porcelain", "-L", f"{lo},{hi}",
                    parent.hexsha, "--", path)
            except Exception:
                continue
            for line in out.splitlines():
                m = SHA_RE.match(line)
                if m:
                    blamed.add(m.group(1))
    return blamed


def mine(repo_path, max_commits, out_file, label=None):
    repo = Repo(repo_path)
    name = label or os.path.basename(os.path.abspath(repo_path))

    commits = [c for c in repo.iter_commits()
               if len(c.parents) == 1][:max_commits]
    commits.reverse()                                   # oldest -> newest
    index = {c.hexsha: i for i, c in enumerate(commits)}
    print(f"[{name}] {len(commits)} commits to analyse")

    # ---- 1. labels via SZZ-lite -----------------------------------
    t0 = time.time()
    inducing = set()
    fixes = [c for c in commits if is_fix_commit(c)]
    for k, fix in enumerate(fixes, 1):
        for sha in inducing_commits(repo, fix):
            # the bug-introducing commit must be older than the fix
            if sha in index and index[sha] < index[fix.hexsha]:
                inducing.add(sha)
        if k % 50 == 0:
            print(f"  blamed {k}/{len(fixes)} fix commits")
    print(f"[{name}] {len(fixes)} fix commits -> "
          f"{len(inducing)} defect-inducing commits "
          f"({time.time() - t0:.0f}s)")

    # ---- 2. features ----------------------------------------------
    cutoff = int(len(commits) * (1 - HOLDOUT_FRACTION))
    cache, author_count, rows = {}, {}, []
    t0 = time.time()
    for i, c in enumerate(commits):
        email = c.author.email or c.author.name
        exp = author_count.get(email, 0)
        author_count[email] = exp + 1
        if i >= cutoff:
            continue                                   # not enough future to label
        try:
            feats, _ = extract_features(repo, c, cache, author_exp=exp)
        except Exception as err:                       # one bad commit must not kill the run
            print("  skip", c.hexsha[:7], type(err).__name__)
            continue
        rows.append({
            "repo": name,
            "sha": c.hexsha[:10],
            "date": c.committed_date,
            **feats,
            "defect_inducing": int(c.hexsha in inducing),
        })
        if (i + 1) % 100 == 0:
            print(f"  features {i + 1}/{cutoff}  ({time.time() - t0:.0f}s)")

    # ---- 3. write -------------------------------------------------
    columns = ["repo", "sha", "date"] + ALL_FEATURES + ["defect_inducing"]
    exists = os.path.exists(out_file)
    with open(out_file, "a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=columns)
        if not exists:
            w.writeheader()
        w.writerows(rows)
    pos = sum(r["defect_inducing"] for r in rows)
    print(f"[{name}] wrote {len(rows)} rows "
          f"({pos} defect-inducing = {100 * pos / max(len(rows), 1):.1f}%) -> {out_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("--max-commits", type=int, default=700)
    ap.add_argument("--out", default="mined_training_data.csv")
    ap.add_argument("--label", default=None)
    a = ap.parse_args()
    mine(a.repo, a.max_commits, a.out, a.label)

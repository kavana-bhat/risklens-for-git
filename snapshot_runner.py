"""
snapshot_runner.py  (NEW)

Runs pytest against the code AS IT WAS AT THE ANALYSED COMMIT.

The original main.py ran tests on whatever happened to be checked out in the
working folder, so analysing an old commit reported the test results of the
current code. Here the commit is exported (`git archive`) into a temporary
folder and the selected test files are executed there.
"""

import io
import os
import re
import subprocess
import sys
import tarfile
import tempfile

FAILED_RE = re.compile(r"(\d+) failed")
ERROR_RE = re.compile(r"(\d+) error")


def select_tests(details, changed_files, affected_files):
    """
    Relevant test files, chosen two ways and merged:
      1. call graph : tests that can reach a changed function   (NEW, precise)
      2. naming     : test_<changed or affected file>.py        (original rule)
    Only files that really define test functions are returned.
    """
    graph = details["graph"]
    real_tests = {graph.nodes[t]["path"] for t in graph.test_nodes}
    chosen, reason = set(), {}

    for t in details["tests_hit"]:
        p = graph.nodes[t]["path"]
        chosen.add(p)
        reason.setdefault(p, "calls changed code")

    names = {os.path.basename(f) for f in list(changed_files) + list(affected_files)}
    for p in real_tests:
        if os.path.basename(p) in {"test_" + n for n in names}:
            chosen.add(p)
            reason.setdefault(p, "name matches changed file")

    for f in changed_files:                      # tests edited in this commit
        if f in real_tests:
            chosen.add(f)
            reason.setdefault(f, "edited in this commit")

    chosen &= real_tests
    return sorted(chosen), reason


def run_tests(repo, commit, test_files, timeout=60):
    """Run each test file in a snapshot of `commit`. Returns a result dict."""
    result = {"relevant": len(test_files), "passed": 0, "failed": 0,
              "failures": 0, "details": []}
    if not test_files:
        return result

    buf = io.BytesIO()
    repo.archive(buf, commit.hexsha)
    buf.seek(0)

    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=buf) as tar:
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:                    # Python < 3.12
                tar.extractall(tmp)

        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        for tf in test_files:
            entry = {"file": tf, "status": "passed", "output": ""}
            try:
                proc = subprocess.run(
                    [sys.executable, "-m", "pytest", tf, "-q",
                     "-p", "no:cacheprovider"],
                    cwd=tmp, capture_output=True, text=True,
                    timeout=timeout, env=env)
                out = proc.stdout + proc.stderr
                entry["output"] = out[-1500:]
                if proc.returncode == 5:         # nothing collected
                    entry["status"] = "no tests"
                elif proc.returncode != 0:
                    entry["status"] = "failed"
                    n = sum(int(x) for x in FAILED_RE.findall(out))
                    n += sum(int(x) for x in ERROR_RE.findall(out))
                    result["failures"] += max(n, 1)
            except subprocess.TimeoutExpired:
                entry["status"], entry["output"] = "timed out", ""
                result["failures"] += 1
            except Exception as err:
                entry["status"], entry["output"] = "error", str(err)
                result["failures"] += 1

            if entry["status"] == "passed":
                result["passed"] += 1
            elif entry["status"] in ("failed", "timed out", "error"):
                result["failed"] += 1
            result["details"].append(entry)
    return result

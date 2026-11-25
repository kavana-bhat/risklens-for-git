"""
commit_features.py  (NEW)

ONE place that turns a Git commit into model features, used by
  - main.py          (analyse a single commit)
  - mine_history.py  (build the training set from real history)

Why this matters: in the old version collect_history.py *approximated*
affected_files (= files-1) and functions_changed (= insertions//10) for
training, while main.py computed the real values at prediction time.
The model was trained on one definition and served another
(train/serve skew). Sharing this module removes that problem.

Features
  Change-metric group (in the spirit of Kamei et al., IEEE TSE 2013):
      files_changed, insertions, deletions, entropy, author_exp
  Dependency / test-gap group (what this project adds):
      functions_changed, affected_files, blast_radius,
      untested_blast, untested_changed, untested_ratio,
      test_files_changed
"""

import math

from callgraph import (
    CallGraph, EMPTY, is_ignored, is_test_file, parse_source,
)

MAX_BYTES = 400_000

KAMEI_FEATURES = [
    "files_changed", "insertions", "deletions", "entropy", "author_exp",
]
GAP_FEATURES = [
    "functions_changed", "affected_files", "blast_radius",
    "untested_blast", "untested_changed", "untested_ratio",
    "test_files_changed",
]
ALL_FEATURES = KAMEI_FEATURES + GAP_FEATURES


# ------------------------------------------------------------------
# Loading python files from a git tree (with a per-blob parse cache)
# ------------------------------------------------------------------

def _info_for_blob(blob, cache):
    if blob is None:
        return EMPTY
    sha = blob.hexsha
    if sha not in cache:
        try:
            if blob.size > MAX_BYTES:
                cache[sha] = EMPTY
            else:
                text = blob.data_stream.read().decode("utf-8", "ignore")
                cache[sha] = parse_source(text)
        except Exception:
            cache[sha] = EMPTY
    return cache[sha]


def tree_infos(tree, cache):
    """{path: FileInfo} for every python file in a git tree."""
    out = {}
    for obj in tree.traverse():
        if (obj.type == "blob" and obj.path.endswith(".py")
                and not is_ignored(obj.path)):
            out[obj.path] = _info_for_blob(obj, cache)
    return out


# ------------------------------------------------------------------
# Small metrics
# ------------------------------------------------------------------

def change_entropy(stats_files):
    """Normalised entropy of how the change is spread over files (0..1)."""
    sizes = [max(v.get("lines", 0), 0) for v in stats_files.values()]
    sizes = [s for s in sizes if s > 0]
    total = sum(sizes)
    if len(sizes) <= 1 or total == 0:
        return 0.0
    h = -sum((s / total) * math.log2(s / total) for s in sizes)
    return round(h / math.log2(len(sizes)), 4)


def author_experience(repo, commit, parent=None):
    """Number of earlier commits by the same author."""
    parent = parent or (commit.parents[0] if commit.parents else None)
    if parent is None:
        return 0
    try:
        out = repo.git.rev_list(
            "--count", "--fixed-strings",
            "--author=" + (commit.author.email or commit.author.name),
            parent.hexsha,
        )
        return int(out.strip() or 0)
    except Exception:
        return 0


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

def numstat(repo, parent, commit):
    """(insertions, deletions, {path: {"lines": n}}) between two commits.
    Same numbers GitPython's commit.stats gives, but works for any pair."""
    out = repo.git.diff("--numstat", "--no-renames", parent.hexsha,
                        commit.hexsha, "--")
    ins = dels = 0
    files = {}
    for line in out.splitlines():
        a, d, path = (line.split("\t", 2) + ["", "", ""])[:3]
        a = int(a) if a.isdigit() else 0
        d = int(d) if d.isdigit() else 0
        ins, dels = ins + a, dels + d
        files[path] = {"lines": a + d}
    return ins, dels, files


def extract_features(repo, commit, cache=None, author_exp=None, parent=None):
    """
    Returns (features: dict, details: dict).

    `parent` (optional) lets you compare against any base commit, e.g. the
    merge-base of a pull request, instead of the commit's first parent.

    `details` carries the human-readable evidence (which functions changed,
    which ones are untested, the graph itself) for reports and the advisor.
    """
    cache = cache if cache is not None else {}
    parent = parent or commit.parents[0]
    diff = parent.diff(commit, M=True)

    # ---- which functions changed? ---------------------------------
    changed = {}           # path -> {"added": [], "removed": [], "modified": []}
    changed_files = []
    test_files_changed = 0

    for item in diff:
        path = item.b_path or item.a_path
        changed_files.append(path)
        if not path.endswith(".py"):
            continue
        if is_test_file(path):
            test_files_changed += 1
            continue
        old = _info_for_blob(item.a_blob, cache)
        new = _info_for_blob(item.b_blob, cache)
        old_f, new_f = old.funcs, new.funcs
        added = sorted(set(new_f) - set(old_f))
        removed = sorted(set(old_f) - set(new_f))
        modified = sorted(
            q for q in set(old_f) & set(new_f)
            if old_f[q]["dump"] != new_f[q]["dump"]
        )
        if added or removed or modified:
            changed[path] = {
                "added": added, "removed": removed, "modified": modified,
            }

    # ---- call graph of the NEW tree -------------------------------
    new_infos = tree_infos(commit.tree, cache)
    graph = CallGraph(new_infos)

    changed_ids = set()
    removed_ids = set()
    for path, d in changed.items():
        for q in d["added"] + d["modified"]:
            nid = graph.node_id(path, q)
            if nid in graph.nodes:
                changed_ids.add(nid)
        for q in d["removed"]:
            removed_ids.add(graph.node_id(path, q))

    # callers of functions that no longer exist (found in the OLD graph)
    extra_callers = set()
    if removed_ids:
        old_graph = CallGraph(tree_infos(parent.tree, cache))
        for nid in old_graph.callers(removed_ids) - removed_ids:
            if nid in graph.nodes:
                extra_callers.add(nid)

    seeds = changed_ids | extra_callers
    blast = {
        n for n in graph.callers(seeds)
        if n in graph.nodes and n not in graph.test_nodes
        and not is_test_file(graph.nodes[n]["path"])
    }
    blast |= changed_ids

    reachable = graph.test_reachable()
    untested = sorted(n for n in blast if n not in reachable)
    untested_changed = sorted(n for n in changed_ids if n not in reachable)
    tests_hit = graph.tests_reaching(changed_ids)

    # ---- file-level impact (kept from the original design) --------
    affected_files = set()
    for path in changed:
        for dep in graph.dependents_of_file(path):
            if dep not in changed and not is_test_file(dep):
                affected_files.add(dep)

    functions_changed = sum(
        len(d["added"]) + len(d["removed"]) + len(d["modified"])
        for d in changed.values()
    )

    insertions, deletions, stat_files = numstat(repo, parent, commit)
    features = {
        "files_changed": len(changed_files),
        "insertions": insertions,
        "deletions": deletions,
        "entropy": change_entropy(stat_files),
        "author_exp": (author_exp if author_exp is not None
                       else author_experience(repo, commit, parent)),
        "functions_changed": functions_changed,
        "affected_files": len(affected_files),
        "blast_radius": len(blast),
        "untested_blast": len(untested),
        "untested_changed": len(untested_changed),
        "untested_ratio": round(len(untested) / len(blast), 4) if blast else 0.0,
        "test_files_changed": test_files_changed,
    }

    details = {
        "changed_files": changed_files,
        "changed": changed,
        "changed_ids": sorted(changed_ids),
        "blast": sorted(blast),
        "untested": untested,
        "untested_changed": untested_changed,
        "tests_hit": sorted(tests_hit),
        "affected_files": sorted(affected_files),
        "graph": graph,
        "unparsable": sorted(
            p for p, i in new_infos.items() if not i.ok),
    }
    return features, details

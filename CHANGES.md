# What changed (and why)

## Problems found in the original
1. Training labels were a formula over files + insertions + deletions, so the model
   only re-learned that formula (circular).
2. `collect_history.py` *approximated* `affected_files` and `functions_changed`,
   but `main.py` computed real values at prediction time (train/serve skew).
3. The dependency graph was hard-coded to the `sample-project/` folder.
4. Tests ran on the working folder, not on the commit being analysed.
5. The model trained and printed output every time it was imported.
6. Only a file-level dependency graph; test selection by file name only.

## Changes
| File | Status | Change |
|---|---|---|
| callgraph.py | new | function-level call graph, test reachability |
| commit_features.py | new | single feature extractor (Kamei-style + function-level) |
| gap_detector.py | new | untested blast radius, exact closure plan, pytest stubs |
| mine_history.py | new | SZZ-lite labelling from real bug-fix history |
| analysis.py | new | whole pipeline as one function (commit or PR) |
| snapshot_runner.py | new | tests run on a `git archive` of the analysed commit |
| ci_comment.py + workflow | new | Markdown PR comment, optional merge gate |
| mined_training_data.csv | new | 6,129 mined commits from 6 OSS repos |
| tests/ | new | 13 tests (call graph, pipeline, SZZ, forced-HIGH rule) |
| demo/ | new | demo repo with real test gaps |
| ml_model.py | modified | RandomForest on mined data, chronological + leave-one-repo-out evaluation, local explanation; original tree kept as fallback |
| main.py | modified | same flow, new pipeline, new Test Gap section, `--repo/--commit` flags |
| risk_report.py, risk_explanation.py | modified | optional new fields (backward compatible) |
| save_report.py | modified | new columns, old history migrated automatically |
| dashboard.py | modified | Test Gap Overview section |
| requirements.txt | modified | was empty |

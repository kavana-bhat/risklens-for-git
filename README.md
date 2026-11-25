# 🛡️ Code Change Risk Analyzer

Predicts how risky a Git change is **and tells you what to test to make it safer.**

Most risk tools stop at a score. This one goes through the call graph to find the
functions a change can break, checks which of them no test can reach, and gives a
concrete plan (plus pytest stubs) to close the gap.

```
Commit / Pull request
   ↓  git diff (rename-aware)
Function-level change detection        (AST: added / modified / removed)
   ↓
Function call graph                    (who calls what, across files)
   ↓
Blast radius  =  changed functions + everything that calls them
   ↓
Test reachability                      (which blast-radius functions can no test reach?)
   ↓
Relevant tests chosen by call graph + naming, run on the analysed commit
   ↓
ML risk score (trained on real bug-fix history) + local explanation
   ↓
Report: risk • why • TEST GAPS • how to close them • test stubs
   ↓
CLI  |  Streamlit dashboard  |  GitHub PR comment
```

## What is different from existing approaches

| | Metric-only JIT defect models | Static analyzers (SonarQube…) | Test-impact tools | **This project** |
|---|---|---|---|---|
| Predicts risk of a *specific change* | ✅ | ❌ | ❌ | ✅ |
| Function-level blast radius | ❌ | ❌ | partly | ✅ |
| Finds *untested* parts of the blast radius | ❌ | ❌ | ❌ | ✅ |
| Gives a plan + test stubs to close the gap | ❌ | ❌ | ❌ | ✅ |
| Trained on real bug-fix history (SZZ) | ✅ | n/a | n/a | ✅ |
| Explains each prediction | rarely | n/a | n/a | ✅ |

Related work: Kamei et al., *A Large-Scale Empirical Study of Just-in-Time Quality
Assurance*, IEEE TSE 39(6), 2013 (change metrics, entropy, author experience);
Śliwerski, Zimmermann, Zeller, *When Do Changes Induce Fixes?*, MSR 2005 (SZZ labelling).

## Quick start

```bash
pip install -r requirements.txt

# try it on a bundled demo repo (has real test gaps)
python demo/make_demo_repo.py /tmp/shop-demo
python main.py --repo /tmp/shop-demo --commit HEAD

# interactive mode (as before)
python main.py

# dashboard
streamlit run dashboard.py

# analyse a whole branch / pull request and write a Markdown comment
python ci_comment.py --repo . --base origin/main --head HEAD --out risk-comment.md

# tests
pytest
```

The model trains automatically on first use from `mined_training_data.csv`.
To see the full evaluation: `python ml_model.py`.

### GitHub integration
`.github/workflows/risk-check.yml` runs on every pull request and posts (or updates)
the report as a PR comment. Add `--fail-on HIGH` to `ci_comment.py` to block merges.

## Building your own training data

```bash
python mine_history.py path/to/any/git/repo --max-commits 1500
python ml_model.py
```

Labels use **SZZ-lite**: a commit is *defect-inducing* if a later bug-fix commit
changed or removed lines it wrote (found with `git blame`). Features are computed
by the same code used at prediction time (`commit_features.py`).

## Evaluation

Training set: 6,129 commits from 6 open-source Python projects
(click, httpx, itsdangerous, markupsafe, requests, werkzeug); 6.3% defect-inducing.

Chronological validation (train on the past, test on the future):

| Model | ROC-AUC | PR-AUC | Recall @ top 20% |
|---|---|---|---|
| Lines changed only | 0.777 | 0.236 | 0.576 |
| Kamei-style change metrics | 0.794 | 0.269 | 0.577 |
| **+ function-level features (this project)** | **0.872** | **0.367** | **0.668** |

Leave-one-repo-out (model never saw the project): ROC-AUC 0.838 – 0.887 vs
0.711 – 0.811 for the metric-only baseline, better on all six.

## Honest limitations

* **The accuracy gain comes from function-level features** (functions changed,
  blast radius, dependents). In ablation the *test-gap* features did **not**
  improve held-out accuracy, so they are reported to the user but are not model
  inputs. Test-gap analysis is an actionable report, not a claimed predictor.
* Labels are SZZ-lite approximations and are noisy; the newest ~8% of commits are
  excluded because they have not had time to be "fixed".
* The training projects are all well-maintained Python libraries; expect a shift on
  very different codebases (retrain with `mine_history.py` on yours).
* "Test-reachable" is static: a call path exists, not that assertions are
  meaningful. Dynamic dispatch, mocks and fixtures are approximated.
* Python only. Changes to non-Python files count toward size metrics but not
  toward function-level impact.
* Risk bands are relative (HIGH ≈ riskiest 15% of code-changing commits).
  Failing relevant tests force HIGH.

## Project structure

**New**
`callgraph.py` function-level call graph • `commit_features.py` one feature extractor
for training and prediction • `gap_detector.py` test-gap plan and stubs •
`mine_history.py` SZZ-lite dataset builder • `analysis.py` pipeline •
`snapshot_runner.py` runs tests on the analysed commit • `ci_comment.py` PR report •
`.github/workflows/risk-check.yml` • `tests/` • `demo/`

**Modified**
`main.py` • `ml_model.py` • `risk_report.py` • `risk_explanation.py` •
`save_report.py` • `dashboard.py`

**Original, kept as is (legacy)**
`collect_history.py`, `build_dataset.py`, `analyzer.py`, `risk_analyzer.py`,
`risk_model.py`, `impact_analysis.py`, `dependency_graph.py`, `code_analyzer.py`,
`change_analyzer.py`, `test_recommender.py`, `sample-project/`

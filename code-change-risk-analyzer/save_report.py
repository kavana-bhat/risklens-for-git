import csv
import os
from datetime import datetime

HISTORY_FILE = "risk_history.csv"

# NEW columns are appended after the original ones, so the original
# dashboard columns keep working.
COLUMNS = [
    "timestamp", "commit_id", "commit_message", "files_changed",
    "insertions", "deletions", "affected_files", "functions_changed",
    "test_failures", "risk", "confidence",
    # NEW
    "blast_radius", "untested_blast", "untested_changed", "entropy", "model",
]


def _migrate_old_header(file_name):
    """Old history files have 11 columns; pad them so rows stay aligned."""
    with open(file_name, newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    if not rows or rows[0] == COLUMNS:
        return
    old_header = rows[0]
    padded = [COLUMNS]
    for r in rows[1:]:
        record = dict(zip(old_header, r))
        padded.append([record.get(c, "") for c in COLUMNS])
    with open(file_name, "w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows(padded)


def save_analysis(
    commit_id,
    commit_message,
    files_changed,
    insertions,
    deletions,
    affected_files,
    functions_changed,
    test_failures,
    prediction,
    confidence,
    extra=None          # NEW: dict with v2 features (optional)
):

    file_name = HISTORY_FILE
    extra = extra or {}

    if os.path.exists(file_name):
        _migrate_old_header(file_name)
    file_exists = os.path.exists(file_name)

    with open(
        file_name,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        # Create header only once
        if not file_exists:
            writer.writerow(COLUMNS)

        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            commit_id,
            commit_message,
            files_changed,
            insertions,
            deletions,
            affected_files,
            functions_changed,
            test_failures,
            prediction,
            round(confidence * 100, 2),
            extra.get("blast_radius", ""),
            extra.get("untested_blast", ""),
            extra.get("untested_changed", ""),
            extra.get("entropy", ""),
            extra.get("model", "legacy"),
        ])

    print("\n✓ Analysis saved to " + file_name)

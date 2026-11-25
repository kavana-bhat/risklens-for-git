from git import Repo
import csv
import os


# =================================
# OPEN REPOSITORY
# =================================

repo_path = input(
    "Enter Git repository path: "
).strip()

repo = Repo(repo_path)


# =================================
# COLLECT COMMIT HISTORY
# =================================

rows = []


commits = list(repo.iter_commits())


print("\nCollecting commit history...\n")


for commit in commits:

    # Skip first commit because
    # it has no parent

    if not commit.parents:
        continue


    parent = commit.parents[0]


    try:

        diff = parent.diff(commit)


        files_changed = len(diff)

        insertions = commit.stats.total[
            "insertions"
        ]

        deletions = commit.stats.total[
            "deletions"
        ]


        # Simple impact approximation
        affected_files = max(
            0,
            files_changed - 1
        )


        # Simple function approximation
        functions_changed = max(
            0,
            insertions // 10
        )


        # We don't yet know actual
        # test failures for old commits

        test_failures = 0


        # Temporary label
        total_change = (
            files_changed
            + insertions
            + deletions
        )


        if total_change >= 40:

            risk = "HIGH"

        elif total_change >= 15:

            risk = "MEDIUM"

        else:

            risk = "LOW"


        rows.append([

            files_changed,

            insertions,

            deletions,

            affected_files,

            functions_changed,

            test_failures,

            risk

        ])


        print(
            commit.hexsha[:7],
            "| files:",
            files_changed,
            "| +",
            insertions,
            "| -",
            deletions,
            "| risk:",
            risk
        )


    except Exception:

        pass


# =================================
# SAVE DATASET
# =================================

output_file = "git_training_data.csv"


with open(
    output_file,
    "w",
    newline="",
    encoding="utf-8"
) as file:

    writer = csv.writer(file)


    writer.writerow([

        "files_changed",

        "insertions",

        "deletions",

        "affected_files",

        "functions_changed",

        "test_failures",

        "risk"

    ])


    writer.writerows(rows)


print(
    "\n==================================="
)

print(
    "DATA COLLECTION COMPLETE"
)

print(
    "==================================="
)

print(
    "\nTotal commits collected:",
    len(rows)
)

print(
    "Dataset:",
    output_file
)
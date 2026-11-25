import pandas as pd


# =================================
# LOAD DATASETS
# =================================

original_data = pd.read_csv(
    "training_data.csv"
)

git_data = pd.read_csv(
    "git_training_data.csv"
)


# =================================
# COMBINE DATA
# =================================

combined_data = pd.concat(
    [
        original_data,
        git_data
    ],
    ignore_index=True
)


# =================================
# REMOVE DUPLICATES
# =================================

combined_data = combined_data.drop_duplicates()


# =================================
# SAVE FINAL DATASET
# =================================

combined_data.to_csv(
    "final_training_data.csv",
    index=False
)


# =================================
# REPORT
# =================================

print("\n===================================")
print("       DATASET CREATED")
print("===================================")

print(
    "\nOriginal samples:",
    len(original_data)
)

print(
    "Git history samples:",
    len(git_data)
)

print(
    "Final samples:",
    len(combined_data)
)

print(
    "\nRisk distribution:"
)

print(
    combined_data["risk"].value_counts()
)

print(
    "\nSaved as:"
)

print(
    "final_training_data.csv"
)
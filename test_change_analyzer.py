from change_analyzer import analyze_changed_files


repo_path = "C:/Users/Admin/code-risk-analyzer"

changed_files = [
    "sample-project/payment.py"
]

results = analyze_changed_files(
    repo_path,
    changed_files
)

print("\nCHANGED FILE ANALYSIS")
print("---------------------")

for file, functions in results.items():

    print("\nFile:", file)

    print("Functions:")

    for function in functions:
        print("-", function)
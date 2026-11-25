
from git import Repo

print("CODE CHANGE RISK ANALYZER")
print("-------------------------")

# Get repository path
repo_path = input("Enter Git repository path: ")

# Open Git repository
repo = Repo(repo_path)

print("\nAvailable commits:")

for commit in repo.iter_commits():
    print(commit.hexsha[:7], "-", commit.message.strip())

# Select commit
commit_id = input("\nEnter commit ID to analyze: ")

commit = repo.commit(commit_id)

# Get previous commit
if not commit.parents:
    print("This commit has no previous commit.")
    exit()

parent = commit.parents[0]

# Compare commits
diff = parent.diff(commit)

print("\nCHANGE SUMMARY")
print("--------------")

print("Commit:", commit.hexsha[:7])
print("Message:", commit.message.strip())

print("\nFILES CHANGED")
print("-------------")

changed_files = []

for item in diff:
    file_name = item.b_path or item.a_path
    changed_files.append(file_name)
    print("-", file_name)

print("\nSTATISTICS")
print("----------")

print("Files changed:", len(changed_files))
print("Insertions:", commit.stats.total["insertions"])
print("Deletions:", commit.stats.total["deletions"])

print("\nANALYSIS COMPLETE")
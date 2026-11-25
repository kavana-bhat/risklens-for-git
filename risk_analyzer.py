print("CODE CHANGE RISK ANALYZER")
print("-------------------------")

# Get Git change information
files_changed = int(input("Files changed: "))
insertions = int(input("Insertions: "))
deletions = int(input("Deletions: "))

# Get impact information
affected_files = int(input("Affected files: "))


# Risk calculation
score = 0

if files_changed >= 3:
    score += 2
elif files_changed >= 2:
    score += 1

if insertions >= 30:
    score += 2
elif insertions >= 10:
    score += 1

if deletions >= 20:
    score += 2
elif deletions >= 5:
    score += 1

if affected_files >= 5:
    score += 2
elif affected_files >= 2:
    score += 1


# Final result
print("\nRISK REPORT")
print("-----------")

print("Files changed:", files_changed)
print("Insertions:", insertions)
print("Deletions:", deletions)
print("Affected files:", affected_files)

print("\nRisk Score:", score, "/ 8")

if score >= 5:
    print("Risk Level: HIGH")
elif score >= 3:
    print("Risk Level: MEDIUM")
else:
    print("Risk Level: LOW")
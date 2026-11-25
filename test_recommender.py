def recommend_tests(changed_files, affected_files):

    tests = []

    # Tests based on changed files
    for file in changed_files:

        if "payment" in file.lower():
            tests.append("Run payment validation tests")

        elif "order" in file.lower():
            tests.append("Run order creation tests")

        elif "user" in file.lower():
            tests.append("Run user authentication tests")

        else:
            tests.append(
                "Run unit tests for " + file
            )

    # Tests based on affected files
    for file in affected_files:

        if "order" in file.lower():
            tests.append("Run order integration tests")

        elif "app" in file.lower():
            tests.append("Run application integration tests")

    return list(set(tests))


# Test
changed_files = ["payment.py"]

affected_files = ["order.py", "app.py"]

tests = recommend_tests(
    changed_files,
    affected_files
)

print("\nRECOMMENDED TESTS")
print("-----------------")

for test in tests:
    print("-", test)
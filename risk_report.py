def print_risk_report(
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
    extra=None
):  # `extra` (NEW): dict with v2 features, optional

    print("\n")
    print("==========================================")
    print("       CODE CHANGE RISK REPORT")
    print("==========================================")

    print("\nCOMMIT INFORMATION")
    print("------------------")

    print("Commit:", commit_id)

    print("Message:", commit_message)


    print("\nCHANGE ANALYSIS")
    print("----------------")

    print("Files changed:", files_changed)

    print("Lines added:", insertions)

    print("Lines deleted:", deletions)

    print("Affected files:", affected_files)

    print("Functions changed:", functions_changed)

    if extra:                                    # NEW: function-level impact
        print("Change spread (entropy):", extra.get("entropy"))
        print("Blast radius (functions):", extra.get("blast_radius"))
        print("Untested in blast radius:", extra.get("untested_blast"))


    print("\nTEST ANALYSIS")
    print("-------------")

    if test_failures == 0:

        print("Test failures: 0")

        print("Test status: ALL TESTS PASSED")

    else:

        print(
            "Test failures:",
            test_failures
        )

        print("Test status: TEST FAILURES DETECTED")


    print("\nAI RISK PREDICTION")
    print("------------------")

    print(
        "Risk Level:",
        prediction
    )

    if extra and extra.get("model") == "v2":     # NEW: relative score
        print(
            "Model risk score:",
            round(confidence * 100, 1),
            "%  (typical commit:",
            round(extra.get("base_rate", 0) * 100, 1),
            "%)"
        )
    else:
        print(
            "Confidence:",
            round(
                confidence * 100,
                2
            ),
            "%"
        )


    print("\n==========================================")

    if prediction == "HIGH":

        print(
            "⚠ HIGH RISK CHANGE"
        )

        print(
            "Review the affected code before merging."
        )

    elif prediction == "MEDIUM":

        print(
            "⚠ MEDIUM RISK CHANGE"
        )

        print(
            "Additional testing is recommended."
        )

    else:

        print(
            "✓ LOW RISK CHANGE"
        )

        print(
            "Change appears relatively safe."
        )


    print("==========================================")
def explain_risk(
    prediction,
    files_changed,
    insertions,
    deletions,
    affected_files,
    functions_changed,
    test_failures,
    contributions=None,
    notes=None
):  # contributions / notes (NEW): model-based reasons

    reasons = []

    # Large number of files
    if files_changed >= 5:
        reasons.append(
            f"{files_changed} files were changed"
        )

    # Large code change
    if insertions >= 100:
        reasons.append(
            f"{insertions} lines were added"
        )

    # Many deletions
    if deletions >= 50:
        reasons.append(
            f"{deletions} lines were deleted"
        )

    # Impacted files
    if affected_files >= 3:
        reasons.append(
            f"{affected_files} dependent files may be affected"
        )

    # Functions
    if functions_changed >= 5:
        reasons.append(
            f"{functions_changed} functions were changed"
        )

    # Test failures
    if test_failures > 0:
        reasons.append(
            f"{test_failures} test(s) failed"
        )

    # NEW: what the model itself says pushed the score up or down
    for feature, value, delta in (contributions or []):
        direction = "raises" if delta > 0 else "lowers"
        reasons.append(
            f"model: {feature} = {value} {direction} the score "
            f"by {abs(delta) * 100:.1f} points"
        )

    for note in (notes or []):
        reasons.append(note)

    # If no major reason
    if not reasons:

        reasons.append(
            "The change has relatively low structural impact"
        )


    print("\n")
    print("==========================================")
    print("          RISK EXPLANATION")
    print("==========================================")

    print(
        "\nPredicted Risk:",
        prediction
    )

    print("\nWhy?")

    for reason in reasons:

        print(
            "•",
            reason
        )


    print("\nRecommendation")

    if prediction == "HIGH":

        print(
            "⚠ Perform detailed code review "
            "and run additional tests before merging."
        )

    elif prediction == "MEDIUM":

        print(
            "⚠ Review affected modules and "
            "perform additional testing."
        )

    else:

        print(
            "✓ Change appears relatively safe, "
            "but normal testing is recommended."
        )

    print(
        "=========================================="
    )
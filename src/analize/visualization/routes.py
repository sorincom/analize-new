"""Visualization routes for viewing test results."""

from flask import Blueprint, current_app, jsonify, render_template

from analize.dal import Database

viz_bp = Blueprint("viz", __name__)


@viz_bp.route("/users", methods=["GET"])
def list_users():
    """List all users."""
    db = Database(current_app.config["DATA_DB_PATH"], current_app.config["CONFIG_DB_PATH"])
    users = db.list_users()
    return jsonify([u.model_dump() for u in users])


@viz_bp.route("/users/<int:user_id>/tests", methods=["GET"])
def list_user_tests(user_id: int):
    """List all tests for a user.

    Returns test types with their latest result.
    """
    db = Database(current_app.config["DATA_DB_PATH"], current_app.config["CONFIG_DB_PATH"])

    # Get user info
    user = db.get_user(user_id)
    if not user:
        return "User not found", 404

    # Get all results for user
    results = db.get_results_for_user(user_id)

    # Group by test type
    tests_by_type: dict[int, dict] = {}
    for result in results:
        type_id = result["test_type_id"]
        if type_id not in tests_by_type:
            # Use stored clinical_status, fallback to computed status if missing
            status = result.get("clinical_status")
            if status:
                status = status.lower()  # Convert NORMAL/ABNORMAL/BORDERLINE to lowercase
            else:
                # Fallback: compute status for old results without clinical_status
                is_qualitative = result["value"] is None and result["value_normalized"] is not None
                if is_qualitative:
                    normalized = result["value_normalized"]
                    if normalized in ("POSITIVE", "DETECTED", "REACTIVE", "PRESENT", "ABNORMAL", "HIGH"):
                        status = "abnormal"
                    elif normalized in ("NEGATIVE", "NOT_DETECTED", "NON_REACTIVE", "ABSENT", "NORMAL"):
                        status = "normal"
                    elif normalized == "BORDERLINE":
                        status = "borderline"
                elif result["value"] is not None:
                    if result["lower_limit"] is not None and result["upper_limit"] is not None:
                        if result["lower_limit"] <= result["value"] <= result["upper_limit"]:
                            status = "normal"
                        else:
                            status = "abnormal"
                    elif result["lower_limit"] is not None:
                        status = "normal" if result["value"] >= result["lower_limit"] else "abnormal"
                    elif result["upper_limit"] is not None:
                        status = "normal" if result["value"] <= result["upper_limit"] else "abnormal"

            tests_by_type[type_id] = {
                "test_type_id": type_id,
                "standard_name": result["standard_name"],
                "category": result["category"],
                "latest_date": result["test_date"],
                "latest_value": result["value"],
                "latest_value_normalized": result["value_normalized"],
                "latest_unit": result["unit"],
                "latest_status": status,
                "result_count": 0,
            }
        tests_by_type[type_id]["result_count"] += 1

    tests = list(tests_by_type.values())
    return render_template("tests_list.html", user=user, tests=tests)


@viz_bp.route("/users/<int:user_id>/tests/<int:test_type_id>/timeline", methods=["GET"])
def test_timeline(user_id: int, test_type_id: int):
    """Get timeline of results for a specific test.

    Returns all results for this test type ordered by date.
    Used for vertical timeline visualization.
    """
    db = Database(current_app.config["DATA_DB_PATH"], current_app.config["CONFIG_DB_PATH"])

    # Get user info
    user = db.get_user(user_id)
    if not user:
        return "User not found", 404

    # Get test type info
    test_types = db.list_test_types()
    test_type = next((t for t in test_types if t.id == test_type_id), None)
    if not test_type:
        return "Test type not found", 404

    # Get results
    results = db.get_results_for_test_type(user_id, test_type_id)

    # Format for timeline
    timeline = []
    for result in results:
        # Use stored clinical_status, fallback to computed status if missing
        status = result.clinical_status
        if status:
            status = status.lower()  # Convert NORMAL/ABNORMAL/BORDERLINE to lowercase
        else:
            # Fallback: compute status for old results without clinical_status
            is_qualitative = result.value is None and result.value_text is not None
            if is_qualitative:
                normalized = result.value_normalized
                if normalized in ("POSITIVE", "DETECTED", "REACTIVE", "PRESENT", "ABNORMAL", "HIGH"):
                    status = "abnormal"
                elif normalized in ("NEGATIVE", "NOT_DETECTED", "NON_REACTIVE", "ABSENT", "NORMAL"):
                    status = "normal"
                elif normalized == "BORDERLINE":
                    status = "borderline"
                else:
                    status = "unknown"
            elif result.value is not None:
                if result.lower_limit is not None and result.upper_limit is not None:
                    if result.lower_limit <= result.value <= result.upper_limit:
                        status = "normal"
                    else:
                        status = "abnormal"
                elif result.lower_limit is not None:
                    status = "normal" if result.value >= result.lower_limit else "abnormal"
                elif result.upper_limit is not None:
                    status = "normal" if result.value <= result.upper_limit else "abnormal"

        is_qualitative = result.value is None and result.value_text is not None
        timeline.append({
            "date": str(result.test_date),
            "value": result.value,
            "value_text": result.value_text,
            "value_normalized": result.value_normalized,
            "unit": result.unit,
            "lower_limit": result.lower_limit,
            "upper_limit": result.upper_limit,
            "status": status,  # normal, abnormal, borderline, unknown
            "is_qualitative": is_qualitative,
            "interpretation": result.interpretation,
            "lab_test_name": result.lab_test_name,
            "documentation": result.documentation,
        })

    return render_template(
        "timeline.html",
        user=user,
        test_name=test_type.standard_name,
        category=test_type.category,
        timeline=timeline,
    )


@viz_bp.route("/test-types", methods=["GET"])
def list_test_types():
    """List all test types in the system."""
    db = Database(current_app.config["DATA_DB_PATH"], current_app.config["CONFIG_DB_PATH"])
    test_types = db.list_test_types()
    return jsonify([t.model_dump() for t in test_types])

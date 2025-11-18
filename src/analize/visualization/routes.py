"""Visualization routes for viewing test results."""

from flask import Blueprint, current_app, jsonify

from analize.mcp import DatabaseMCP

viz_bp = Blueprint("viz", __name__)


@viz_bp.route("/users", methods=["GET"])
def list_users():
    """List all users."""
    db = DatabaseMCP(current_app.config["DATABASE_PATH"])
    users = db.list_users()
    return jsonify([u.model_dump() for u in users])


@viz_bp.route("/users/<int:user_id>/tests", methods=["GET"])
def list_user_tests(user_id: int):
    """List all tests for a user.

    Returns test types with their latest result.
    """
    db = DatabaseMCP(current_app.config["DATABASE_PATH"])

    # Get all results for user
    results = db.get_results_for_user(user_id)

    # Group by test type
    tests_by_type: dict[int, dict] = {}
    for result in results:
        type_id = result["test_type_id"]
        if type_id not in tests_by_type:
            tests_by_type[type_id] = {
                "test_type_id": type_id,
                "standard_name": result["standard_name"],
                "category": result["category"],
                "latest_date": result["test_date"],
                "latest_value": result["value"],
                "latest_value_text": result["value_text"],
                "latest_unit": result["unit"],
                "result_count": 0,
            }
        tests_by_type[type_id]["result_count"] += 1

    return jsonify(list(tests_by_type.values()))


@viz_bp.route("/users/<int:user_id>/tests/<int:test_type_id>/timeline", methods=["GET"])
def test_timeline(user_id: int, test_type_id: int):
    """Get timeline of results for a specific test.

    Returns all results for this test type ordered by date.
    Used for vertical timeline visualization.
    """
    db = DatabaseMCP(current_app.config["DATABASE_PATH"])

    # Get test type info
    test_types = db.list_test_types()
    test_type = next((t for t in test_types if t.id == test_type_id), None)
    if not test_type:
        return jsonify({"error": "Test type not found"}), 404

    # Get results
    results = db.get_results_for_test_type(user_id, test_type_id)

    # Format for timeline
    timeline = []
    for result in results:
        # Determine if value is in range
        in_range = None
        if result.value is not None:
            if result.lower_limit is not None and result.upper_limit is not None:
                in_range = result.lower_limit <= result.value <= result.upper_limit
            elif result.lower_limit is not None:
                in_range = result.value >= result.lower_limit
            elif result.upper_limit is not None:
                in_range = result.value <= result.upper_limit

        timeline.append({
            "date": str(result.test_date),
            "value": result.value,
            "value_text": result.value_text,
            "unit": result.unit,
            "lower_limit": result.lower_limit,
            "upper_limit": result.upper_limit,
            "in_range": in_range,
            "lab_name": result.lab_name,
            "lab_test_name": result.lab_test_name,
            "documentation": result.documentation,
        })

    return jsonify({
        "test_type_id": test_type_id,
        "standard_name": test_type.standard_name,
        "category": test_type.category,
        "timeline": timeline,
    })


@viz_bp.route("/test-types", methods=["GET"])
def list_test_types():
    """List all test types in the system."""
    db = DatabaseMCP(current_app.config["DATABASE_PATH"])
    test_types = db.list_test_types()
    return jsonify([t.model_dump() for t in test_types])

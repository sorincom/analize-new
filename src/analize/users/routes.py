"""User management routes."""

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from analize.dal import Database

users_bp = Blueprint("users", __name__)


@users_bp.route("/")
def list_users():
    """List all users."""
    db = Database(current_app.config["DATA_DB_PATH"], current_app.config["CONFIG_DB_PATH"])
    users = db.list_users()
    return render_template("users.html", users=users)


@users_bp.route("/new", methods=["GET", "POST"])
def create_user():
    """Create a new user."""
    if request.method == "POST":
        name = request.form.get("name")
        sex = request.form.get("sex")
        date_of_birth = request.form.get("date_of_birth")

        if not name or not sex or not date_of_birth:
            return render_template("user_new.html", error="All fields are required")

        if sex not in ("M", "F", "O"):
            return render_template("user_new.html", error="Invalid sex value")

        db = Database(current_app.config["DATA_DB_PATH"], current_app.config["CONFIG_DB_PATH"])
        user_id = db.create_user(name=name, sex=sex, date_of_birth=date_of_birth)

        # Set session and redirect to user's documents
        session["user_id"] = user_id
        return redirect(url_for("upload.upload_page"))

    return render_template("user_new.html")

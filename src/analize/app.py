"""Flask application factory."""

import os

from flask import Flask, render_template

from analize.config import config


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "default")

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Enable sessions
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = "dev-secret-key-change-in-production"

    # Ensure upload directory exists
    app.config["UPLOAD_DIR"].mkdir(parents=True, exist_ok=True)

    # Register blueprints
    from analize.upload.routes import upload_bp
    from analize.users.routes import users_bp
    from analize.visualization.routes import viz_bp

    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(upload_bp, url_prefix="/upload")
    app.register_blueprint(viz_bp, url_prefix="/viz")

    @app.route("/")
    def index():
        """Landing page - user selection."""
        from analize.dal import Database

        db = Database(app.config["DATA_DB_PATH"], app.config["CONFIG_DB_PATH"])
        users = db.list_users()
        return render_template("user_selection.html", users=users)

    @app.route("/select-user/<int:user_id>")
    def select_user(user_id: int):
        """Select a user for this session."""
        from flask import session, redirect, url_for
        from analize.dal import Database

        db = Database(app.config["DATA_DB_PATH"], app.config["CONFIG_DB_PATH"])
        user = db.get_user(user_id)

        if user:
            session["user_id"] = user_id
            return redirect(url_for("upload.upload_page"))

        return redirect(url_for("index"))

    @app.route("/tests")
    def tests():
        """Show tests for session user."""
        from flask import session, redirect, url_for
        if "user_id" not in session:
            return redirect(url_for("index"))
        return redirect(url_for("viz.list_user_tests", user_id=session["user_id"]))

    @app.route("/change-user")
    def change_user():
        """Clear user session and return to selection."""
        from flask import session, redirect, url_for
        session.pop("user_id", None)
        return redirect(url_for("index"))

    @app.route("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app

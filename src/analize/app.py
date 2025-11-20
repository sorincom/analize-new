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
        """Home page."""
        from analize.dal import Database

        db = Database(app.config["DATABASE_PATH"])
        stats = {
            "users": len(db.list_users()),
            "labs": len(db.list_labs()),
            "test_types": len(db.list_test_types()),
        }
        return render_template("index.html", stats=stats)

    @app.route("/health")
    def health_check() -> dict[str, str]:
        return {"status": "healthy"}

    return app

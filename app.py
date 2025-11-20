"""Flask application entry point."""

from analize.app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

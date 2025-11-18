"""Upload routes for PDF handling."""

import hashlib
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from werkzeug.utils import secure_filename

from analize.mcp import DatabaseMCP

upload_bp = Blueprint("upload", __name__)


def allowed_file(filename: str) -> bool:
    """Check if file extension is allowed."""
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in current_app.config["ALLOWED_EXTENSIONS"]
    )


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


@upload_bp.route("/", methods=["POST"])
def upload_file():
    """Upload a PDF file for processing.

    Expects:
        - file: PDF file
        - user_id: User ID

    Returns:
        - document_id: ID of created document
        - is_duplicate: Whether this file was already uploaded
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    user_id = request.form.get("user_id")

    if not user_id:
        return jsonify({"error": "No user_id provided"}), 400

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only PDF allowed"}), 400

    # Save file
    filename = secure_filename(file.filename)
    upload_dir: Path = current_app.config["UPLOAD_DIR"]
    file_path = upload_dir / f"{user_id}_{filename}"
    file.save(file_path)

    # Compute hash
    content_hash = compute_file_hash(file_path)

    # Check for duplicate
    db = DatabaseMCP(current_app.config["DATABASE_PATH"])
    existing = db.get_document_by_hash(content_hash)

    if existing:
        # File already processed - delete uploaded copy and return existing
        file_path.unlink()
        return jsonify({
            "document_id": existing.id,
            "is_duplicate": True,
            "message": "File already uploaded. Use reprocess endpoint to re-extract data.",
        })

    # Create document record
    document_id = db.create_document(
        user_id=int(user_id),
        file_path=str(file_path),
        content_hash=content_hash,
    )

    return jsonify({
        "document_id": document_id,
        "is_duplicate": False,
        "message": "File uploaded successfully. Call process endpoint to extract data.",
    })


@upload_bp.route("/reprocess/<int:document_id>", methods=["POST"])
def reprocess_document(document_id: int):
    """Reprocess an existing document.

    Deletes existing results and allows re-extraction.
    Useful when LLM extraction improves or errors need fixing.
    """
    db = DatabaseMCP(current_app.config["DATABASE_PATH"])
    deleted_count = db.delete_results_for_document(document_id)

    return jsonify({
        "document_id": document_id,
        "deleted_results": deleted_count,
        "message": "Results cleared. Call process endpoint to re-extract data.",
    })

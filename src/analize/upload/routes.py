"""Upload routes for PDF handling."""

import hashlib
from pathlib import Path

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from analize.dal import Database

upload_bp = Blueprint("upload", __name__)


@upload_bp.route("/")
def upload_page():
    """Show upload page with user selection."""
    db = Database(current_app.config["DATABASE_PATH"])
    users = db.list_users()
    return render_template("upload.html", users=users)


@upload_bp.route("/user/<int:user_id>")
def user_documents(user_id: int):
    """Show documents for a specific user."""
    db = Database(current_app.config["DATABASE_PATH"])
    user = db.get_user(user_id)
    if not user:
        return "User not found", 404

    documents = db.list_documents_for_user(user_id)
    return render_template("user_documents.html", user=user, documents=documents)


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


@upload_bp.route("/upload", methods=["POST"])
def upload_file():
    """Upload a PDF file for processing.

    Expects:
        - file: PDF file
        - user_id: User ID
        - redirect: Optional, if present returns HTML redirect instead of JSON

    Returns:
        - document_id: ID of created document
        - is_duplicate: Whether this file was already uploaded
    """
    if "file" not in request.files:
        if request.form.get("redirect"):
            return render_template("upload.html", error="No file provided", users=[])
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    user_id = request.form.get("user_id")
    should_redirect = request.form.get("redirect")

    if not user_id:
        if should_redirect:
            db = Database(current_app.config["DATABASE_PATH"])
            users = db.list_users()
            return render_template("upload.html", error="No user selected", users=users)
        return jsonify({"error": "No user_id provided"}), 400

    if file.filename == "":
        if should_redirect:
            return redirect(url_for("upload.user_documents", user_id=user_id))
        return jsonify({"error": "No file selected"}), 400

    if not file.filename or not allowed_file(file.filename):
        if should_redirect:
            return redirect(url_for("upload.user_documents", user_id=user_id, error="invalid_file"))
        return jsonify({"error": "Invalid file type. Only PDF allowed"}), 400

    # Save file
    filename = secure_filename(file.filename)
    upload_dir: Path = current_app.config["UPLOAD_DIR"]
    file_path = upload_dir / f"{user_id}_{filename}"
    file.save(file_path)

    # Compute hash
    content_hash = compute_file_hash(file_path)

    # Check for duplicate
    db = Database(current_app.config["DATABASE_PATH"])
    existing = db.get_document_by_hash(content_hash)

    if existing:
        # File already processed - delete uploaded copy
        file_path.unlink()
        if should_redirect:
            return redirect(url_for("upload.user_documents", user_id=user_id, duplicate="1"))
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

    if should_redirect:
        return redirect(url_for("upload.user_documents", user_id=user_id))

    return jsonify({
        "document_id": document_id,
        "is_duplicate": False,
        "message": "File uploaded successfully. Call process endpoint to extract data.",
    })


@upload_bp.route("/process/<int:document_id>", methods=["POST"])
def process_document(document_id: int):
    """Process a document to extract test results.

    Flow:
    1. Extract lab info from document header/footer
    2. Normalize lab (LLM deduplication)
    3. Extract test results
    4. Normalize and store tests with lab_id

    Uses upsert logic - if historical data is found in multiple documents,
    existing results are updated rather than duplicated.
    """
    from analize.processing import LabNormalizer, PDFExtractor, TestNormalizer

    db = Database(current_app.config["DATABASE_PATH"])
    document = db.get_document(document_id)

    if not document:
        return jsonify({"error": "Document not found"}), 404

    # Extract lab info and tests from PDF
    extractor = PDFExtractor(
        api_key=current_app.config["GEMINI_API_KEY"],
        model=current_app.config["GEMINI_MODEL"],
    )
    extracted_lab, extracted_tests = extractor.extract_from_pdf(Path(document.file_path))

    # Normalize lab (get or create with LLM dedup)
    lab_normalizer = LabNormalizer(
        db=db,
        api_key=current_app.config["ANTHROPIC_API_KEY"],
        model=current_app.config["ANTHROPIC_MODEL"],
    )
    lab = lab_normalizer.get_or_create_lab(extracted_lab)

    # Update document with lab_id
    db.update_document_lab(document_id, lab.id)  # type: ignore[arg-type]

    # Normalize and store tests
    test_normalizer = TestNormalizer(
        db=db,
        api_key=current_app.config["ANTHROPIC_API_KEY"],
        model=current_app.config["ANTHROPIC_MODEL"],
    )
    result_ids = test_normalizer.normalize_and_store(
        user_id=document.user_id,
        document_id=document_id,
        lab_id=lab.id,  # type: ignore[arg-type]
        extracted_tests=extracted_tests,
    )

    # Collect and store token usage
    import json

    tokens = {
        current_app.config["GEMINI_MODEL"]: {
            "input": extractor.tokens_used["input"],
            "output": extractor.tokens_used["output"],
        },
        current_app.config["ANTHROPIC_MODEL"]: {
            "input": lab_normalizer.tokens_used["input"] + test_normalizer.tokens_used["input"],
            "output": lab_normalizer.tokens_used["output"]
            + test_normalizer.tokens_used["output"],
        },
    }
    db.update_document_tokens(document_id, json.dumps(tokens))

    # Mark document as processed
    db.mark_document_processed(document_id)

    # Check if this is a form submission (redirect back)
    if request.form.get("redirect") or request.referrer and "/upload/user/" in request.referrer:
        return redirect(url_for("upload.user_documents", user_id=document.user_id))

    return jsonify({
        "document_id": document_id,
        "lab_id": lab.id,
        "lab_name": lab.name,
        "extracted_count": len(extracted_tests),
        "result_ids": result_ids,
        "message": "Document processed successfully.",
    })

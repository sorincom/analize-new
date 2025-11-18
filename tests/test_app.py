"""Basic application tests."""


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "healthy"}


def test_create_user(db):
    """Test user creation."""
    user_id = db.create_user(name="John Doe", sex="M", age=45)
    user = db.get_user(user_id)

    assert user is not None
    assert user.name == "John Doe"
    assert user.sex == "M"
    assert user.age == 45


def test_list_users(db):
    """Test listing users."""
    db.create_user(name="Alice", sex="F", age=30)
    db.create_user(name="Bob", sex="M", age=40)

    users = db.list_users()
    assert len(users) == 2
    names = [u.name for u in users]
    assert "Alice" in names
    assert "Bob" in names


def test_create_test_type(db):
    """Test creating test types."""
    test_id = db.create_test_type(
        standard_name="Blood Glucose",
        description="Measures blood sugar levels",
        category="Metabolic",
    )

    test_type = db.get_test_type_by_name("Blood Glucose")
    assert test_type is not None
    assert test_type.id == test_id
    assert test_type.standard_name == "Blood Glucose"
    assert test_type.category == "Metabolic"


def test_document_hash_detection(db, sample_user):
    """Test duplicate document detection by hash."""
    # Create first document
    doc_id = db.create_document(
        user_id=sample_user.id,
        file_path="/uploads/test.pdf",
        content_hash="abc123",
    )

    # Try to find by hash
    existing = db.get_document_by_hash("abc123")
    assert existing is not None
    assert existing.id == doc_id

    # Non-existent hash
    not_found = db.get_document_by_hash("xyz789")
    assert not_found is None

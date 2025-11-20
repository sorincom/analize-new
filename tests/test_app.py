"""Basic application tests."""


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json == {"status": "healthy"}


def test_create_user(db):
    """Test user creation."""
    user_id = db.create_user(name="John Doe", sex="M", date_of_birth="1979-01-15")
    user = db.get_user(user_id)

    assert user is not None
    assert user.name == "John Doe"
    assert user.sex == "M"
    assert user.date_of_birth.year == 1979
    assert user.age >= 45  # Age is computed


def test_list_users(db):
    """Test listing users."""
    db.create_user(name="Alice", sex="F", date_of_birth="1994-05-10")
    db.create_user(name="Bob", sex="M", date_of_birth="1984-08-20")

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


def test_create_lab(db):
    """Test lab creation."""
    lab_id = db.create_lab(
        name="MedLife Laboratory",
        address="123 Medical St",
        phone="+40-123-456-789",
    )

    lab = db.get_lab(lab_id)
    assert lab is not None
    assert lab.name == "MedLife Laboratory"
    assert lab.address == "123 Medical St"
    assert lab.phone == "+40-123-456-789"


def test_upsert_test_result(db, sample_user):
    """Test upserting test results."""
    # Create lab and test type
    lab_id = db.create_lab(name="Test Lab")
    test_type_id = db.create_test_type(standard_name="Blood Glucose")

    # Create document
    doc_id = db.create_document(
        user_id=sample_user.id,
        file_path="/uploads/test.pdf",
        content_hash="abc123",
        lab_id=lab_id,
    )

    # First insert
    result_id1, created1 = db.upsert_test_result(
        test_type_id=test_type_id,
        user_id=sample_user.id,
        document_id=doc_id,
        lab_id=lab_id,
        lab_test_name="Glucoza",
        test_date="2024-01-15",
        value=95.0,
        unit="mg/dL",
    )
    assert created1 is True

    # Try to insert same test (same user, type, date, lab)
    result_id2, created2 = db.upsert_test_result(
        test_type_id=test_type_id,
        user_id=sample_user.id,
        document_id=doc_id,
        lab_id=lab_id,
        lab_test_name="Glucoza",
        test_date="2024-01-15",
        value=96.0,  # Different value
        unit="mg/dL",
    )
    assert created2 is False
    assert result_id1 == result_id2  # Same result updated

    # Verify value was updated
    result = db.get_test_result(sample_user.id, test_type_id, "2024-01-15", lab_id)
    assert result is not None
    assert result.value == 96.0  # Updated value


def test_qualitative_result(db, sample_user):
    """Test qualitative (positive/negative) results."""
    # Create lab and test type
    lab_id = db.create_lab(name="Test Lab")
    test_type_id = db.create_test_type(standard_name="COVID-19 Antigen")

    # Create document
    doc_id = db.create_document(
        user_id=sample_user.id,
        file_path="/uploads/test.pdf",
        content_hash="xyz123",
        lab_id=lab_id,
    )

    # Insert qualitative result
    result_id, created = db.upsert_test_result(
        test_type_id=test_type_id,
        user_id=sample_user.id,
        document_id=doc_id,
        lab_id=lab_id,
        lab_test_name="COVID-19 Ag",
        test_date="2024-01-15",
        value=None,
        value_text="Pozitiv",
        value_normalized="POSITIVE",
        interpretation="Positive result indicates active SARS-CoV-2 infection",
    )
    assert created is True

    # Verify qualitative fields
    result = db.get_test_result(sample_user.id, test_type_id, "2024-01-15", lab_id)
    assert result is not None
    assert result.value is None
    assert result.value_text == "Pozitiv"
    assert result.value_normalized == "POSITIVE"
    assert result.interpretation is not None
    assert "SARS-CoV-2" in result.interpretation


def test_list_documents_for_user(db, sample_user):
    """Test listing documents for a user."""
    lab_id = db.create_lab(name="Test Lab")

    # Create multiple documents
    doc1 = db.create_document(
        user_id=sample_user.id,
        file_path="/uploads/test1.pdf",
        content_hash="hash1",
        lab_id=lab_id,
    )
    doc2 = db.create_document(
        user_id=sample_user.id,
        file_path="/uploads/test2.pdf",
        content_hash="hash2",
        lab_id=lab_id,
    )

    # List documents
    documents = db.list_documents_for_user(sample_user.id)
    assert len(documents) == 2
    assert documents[0].id in (doc1, doc2)
    assert documents[1].id in (doc1, doc2)

"""Pydantic schemas for data validation."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    """User profile."""

    id: int | None = None
    name: str
    sex: str = Field(pattern="^(M|F|O)$")
    age: int = Field(ge=0, le=150)
    created_at: datetime | None = None


class Document(BaseModel):
    """Uploaded document record."""

    id: int | None = None
    user_id: int
    file_path: str
    content_hash: str
    uploaded_at: datetime | None = None
    processed_at: datetime | None = None


class TestType(BaseModel):
    """Normalized test type registry."""

    id: int | None = None
    standard_name: str
    description: str | None = None
    category: str | None = None


class TestResult(BaseModel):
    """Individual test result."""

    id: int | None = None
    test_type_id: int
    user_id: int
    document_id: int
    lab_test_name: str
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    test_date: date
    lab_name: str | None = None
    documentation: str | None = None
    created_at: datetime | None = None


class ExtractedTest(BaseModel):
    """Test data extracted by LLM from PDF.

    This is used as intermediate format before normalization and storage.
    """

    lab_test_name: str
    lab_test_code: str | None = None
    suggested_standard_name: str
    value: float | None = None
    value_text: str | None = None
    unit: str | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    test_date: date
    lab_name: str | None = None
    documentation: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

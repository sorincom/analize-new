"""Pydantic schemas for data validation."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class User(BaseModel):
    """User profile."""

    id: int | None = None
    name: str
    sex: str = Field(pattern="^(M|F|O)$")
    date_of_birth: date
    created_at: datetime | None = None

    @property
    def age(self) -> int:
        """Calculate age from date of birth."""
        from datetime import date as date_type

        today = date_type.today()
        age = today.year - self.date_of_birth.year
        if (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day):
            age -= 1
        return age


class Lab(BaseModel):
    """Laboratory information."""

    id: int | None = None
    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    accreditation: str | None = None
    created_at: datetime | None = None


class Document(BaseModel):
    """Uploaded document record."""

    id: int | None = None
    user_id: int
    lab_id: int | None = None
    file_path: str
    content_hash: str
    uploaded_at: datetime | None = None
    processed_at: datetime | None = None
    tokens: str | None = None  # JSON string: {"model_name": {"input": X, "output": Y}}
    cost: float | None = None


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
    lab_id: int
    lab_test_name: str
    value: float | None = None
    value_text: str | None = None
    value_normalized: str | None = None  # Normalized qualitative value
    unit: str | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    test_date: date
    interpretation: str | None = None  # What this result means
    documentation: str | None = None
    created_at: datetime | None = None


class ExtractedLab(BaseModel):
    """Lab information extracted from document header/footer."""

    name: str
    address: str | None = None
    phone: str | None = None
    email: str | None = None
    accreditation: str | None = None


class ExtractedTest(BaseModel):
    """Test data extracted by LLM from PDF.

    This is used as intermediate format before normalization and storage.
    Lab info is extracted separately at document level.
    """

    lab_test_name: str
    lab_test_code: str | None = None
    suggested_standard_name: str
    value: float | None = None
    value_text: str | None = None
    value_normalized: str | None = None  # POSITIVE, NEGATIVE, NORMAL, ABNORMAL, etc.
    unit: str | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    test_date: date
    interpretation: str | None = None  # Clinical interpretation of the result
    documentation: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)

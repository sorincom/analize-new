"""Test normalization - map lab names to standard names."""

from google import genai
from google.genai import types

from analize.mcp import DatabaseMCP
from analize.models.schemas import ExtractedTest, TestType

NORMALIZATION_PROMPT = """You are a medical test normalization system.

Given a lab test name and a list of existing standard test names in the database,
determine if the lab test matches any existing standard name.

Lab test name: {lab_test_name}
Suggested standard name: {suggested_name}

Existing standard names in database:
{existing_names}

Consider:
- Different languages (e.g., "Glucoza" = "Blood Glucose")
- Different naming conventions (e.g., "CBC" = "Complete Blood Count")
- Common abbreviations
- Regional variations

If the test matches an existing standard name, respond with:
{{"match": true, "standard_name": "<existing name>"}}

If it's a new test not in the database, respond with:
{{"match": false, "standard_name": "<suggested standard name>"}}

Return ONLY the JSON object.
"""


class TestNormalizer:
    """Normalize lab test names to standard medical names.

    Uses LLM to identify if a test already exists under a different name,
    preventing duplicates across different labs.
    """

    def __init__(self, db: DatabaseMCP, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.db = db
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def get_or_create_test_type(self, extracted: ExtractedTest) -> TestType:
        """Get existing test type or create new one.

        Uses LLM to determine if the test matches an existing standard name.

        Args:
            extracted: Extracted test data from PDF

        Returns:
            TestType with the matched or newly created test type
        """
        # Get all existing test types
        existing_types = self.db.list_test_types()

        if not existing_types:
            # No existing tests - create new one
            test_id = self.db.create_test_type(
                standard_name=extracted.suggested_standard_name,
                category=None,
            )
            return TestType(
                id=test_id,
                standard_name=extracted.suggested_standard_name,
            )

        # Ask LLM to match
        existing_names = "\n".join([f"- {t.standard_name}" for t in existing_types])

        prompt = NORMALIZATION_PROMPT.format(
            lab_test_name=extracted.lab_test_name,
            suggested_name=extracted.suggested_standard_name,
            existing_names=existing_names,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )

        import json

        try:
            result = json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback to suggested name
            result = {"match": False, "standard_name": extracted.suggested_standard_name}

        if result.get("match"):
            # Find the existing test type
            standard_name = result["standard_name"]
            for t in existing_types:
                if t.standard_name == standard_name:
                    return t

        # Create new test type
        test_id = self.db.create_test_type(
            standard_name=result["standard_name"],
            category=None,
        )
        return TestType(
            id=test_id,
            standard_name=result["standard_name"],
        )

    def normalize_and_store(
        self,
        user_id: int,
        document_id: int,
        extracted_tests: list[ExtractedTest],
    ) -> list[int]:
        """Normalize extracted tests and store in database.

        Args:
            user_id: User ID
            document_id: Document ID
            extracted_tests: List of extracted test data

        Returns:
            List of created test result IDs
        """
        result_ids = []

        for extracted in extracted_tests:
            # Get or create normalized test type
            test_type = self.get_or_create_test_type(extracted)

            # Store the result
            result_id = self.db.create_test_result(
                test_type_id=test_type.id,  # type: ignore[arg-type]
                user_id=user_id,
                document_id=document_id,
                lab_test_name=extracted.lab_test_name,
                test_date=str(extracted.test_date),
                value=extracted.value,
                value_text=extracted.value_text,
                unit=extracted.unit,
                lower_limit=extracted.lower_limit,
                upper_limit=extracted.upper_limit,
                lab_name=extracted.lab_name,
                documentation=extracted.documentation,
            )
            result_ids.append(result_id)

        # Mark document as processed
        self.db.mark_document_processed(document_id)

        return result_ids

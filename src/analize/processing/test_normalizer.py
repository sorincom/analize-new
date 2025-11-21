"""Test normalization - map lab names to standard names."""

from anthropic import Anthropic

from analize.dal import Database
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

    def __init__(
        self, db: Database, api_key: str, model: str = "claude-haiku-4-5"
    ) -> None:
        self.db = db
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.tokens_used = {"input": 0, "output": 0}

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

        response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            temperature=0.0,
            messages=[{"role": "user", "content": prompt}],
        )

        # Track tokens
        self.tokens_used["input"] += response.usage.input_tokens
        self.tokens_used["output"] += response.usage.output_tokens

        import json

        try:
            result = json.loads(response.content[0].text)
        except json.JSONDecodeError:
            # Fallback to suggested name
            result = {"match": False, "standard_name": extracted.suggested_standard_name}

        if result.get("match"):
            # Find the existing test type
            standard_name = result["standard_name"]
            for t in existing_types:
                if t.standard_name == standard_name:
                    return t

        # Before creating new test type, check for exact name match
        # (fallback in case LLM incorrectly said no match)
        standard_name = result["standard_name"]
        for t in existing_types:
            if t.standard_name.lower() == standard_name.lower():
                return t

        # Create new test type
        test_id = self.db.create_test_type(
            standard_name=standard_name,
            category=None,
        )
        return TestType(
            id=test_id,
            standard_name=standard_name,
        )

    def normalize_and_store(
        self,
        user_id: int,
        document_id: int,
        lab_id: int,
        extracted_tests: list[ExtractedTest],
    ) -> list[int]:
        """Normalize extracted tests and store in database.

        Args:
            user_id: User ID
            document_id: Document ID
            lab_id: Lab ID (already normalized)
            extracted_tests: List of extracted test data

        Returns:
            List of created test result IDs
        """
        result_ids = []

        for extracted in extracted_tests:
            # Get or create normalized test type
            test_type = self.get_or_create_test_type(extracted)

            # Store the result (upsert - handles historical data from multiple docs)
            result_id, created = self.db.upsert_test_result(
                test_type_id=test_type.id,  # type: ignore[arg-type]
                user_id=user_id,
                document_id=document_id,
                lab_id=lab_id,
                lab_test_name=extracted.lab_test_name,
                test_date=str(extracted.test_date),
                value=extracted.value,
                value_text=extracted.value_text,
                value_normalized=extracted.value_normalized,
                unit=extracted.unit,
                lower_limit=extracted.lower_limit,
                upper_limit=extracted.upper_limit,
                clinical_status=extracted.clinical_status,
                interpretation=extracted.interpretation,
                documentation=extracted.documentation,
                raw_text=extracted.raw_text,
            )
            result_ids.append(result_id)

        # Mark document as processed
        self.db.mark_document_processed(document_id)

        return result_ids

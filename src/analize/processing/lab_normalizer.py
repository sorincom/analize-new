"""Lab normalization - deduplicate labs using LLM."""

import json

from anthropic import Anthropic

from analize.dal import Database
from analize.models.schemas import ExtractedLab, Lab

LAB_NORMALIZATION_PROMPT = """You are a laboratory normalization system.

Given lab information extracted from a document and a list of existing labs in the database,
determine if this lab matches any existing lab.

Extracted lab info:
Name: {lab_name}
Address: {address}
Phone: {phone}

Existing labs in database:
{existing_labs}

Consider:
- Different address formats (abbreviations, etc.)
- Same lab, different locations (treat as separate)
- Minor variations in name (e.g., "MedLife Lab" vs "MedLife Laboratory")

If the lab matches an existing one, respond with:
{{"match": true, "lab_id": <existing lab id>}}

If it's a new lab not in the database, respond with:
{{"match": false}}

Return ONLY the JSON object.
"""


class LabNormalizer:
    """Normalize lab info to avoid duplicates.

    Uses LLM to identify if a lab already exists with minor variations.
    """

    def __init__(
        self, db: Database, api_key: str, model: str = "claude-haiku-4-5"
    ) -> None:
        self.db = db
        self.client = Anthropic(api_key=api_key)
        self.model = model
        self.tokens_used = {"input": 0, "output": 0}

    def get_or_create_lab(self, extracted: ExtractedLab) -> Lab:
        """Get existing lab or create new one.

        Uses LLM to determine if the lab matches an existing one.

        Args:
            extracted: Extracted lab data from PDF

        Returns:
            Lab with the matched or newly created lab
        """
        # Get all existing labs
        existing_labs = self.db.list_labs()

        if not existing_labs:
            # No existing labs - create new one
            lab_id = self.db.create_lab(
                name=extracted.name,
                address=extracted.address,
                phone=extracted.phone,
                email=extracted.email,
                accreditation=extracted.accreditation,
            )
            return Lab(
                id=lab_id,
                name=extracted.name,
                address=extracted.address,
                phone=extracted.phone,
                email=extracted.email,
                accreditation=extracted.accreditation,
            )

        # Ask LLM to match
        existing_labs_str = "\n".join(
            [
                f"- ID: {lab.id}, Name: {lab.name}, Address: {lab.address}, Phone: {lab.phone}"
                for lab in existing_labs
            ]
        )

        prompt = LAB_NORMALIZATION_PROMPT.format(
            lab_name=extracted.name,
            address=extracted.address or "Not provided",
            phone=extracted.phone or "Not provided",
            existing_labs=existing_labs_str,
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

        try:
            result = json.loads(response.content[0].text)
        except json.JSONDecodeError:
            # Fallback to creating new lab
            result = {"match": False}

        if result.get("match"):
            # Find the existing lab
            lab_id = result["lab_id"]
            for lab in existing_labs:
                if lab.id == lab_id:
                    return lab
            # If not found, create new (shouldn't happen)
            result = {"match": False}

        # Create new lab
        lab_id = self.db.create_lab(
            name=extracted.name,
            address=extracted.address,
            phone=extracted.phone,
            email=extracted.email,
            accreditation=extracted.accreditation,
        )
        return Lab(
            id=lab_id,
            name=extracted.name,
            address=extracted.address,
            phone=extracted.phone,
            email=extracted.email,
            accreditation=extracted.accreditation,
        )

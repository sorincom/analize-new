"""PDF extraction using Gemini vision."""

import json
from pathlib import Path

from google import genai
from google.genai import types

from analize.models.schemas import ExtractedTest

EXTRACTION_PROMPT = """Analyze this medical lab report PDF and extract all test results.

For each test, provide:
- lab_test_name: The exact name as printed on the report
- lab_test_code: Any code/identifier shown (optional)
- suggested_standard_name: Your suggestion for the standard medical name
- value: Numeric value (null if non-numeric)
- value_text: Text value for non-numeric results (e.g., "Positive", "Normal")
- unit: Unit of measurement
- lower_limit: Lower reference range (null if not shown)
- upper_limit: Upper reference range (null if not shown)
- test_date: Date the test was performed (YYYY-MM-DD)
- lab_name: Name of the laboratory
- documentation: Any notes or comments about this specific test
- confidence: Your confidence in the extraction (0.0 to 1.0)

Return a JSON array of test objects. Example:
[
  {
    "lab_test_name": "Glucoza",
    "lab_test_code": "GLU",
    "suggested_standard_name": "Blood Glucose",
    "value": 95.0,
    "value_text": null,
    "unit": "mg/dL",
    "lower_limit": 70.0,
    "upper_limit": 100.0,
    "test_date": "2024-01-15",
    "lab_name": "MedLife",
    "documentation": null,
    "confidence": 0.95
  }
]

Important:
- Extract ALL tests from the document
- Use consistent date format (YYYY-MM-DD)
- For suggested_standard_name, use English medical terminology
- If multiple pages, combine all results
- Return ONLY the JSON array, no other text
"""


class PDFExtractor:
    """Extract test data from PDF using Gemini vision."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def extract_from_pdf(self, pdf_path: Path) -> list[ExtractedTest]:
        """Extract test results from a PDF file.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            List of extracted test data
        """
        # Upload the PDF
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Create the request with PDF
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                        types.Part.from_text(text=EXTRACTION_PROMPT),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for consistent extraction
                response_mime_type="application/json",
            ),
        )

        # Parse response
        try:
            result_text = response.text
            tests_data = json.loads(result_text)
            return [ExtractedTest(**test) for test in tests_data]
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Failed to parse LLM response: {e}") from e

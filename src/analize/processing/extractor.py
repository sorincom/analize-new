"""PDF extraction using Gemini vision."""

import json
from pathlib import Path

from google import genai
from google.genai import types

from analize.models.schemas import ExtractedLab, ExtractedTest

LAB_EXTRACTION_PROMPT = """Analyze this medical lab report PDF and extract the laboratory information from the header/footer.

Extract:
- name: Laboratory name
- address: Full address (if shown)
- phone: Phone number (if shown)
- email: Email address (if shown)
- accreditation: Any accreditation info (if shown)

Return a JSON object. Example:
{{
  "name": "MedLife Laboratory",
  "address": "123 Medical Center Dr, City, Country",
  "phone": "+40-XXX-XXX-XXX",
  "email": "contact@medlife.ro",
  "accreditation": "ISO 15189"
}}

Return ONLY the JSON object, no other text.
"""

TEST_EXTRACTION_PROMPT = """Analyze this medical lab report PDF and extract all test results.

PATIENT CONTEXT:
- Sex: {patient_sex}
- Age: {patient_age} years

For each test, provide:
- lab_test_name: The exact name as printed on the report
- lab_test_code: Any code/identifier shown (optional)
- suggested_standard_name: Your suggestion for the standard medical name
- value: Numeric value (null if non-numeric)
- value_text: Text value for non-numeric results (e.g., "Pozitiv", "Normal", "Negative")
- value_normalized: Normalized version of value_text using standard values:
  * POSITIVE, NEGATIVE, NORMAL, ABNORMAL, DETECTED, NOT_DETECTED, REACTIVE, NON_REACTIVE,
  * PRESENT, ABSENT, HIGH, LOW, BORDERLINE
  * (null if numeric result)
- unit: Unit of measurement
- lower_limit: Lower reference range (null if not shown)
- upper_limit: Upper reference range (null if not shown)
- test_date: Date the test was performed (YYYY-MM-DD)
- clinical_status: Clinical assessment of this result considering patient's age and sex:
  * NORMAL: Result is clinically normal/optimal for this patient
  * BORDERLINE: Result is suboptimal, insufficient, or warrants monitoring
  * ABNORMAL: Result is outside healthy range, deficient, or concerning
  * Consider age-specific and sex-specific ranges when available
  * For multi-level ranges (e.g., deficient/insufficient/optimal), use the optimal range
  * Examples: Vitamin D 20-29 is "insufficient" → BORDERLINE, not NORMAL
- interpretation: Clinical interpretation of what this result means for this specific test
  * For qualitative: explain what positive/negative means
  * For quantitative: explain if value is normal/abnormal and clinical significance
  * Examples: "Positive indicates active COVID-19 infection", "Elevated glucose suggests diabetes risk"
- documentation: Any notes or comments about this specific test
- raw_text: The complete original text from the report for this test (including test name, value, ranges, notes, etc.)
- confidence: Your confidence in the extraction (0.0 to 1.0)

Return a JSON array of test objects. Example:
[
  {{
    "lab_test_name": "COVID-19 Ag",
    "lab_test_code": "CV19",
    "suggested_standard_name": "SARS-CoV-2 Antigen Test",
    "value": null,
    "value_text": "Pozitiv",
    "value_normalized": "POSITIVE",
    "unit": null,
    "lower_limit": null,
    "upper_limit": null,
    "test_date": "2024-01-15",
    "clinical_status": "ABNORMAL",
    "interpretation": "Positive result indicates active SARS-CoV-2 infection detected",
    "documentation": null,
    "raw_text": "COVID-19 Ag (CV19): Pozitiv",
    "confidence": 0.98
  }},
  {{
    "lab_test_name": "Glucoza",
    "lab_test_code": "GLU",
    "suggested_standard_name": "Blood Glucose",
    "value": 125.0,
    "value_text": null,
    "value_normalized": null,
    "unit": "mg/dL",
    "lower_limit": 70.0,
    "upper_limit": 100.0,
    "test_date": "2024-01-15",
    "clinical_status": "ABNORMAL",
    "interpretation": "Elevated fasting glucose above normal range, suggests impaired glucose metabolism or diabetes",
    "documentation": null,
    "raw_text": "Glucoza (GLU): 125.0 mg/dL | Interval: 70.0-100.0 mg/dL",
    "confidence": 0.95
  }}
]

Important:
- Extract ALL tests from the document
- Use consistent date format (YYYY-MM-DD)
- For suggested_standard_name, use English medical terminology
- Normalize ALL qualitative values (Pozitiv → POSITIVE, Negativ → NEGATIVE, etc.)
- Use English for units of measurement (where applicable)
- Provide clinical interpretation for every result
- If multiple pages, combine all results
- Extract historical data from graphs/charts if present
- Return ONLY the JSON array, no other text
"""


class PDFExtractor:
    """Extract lab info and test data from PDF using Gemini vision."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model = model
        self.tokens_used = {"input": 0, "output": 0}

    def _extract_with_prompt(self, pdf_bytes: bytes, prompt: str) -> str:
        """Generic extraction method."""
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Content(
                    parts=[
                        types.Part.from_bytes(
                            data=pdf_bytes, mime_type="application/pdf"
                        ),
                        types.Part.from_text(text=prompt),
                    ]
                )
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,  # Low temperature for consistent extraction
                response_mime_type="application/json",
            ),
        )

        # Track tokens if available
        if hasattr(response, "usage_metadata"):
            self.tokens_used["input"] += response.usage_metadata.prompt_token_count
            self.tokens_used["output"] += response.usage_metadata.candidates_token_count

        return response.text

    def extract_lab_from_pdf(self, pdf_path: Path) -> ExtractedLab:
        """Extract laboratory information from PDF header/footer.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            Extracted lab information
        """
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        try:
            result_text = self._extract_with_prompt(pdf_bytes, LAB_EXTRACTION_PROMPT)
            lab_data = json.loads(result_text)
            return ExtractedLab(**lab_data)
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(f"Failed to parse lab info from LLM response: {e}") from e

    def extract_tests_from_pdf(
        self, pdf_path: Path, patient_sex: str = "Unknown", patient_age: int | None = None
    ) -> list[ExtractedTest]:
        """Extract test results from a PDF file.

        Args:
            pdf_path: Path to the PDF file
            patient_sex: Patient sex (M/F/O) for context
            patient_age: Patient age for age-specific ranges

        Returns:
            List of extracted test data
        """
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        # Format prompt with patient context
        prompt = TEST_EXTRACTION_PROMPT.format(
            patient_sex=patient_sex, patient_age=patient_age or "Unknown"
        )

        try:
            result_text = self._extract_with_prompt(pdf_bytes, prompt)
            tests_data = json.loads(result_text)
            return [ExtractedTest(**test) for test in tests_data]
        except (json.JSONDecodeError, TypeError) as e:
            raise ValueError(
                f"Failed to parse test results from LLM response: {e}"
            ) from e

    def extract_from_pdf(
        self,
        pdf_path: Path,
        patient_sex: str = "Unknown",
        patient_age: int | None = None,
    ) -> tuple[ExtractedLab, list[ExtractedTest]]:
        """Extract both lab info and test results from PDF.

        Args:
            pdf_path: Path to the PDF file
            patient_sex: Patient sex (M/F/O) for context
            patient_age: Patient age for age-specific ranges

        Returns:
            Tuple of (lab_info, test_results)
        """
        lab_info = self.extract_lab_from_pdf(pdf_path)
        test_results = self.extract_tests_from_pdf(pdf_path, patient_sex, patient_age)
        return (lab_info, test_results)

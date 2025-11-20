# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Medical test analysis application that uses LLM vision (Gemini 2.5) to extract and normalize lab test results from PDF uploads.

## Tech Stack

- **Backend**: Flask
- **Database**: SQLite (accessed via DAL module only)
- **LLM**:
  - Gemini 2.5 Flash (vision for PDF extraction)
  - Claude Haiku 4.5 (text normalization)
- **Language**: Python
- **Package/Env Management**: uv with pyproject.toml

## Architecture

### Core Modules

1. **DAL Module** (`dal/`)
   - Data Access Layer - sole interface to SQLite database
   - Flask app must NOT access database directly
   - All CRUD operations go through DAL

2. **Upload Module** (`upload/`)
   - Web UI for document upload and processing
   - PDF upload and local storage
   - Content hash tracking for deduplication
   - Allows cleanup/reload when same file is reprocessed
   - Shows upload history per user with processing status
   - Both API and web UI support

3. **Processing Module** (`processing/`)
   - **PDFExtractor**: Gemini vision extraction from PDFs (lab info + test data)
   - **LabNormalizer**: Claude-based lab deduplication
   - **TestNormalizer**: Claude-based test name normalization
   - Lab info extraction from document header/footer
   - Test data parsing: date, values, limits, documentation
   - Historic data extraction: some PDFs contain historical results (as text or graphs) - extract those too
   - Token tracking: tracks usage per model for cost analysis

4. **Users Module** (`users/`)
   - Web UI for user management
   - Create and list users

5. **Visualization Module** (`visualization/`)
   - List view of all tests
   - Vertical timeline per test showing results over time

### Data Model

**Users** (no authentication, just differentiation)
- name, sex, date_of_birth (age computed as property)

**Labs** (normalized laboratory registry)
- id, name, address, phone, email, accreditation
- Uses NLP to match labs and prevent duplicates (e.g., "MedLife Lab" = "MedLife Laboratory")

**Documents**
- file path, content hash, user_id, lab_id, upload date
- Hash enables detecting reprocessed files
- Lab extracted from document header/footer

**Tests** (normalized test registry)
- id, standard_name (medical standard)
- Uses NLP to match incoming tests to existing entries
- Prevents duplicates across different lab naming conventions

**Test Results**
- test_id, user_id, document_id, lab_id
- lab_test_name (original name from lab)
- Quantitative: value, unit, lower_limit, upper_limit
- Qualitative: value_text, value_normalized (POSITIVE/NEGATIVE/etc.)
- interpretation (clinical meaning of the result)
- test_date
- documentation (if provided in report)

### Test Normalization Logic

When processing a new test result:
1. Extract lab's test code/name from PDF
2. Query existing tests using NLP similarity
3. If match found: use existing test_id
4. If no match: create new test with standard medical name, assign new id
5. Always store lab's original name alongside for traceability

This aligns tests across labs (e.g., "CBC", "Complete Blood Count", "Hemogram" → same test_id).

### Lab Extraction and Normalization

**Lab info is extracted once per document:**
- Extracted from PDF header/footer (not per-test)
- LLM identifies matching labs to avoid duplicates
- Labs table stores: name, address, phone, email, accreditation
- Documents reference their source lab

### Qualitative Results Handling

**Positive/Negative tests are properly handled:**
- `value_text`: Original text from lab (e.g., "Pozitiv", "Negativ")
- `value_normalized`: Standardized value (POSITIVE, NEGATIVE, NORMAL, ABNORMAL, DETECTED, NOT_DETECTED, etc.)
- `interpretation`: Clinical meaning (e.g., "Positive indicates active COVID-19 infection")
- LLM normalizes different languages/formats to standard values
- Visualization uses `value_normalized` to determine status (normal/abnormal/borderline)
- Timeline shows both original and normalized values plus interpretation

### Natural Key and Historical Data Handling

**Critical design decision:**

Test results use natural key: **(user_id, test_type_id, test_date, lab_id)**

Why this matters:
- A person's test on a specific date is ONE piece of data
- Multiple documents can reference the same result (original report, later historical graphs)
- Using `document_id` in the unique constraint would create duplicates

Example scenario:
1. Document A from Jan 2024 shows glucose test from Jan 2024
2. Document B from Mar 2024 shows historical graph with glucose from Jan 2024
3. Both reference the SAME test result → stored once, not twice

**Implementation:**
- `upsert_test_result()` checks natural key before insert
- If exists: updates values (document_id tracks latest reference)
- If new: creates result
- The unique constraint prevents duplicates at DB level

### Database Schema Versioning

**Schema evolution without migration hell:**

The database uses a simple versioning system:
- `schema_version` table tracks current schema (currently version 1)
- On startup, DAL checks for schema version
- If old schema detected (e.g., 'age' column instead of 'date_of_birth'), raises clear error
- User deletes old database and restarts with fresh schema
- Tests always use fresh temporary databases, so they always pass

This approach works because:
- Early development - no production data to preserve
- Breaking changes are rare
- Clear error message tells user exactly what to do
- Future: can add proper migration code as needed

**Schema versions:**

**v1:**
- Changed from storing `age` to storing `date_of_birth`
- Age now computed as property when User object is created
- Can't auto-migrate (can't calculate exact birth date from age)
- Solution: delete database file and restart

**v2:**
- Added `tokens` (TEXT/JSON) and `cost` (REAL) columns to documents table
- Tokens JSON format: `{"model_name": {"input": X, "output": Y}}`
- Tracks token usage per model for cost analysis
- Cost calculation not yet implemented

## Development Commands

```bash
# Setup environment and install dependencies
uv sync

# Run development server
uv run flask run --debug

# Run tests
uv run pytest

# Run single test
uv run pytest tests/test_file.py::test_function -v

# Add dependency
uv add <package>

# Add dev dependency
uv add --dev <package>
```

## Questions / Clarifications / Suggestions

### Questions

1. **PDF storage location**: Local filesystem path? Configurable? Should old PDFs be auto-cleaned after X days?

2. **User management**: How are users created? CLI? Simple web form? Pre-seeded?

3. **Gemini API**: Rate limiting strategy? Batch processing for large PDFs? Retry logic?

4. **Test limits**: Are limits always numeric? How to handle qualitative results (Positive/Negative)?

5. **Multi-page PDFs**: Process as single document or split by test date if multiple dates present?

### Suggestions

1. **Add reference ranges by demographics**: Limits often vary by sex/age. Store these and flag results that are abnormal for the specific user.

2. **Confidence scores**: Have LLM return confidence for extracted values. Flag low-confidence extractions for human review.

3. **Export functionality**: CSV/PDF export of test history for sharing with doctors.

4. **Trend alerts**: Notify when a value is trending in a concerning direction across multiple tests.

5. **Test categories**: Group tests (Lipid Panel, Liver Function, etc.) for better visualization.

6. **OCR fallback**: Some PDFs are scanned images. Consider Tesseract as fallback if Gemini struggles.

7. **Audit log**: Track all processing runs, especially for reprocessed files, to debug normalization issues.

## Original Prompt

> init a flask app which will be using a llm (gemini 2.5) for uploading and processing medical tests
> - the db backend will be sqlite
> - the app will support users (no auth, just for differentiating) with profiles: name, sex, age
> - upload: upload pdfs, store them locally, track them in a sql table; content hashes will be also stored, to allow the cleanup/reload of data if a file is processed multiple times
> - processing: llm vision, extract all test data, store data in sqlite
> - processing data should track the test date and the lab having performed it, the user, the limits, the values, the documentation - if any
> - storing test data: the llm should extract the test code/name and assign to it a new id and the standard (medically) test name; data should be stored under this id and with the standard name; but first, it should ask himself if the same test isn't already stored under the same name or a different one (use nlp abilities for that), to avoid duplicates; for tracking, store lab's test name too additionally to the standard name; some normalization will be required to align tests performed by different labs
> - the app will have a dal module for working with the database (aka the app will not access directly the database)
> - the app will also have a visualization module: list of tests, vertical timeline with results for each test

# Analize

Medical test analysis application using LLM vision (Gemini 2.5) to extract and normalize lab test results from PDF uploads.

## Features

- **Web UI** for user management
- PDF upload with hash-based deduplication
- LLM vision extraction of test results
- Lab information extraction and normalization
- Intelligent test normalization across labs
- Qualitative (positive/negative) and quantitative results
- Clinical interpretation for all results
- Historical data handling (prevents duplicates from multiple documents)
- Visualization: test lists and timelines
- **Token tracking** per document (tracks usage per model)
- **Dual LLM usage**: Gemini for vision, Anthropic for normalization

## Setup

```bash
# Copy environment template
cp .env.example .env

# Add your API keys to .env
# GEMINI_API_KEY=your-gemini-key (for PDF vision extraction)
# ANTHROPIC_API_KEY=your-anthropic-key (for text normalization)

# Install dependencies
uv sync

# Run development server
uv run flask run --debug

# Run tests
uv run pytest
```

## Database Schema

The database uses SQLite with schema versioning. If you see an error about outdated schema, delete the database file and restart:

```bash
rm analize.db
uv run flask run --debug
```

Current schema version: 2
- v1: Stores date of birth (computes age dynamically)
- v2: Token and cost tracking per document

## Usage

1. **Start the server:**
   ```bash
   uv run flask run --debug
   ```

2. **Open browser:** http://localhost:5000

3. **Create a user:**
   - Navigate to Users → Create New User
   - Fill in name, sex, and date of birth
   - Age is computed automatically

4. **Upload PDF:**
   - Navigate to Upload
   - Select a user from the list
   - Choose PDF file and upload
   - Click "Process" to extract test results

5. **View results:**
   - After processing, click "View Results"
   - See list of all tests with latest values
   - Click "View Timeline →" for any test to see:
     - Vertical timeline of all results
     - Color-coded status (green=normal, red=abnormal, yellow=borderline)
     - Reference ranges for quantitative tests
     - Clinical interpretation for each result

## API Endpoints

For programmatic access:

```bash
# Upload PDF
curl -X POST http://localhost:5000/upload/upload \
  -F "file=@test.pdf" \
  -F "user_id=1"

# Process document
curl -X POST http://localhost:5000/upload/process/1

# View test results
curl http://localhost:5000/viz/users/1/tests
```

## Project Structure

```
src/analize/
├── dal/            # Data Access Layer (database interface)
├── models/         # Pydantic schemas
├── upload/         # PDF upload routes
├── processing/     # LLM extraction and normalization
└── visualization/  # Result viewing endpoints
```

## LLM Usage

**Gemini 2.5 Flash** (vision):
- Extracts lab info from PDF headers/footers
- Extracts test results with clinical interpretation
- Handles both text and graphical data

**Claude Haiku 4.5** (text normalization):
- Lab deduplication (matches "MedLife Lab" = "MedLife Laboratory")
- Test normalization (maps lab-specific names to standard medical terms)
- Much better rate limits than Gemini for text tasks

**Token tracking**: Each document stores token usage per model as JSON:
```json
{
  "gemini-2.5-flash": {"input": 5120, "output": 850},
  "claude-haiku-4-5": {"input": 1200, "output": 150}
}
```

Cost calculation can be added later based on current pricing.

See `CLAUDE.md` for detailed architecture and development guidance.

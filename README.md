# Multi-Source Candidate Data ETL Pipeline

A deterministic, explainable, and scalable backend pipeline that extracts candidate information from multiple structured and unstructured sources, merges them into a clean canonical profile, and handles complex edge cases without crashing.

## Features

- **6 Source Adapters** — CSV, ATS JSON, Resume PDF, Resume DOCX, Recruiter Notes TXT, GitHub Profile
- **Deterministic Merging** — Same input always produces same output via priority-based conflict resolution
- **Explainable** — Every output field has provenance (source, method, confidence, alternatives)
- **Strictest Normalization** — Advanced fallback logic for phones (defaults to India `+91`), locations (defaults to Indian states), and strict regex boundaries to prevent garbage extraction.
- **Runtime Configurable Output** — Select, rename, transform fields via `custom.json` without modifying core code.
- **Robust Error Handling** — Empty files, malformed JSON, or extra CSV columns degrade gracefully instead of crashing.
- **Interactive UI** — Streamlit web dashboard for real-time file uploads and pipeline execution.

## Quick Start

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the Streamlit Web App (Recommended)
streamlit run app.py

# 4. Or run the CLI with sample data
python main.py --demo --config output_configs/custom.json
```

## Architecture

```text
Sources → Extract (Adapters) → Normalize → Merge → Score → Provenance → Project → Validate → Output
```

| Stage | Description |
|-------|-------------|
| **Ingest** | Adapters extract raw data into `SourceRecord` (flat intermediate representation). Uses parallel thread execution. |
| **Normalize** | Pure functions normalize each field (e.g. converting "Bengaluru, KA" to "Karnataka, India"). |
| **Merge** | Priority-based deterministic merge into one `CanonicalProfile`. Resolves conflicts mathematically. |
| **Score** | Confidence = source_trust × extraction_quality + agreement_bonus. |
| **Provenance** | Records source, method, confidence, timestamp, alternatives for every field. Zero data loss. |
| **Project** | Applies runtime `config.json` (field mapping, renaming). |
| **Validate** | Checks python types and enforces required fields before final output. |

## Runtime Output Configuration

The pipeline's final payload is dynamically driven by a JSON config file.

```json
{
  "version": "1.0",
  "fields": [
    {"path": "candidateName", "from": "full_name", "type": "string", "required": true},
    {"path": "primaryEmail", "from": "emails[0]", "type": "string"},
    {"path": "phoneNumbers", "from": "phones", "type": "string[]"},
    {"path": "technicalSkills", "from": "skills[].name", "type": "string[]"}
  ],
  "include_provenance": false,
  "include_confidence": true,
  "on_missing": "null"
}
```

| Option | Values | Description |
|--------|--------|-------------|
| `include_provenance` | `true/false` | Include/exclude transparency tracking data |
| `include_confidence` | `true/false` | Include/exclude generated confidence scores |
| `on_missing` | `"null"`, `"omit"` | How to handle missing data to prevent schema breaking |

## Project Structure

```text
ETL/
├── app.py                      # Interactive Streamlit Dashboard
├── main.py                     # CLI entry point
├── src/
│   ├── pipeline.py             # Pipeline orchestrator
│   ├── registry.py             # Dynamic adapter registry
│   ├── logger.py               # Structured logging
│   ├── schema/                 # Dataclasses (CanonicalProfile, SourceRecord)
│   ├── adapters/               # Extractor classes (PDF, TXT, JSON, CSV, GitHub)
│   ├── normalizers/            # Regex cleaners (Phones, Emails, Locations)
│   ├── merger/                 # Conflict resolution engine
│   ├── provenance/             # Data transparency tracker
│   ├── projection/             # Dynamic JSON projection mapping
│   └── validation/             # Strict type enforcement
├── config/                     # YAML trust priorities & aliases
├── output_configs/             # Runtime customer JSON mappings
└── tests/
    └── edge_cases/             # The 20 edge-case test suite
```

## Testing

The system is validated against a rigorous 20-edge-case test suite covering everything from malformed files to duplicate data:

```bash
# Run the complete test suite
pytest -v tests/edge_cases/test_assignment_20_edges.py
```

## Tech Stack

- **Python 3.11+**
- **Streamlit** — Web interface
- **pdfplumber** — PDF text extraction
- **phonenumbers** — Multi-country E.164 phone validation
- **PyYAML** — Config file loading
- **pytest** — Testing framework

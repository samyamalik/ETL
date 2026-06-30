# Multi-Source Candidate Data Transformer

A deterministic, explainable, scalable backend that combines candidate information from multiple structured and unstructured sources into one clean canonical profile.

## Features

- **6 Source Adapters** — CSV, ATS JSON, Resume PDF, Resume DOCX, Recruiter Notes TXT, GitHub Profile
- **Deterministic Merging** — Same input always produces same output via priority-based conflict resolution
- **Explainable** — Every output field has provenance (source, method, confidence, alternatives)
- **Confidence Scoring** — Per-field scores based on source trust × extraction quality × agreement bonus
- **Runtime Configurable Output** — Select, rename, transform fields without affecting the pipeline
- **Robust Error Handling** — Malformed input degrades gracefully; bad config fails fast
- **Scalable** — Batch processing with parallel workers via ThreadPoolExecutor

## Quick Start

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run with sample data
python main.py --demo

# 4. Run with custom output config
python main.py --demo --config custom.json

# 5. Run tests
python -m pytest tests/ -v
```

## Architecture

```
Sources → Adapters → Normalize → Merge → Score → Provenance → Project → Validate → Output
```

| Stage | Description |
|-------|-------------|
| **Ingest** | Adapters extract raw data into `SourceRecord` (flat intermediate representation) |
| **Normalize** | Pure functions normalize each field (emails, phones, skills, dates, etc.) |
| **Merge** | Priority-based deterministic merge into one `CanonicalProfile` |
| **Score** | Confidence = source_trust × extraction_quality + agreement_bonus |
| **Provenance** | Records source, method, confidence, timestamp, alternatives for every field |
| **Project** | Applies runtime config (field selection, renaming, transforms) |
| **Validate** | Checks types, ranges, required fields on final output |

## Usage

```bash
# Individual sources
python main.py --csv data.csv --json ats.json --notes notes.txt --github username

# With output config
python main.py --csv data.csv --config output_configs/custom.json

# Save output to file
python main.py --demo --output result.json
```

## Runtime Output Config

```json
{
  "version": "1.0",
  "fields": [
    {"canonical_path": "full_name", "output_name": "candidateName", "normalize": "title_case", "required": true},
    {"canonical_path": "skills", "output_name": "technicalSkills"},
    {"canonical_path": "experience", "output_name": "workHistory"}
  ],
  "include_provenance": false,
  "include_confidence": true,
  "missing_value_strategy": "null"
}
```

| Option | Values | Description |
|--------|--------|-------------|
| `include_provenance` | `true/false` | Include/exclude provenance data |
| `include_confidence` | `true/false` | Include/exclude confidence scores |
| `missing_value_strategy` | `null`, `omit`, `error` | How to handle missing fields |
| `normalize` | `title_case`, `upper_case`, `lower_case` | Output-only transforms |

## Project Structure

```
├── main.py                     # CLI entry point
├── src/
│   ├── pipeline.py             # Pipeline orchestrator
│   ├── registry.py             # Adapter registry
│   ├── errors.py               # Error taxonomy + collector
│   ├── logger.py               # Structured logging
│   ├── schema/
│   │   ├── canonical.py        # Immutable canonical profile
│   │   └── source_record.py    # Intermediate representation
│   ├── adapters/
│   │   ├── base_adapter.py     # Abstract base class
│   │   ├── csv_adapter.py      # Recruiter CSV
│   │   ├── ats_json_adapter.py # ATS JSON
│   │   ├── pdf_adapter.py      # Resume PDF
│   │   ├── docx_adapter.py     # Resume DOCX
│   │   ├── txt_adapter.py      # Recruiter Notes
│   │   └── github_adapter.py   # GitHub Profile
│   ├── normalizers/
│   │   └── normalizers.py      # All field normalizers
│   ├── merger/
│   │   └── merge_engine.py     # Deterministic merge
│   ├── scoring/
│   │   └── confidence.py       # Confidence scoring
│   ├── provenance/
│   │   └── tracker.py          # Provenance tracking
│   ├── projection/
│   │   ├── engine.py           # Output projection
│   │   └── config_schema.py    # Config validation
│   └── validation/
│       └── validator.py        # Output validation
├── config/                     # Static configuration
├── output_configs/             # Runtime output configs
├── sample_data/                # Sample input files
├── tests/                      # Test suite (118 tests)
└── context.md                  # Full change log
```

## Adding a New Source

1. Create `src/adapters/my_adapter.py` extending `BaseAdapter`
2. Implement `extract()` — must never raise, return `SourceRecord` with errors
3. Register in `pipeline.py`: `registry.register(MyAdapter())`

Zero changes to existing code required.

## Tests

```bash
python -m pytest tests/ -v              # All tests
python -m pytest tests/unit/ -v         # Unit tests only
python -m pytest tests/integration/ -v  # Integration tests
python -m pytest tests/edge_cases/ -v   # Edge case tests
```

## Tech Stack

- **Python 3.11+**
- **pdfplumber** — PDF text extraction
- **python-docx** — DOCX text extraction
- **phonenumbers** — Phone number parsing/validation
- **PyYAML** — Config file loading
- **requests** — GitHub API
- **pytest** — Testing

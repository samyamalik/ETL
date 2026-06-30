# Multi-Source Candidate Data Transformer — Change Log

This file tracks every change made across all implementation phases.

---

## Phase 1: Project Scaffold
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:46:00+05:30

### Changes Made
- Created `context.md` (this file)
- Created project folder structure with all packages
- Created `requirements.txt` with dependencies
- Created `config/source_priority.yaml` — source trust rankings + weights
- Created `config/skill_aliases.yaml` — skill synonym map (40+ aliases)
- Created `config/company_aliases.yaml` — company synonym map (20+ aliases)
- Created `output_configs/default.json` — default output config (all fields)
- Created `__init__.py` for all packages (src, adapters, normalizers, merger, scoring, provenance, projection, validation, schema, tests)

### Files Created
```
requirements.txt
config/source_priority.yaml
config/skill_aliases.yaml
config/company_aliases.yaml
output_configs/default.json
src/__init__.py
src/adapters/__init__.py
src/normalizers/__init__.py
src/merger/__init__.py
src/scoring/__init__.py
src/provenance/__init__.py
src/projection/__init__.py
src/validation/__init__.py
src/schema/__init__.py
tests/__init__.py
tests/unit/__init__.py
tests/integration/__init__.py
tests/edge_cases/__init__.py
```

---

## Phase 2: Schema Definitions
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:48:00+05:30

### Changes Made
- Created `src/schema/canonical.py` — immutable canonical profile with all sub-models
  - `CanonicalProfile` — the ONE output schema (never changes)
  - `Email`, `Phone`, `Location`, `Skill`, `Experience`, `Education` — sub-models
  - `ProvenanceEntry` — tracks origin, method, confidence, alternatives
- Created `src/schema/source_record.py` — flat intermediate representation
  - `SourceRecord` — what every adapter produces (source_name + all optional fields)

### Design Decisions
- Used Python `dataclasses` for simplicity (no Pydantic dependency)
- All canonical fields have default values so partial profiles work
- ProvenanceEntry.alternatives stores losing merge values

---

## Phase 3: Error Handling + Logging
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:48:30+05:30

### Changes Made
- Created `src/errors.py` — error taxonomy + error collector
  - `TransformerBaseError` base class with `to_dict()` serialization
  - `SourceError`, `ParseError`, `NormalizationError` — graceful degradation
  - `ConfigError` — hard failure (bad config = reject)
  - `ValidationError` — output validation failures
  - `ErrorCollector` — accumulator pattern (collect errors, don't crash)
- Created `src/logger.py` — structured pipeline logger
  - JSON-like structured output with timestamp, stage, source, message
  - Correlation ID per pipeline run for traceability
  - Candidate ID tracking after merge

### Design Decisions
- Bad input data → degrade gracefully (warnings, nulls)
- Bad config → fail fast (raise ConfigError)
- Errors are collected during pipeline, reported at the end

---

## Phase 4: Source Adapters
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:50:00+05:30

### Changes Made
- Created `src/adapters/base_adapter.py` — abstract base class
  - `can_handle()`, `extract()`, `_empty_record_with_error()` methods
  - Contract: adapters NEVER raise, they return SourceRecord with errors
- Created `src/registry.py` — adapter registry for plug-and-play sources
  - `register()`, `get_adapter()`, `get_adapter_for_file()`, `list_adapters()`
- Created 6 concrete adapters:

| File | Source | Method |
|------|--------|--------|
| `csv_adapter.py` | Recruiter CSV | `csv.DictReader`, flexible column mapping |
| `ats_json_adapter.py` | ATS JSON | `json.load`, handles single/list/wrapper formats |
| `pdf_adapter.py` | Resume PDF | `pdfplumber` text extraction + regex parsing |
| `docx_adapter.py` | Resume DOCX | `python-docx` + regex parsing |
| `txt_adapter.py` | Recruiter Notes | Regex + heuristic extraction |
| `github_adapter.py` | GitHub Profile | REST API + repo language scraping |

### Edge Cases Handled
- Empty files → warning + empty record
- Corrupted files → error + empty record
- Invalid JSON → error + empty record
- Missing GitHub user → warning + empty record
- API rate limiting → warning + empty record
- Encoding issues → `errors="replace"` fallback

---

## Phase 5: Normalizers
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:51:00+05:30

### Changes Made
- Created `src/normalizers/normalizers.py` — all field normalizers as pure functions:

| Normalizer | Logic |
|-----------|-------|
| `normalize_name()` | Strip, remove salutations/suffixes, handle "Last, First", title-case |
| `normalize_email()` / `_list()` | Lowercase, RFC 5322 validation, dedup, sorted |
| `normalize_phone()` / `_list()` | E.164 via phonenumbers lib, fallback manual, dedup |
| `normalize_location()` | Split by comma, US state abbreviation expansion |
| `normalize_skill()` / `_list()` | Alias map lookup, lowercase, dedup, sorted |
| `normalize_date()` | Multiple format parsing → ISO 8601, "Present" → None |
| `normalize_company()` | Alias map lookup |
| `normalize_experience()` / `_list()` | Company + title + date normalization, sort by start_date desc |
| `normalize_degree()` | Abbreviation expansion (BS → Bachelor of Science, etc.) |
| `normalize_education()` / `_list()` | Institution title-case, degree expansion, sort by end_date desc |
| `normalize_links()` | URL validation, key lowercasing |

### Design Decisions
- Normalization failure → return None (never fabricate)
- Alias maps loaded once and cached (module-level singleton)
- All list normalizers sort output for determinism

---

## Phase 6: Merge Engine
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:52:00+05:30

### Changes Made
- Created `src/merger/merge_engine.py`
  - `merge_records()` — merges N SourceRecords into 1 CanonicalProfile
  - Loads source priority from `config/source_priority.yaml`
  - Scalar fields: highest-priority non-null source wins
  - List fields: union + dedup (emails by address, phones by number, skills by name)
  - Experience: dedup by (company, title, start_date) composite key
  - Education: dedup by (institution, degree) composite key
  - Links: merge dicts, highest-priority overwrites per key
  - `_generate_candidate_id()` — deterministic SHA-256 hash from (sorted emails + name)

### Determinism Guarantee
- Same inputs + same priority config → identical output every time
- All lists sorted, all dedup uses stable key ordering

---

## Phase 7: Confidence Scoring
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:52:30+05:30

### Changes Made
- Created `src/scoring/confidence.py`
  - Per-field formula: `confidence = source_trust × extraction_quality + agreement_bonus`
  - `source_trust` from config (ATS=0.95, CSV=0.85, PDF/DOCX=0.75, GitHub=0.70, Notes=0.50)
  - `extraction_quality`: structured=1.0, regex=0.7, heuristic=0.6
  - `agreement_bonus`: +0.1 if ≥2 sources agree (capped at 1.0)
  - Overall confidence: weighted mean across all fields
  - Field weights: name=1.0, email=0.9, experience=0.8, skills=0.7, etc.

---

## Phase 8: Provenance Tracking
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:53:00+05:30

### Changes Made
- Created `src/provenance/tracker.py`
  - `track_provenance()` — builds ProvenanceEntry for every field
  - Records: field_path, value, source, method, confidence, timestamp
  - Scalar fields record `alternatives` (losing values from other sources)
  - List items each get individual provenance entries
  - Experience/Education entries tracked as "{title} at {company}" etc.

---

## Phase 9: Projection Engine + Runtime Config
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:54:00+05:30

### Changes Made
- Created `src/projection/config_schema.py` — config validation
  - Validates: version, canonical paths, output names (no dupes), normalize rules, missing strategy
  - Invalid config → raises ConfigError (hard failure)
  - Supports: field selection, renaming, normalization, provenance/confidence toggles
- Created `src/projection/engine.py` — projection engine
  - `project()` — transforms CanonicalProfile into configured output shape
  - `_resolve_path()` — handles dotted paths, indexed paths, wildcard `[*]` paths
  - `_apply_normalization()` — output-only transforms (title_case, upper_case, lower_case)
  - `_strip_nested_field()` — recursively removes source/confidence from nested objects
  - READ-ONLY: never mutates the canonical profile
- Created `output_configs/custom.json` — example config with renamed fields + no provenance

---

## Phase 10: Validation Layer
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:54:30+05:30

### Changes Made
- Created `src/validation/validator.py`
  - `validate_output()` — validates the final projected output
  - Type checks: ensures lists are lists, strings are strings, etc.
  - Confidence range: all scores must be in [0.0, 1.0]
  - Required field checks: honors config's `required` flag + `missing_value_strategy`

---

## Phase 11: Pipeline Orchestrator
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:55:00+05:30

### Changes Made
- Created `src/pipeline.py`
  - `process_candidate()` — full 7-stage pipeline for one candidate
    - Ingest → Merge → Score → Provenance → Project → Validate
  - `process_batch()` — parallel processing via ThreadPoolExecutor
    - Results sorted by original index for determinism
  - `create_default_registry()` — registers all 6 adapters
  - Error handling: adapters can't crash the pipeline, config errors reject fast

---

## Phase 12: Sample Data + Main Entry Point
**Status:** ✅ Complete
**Timestamp:** 2026-06-29T23:56:00+05:30

### Changes Made
- Created `sample_data/candidates.csv` — 2 CSV rows with conflicting data
- Created `sample_data/ats_data.json` — full ATS candidate with experience + education
- Created `sample_data/recruiter_notes.txt` — freeform notes with embedded data
- Created `main.py` — CLI entry point
  - `--demo` flag runs with sample data
  - `--config` flag for custom output configs
  - `--csv`, `--json`, `--notes`, `--github` for individual sources
  - `--output` to save results to file
- Created `venv/` — Python virtual environment
- Installed all dependencies

### Verification
- ✅ `python main.py --demo` → Valid=True, 0 errors, full profile with provenance
- ✅ `python main.py --demo --config custom.json` → Renamed fields, no provenance, confidence retained
- ✅ Merge correctly resolves: "Google LLC" → "Google", "Meta Platforms" → "Meta", "Amazon Inc" → "Amazon"
- ✅ Skill aliases work: "Python" stays, "kubernetes" stays from CSV
- ✅ Degree normalization: "MS" → "Master of Science", "BTech" → "Bachelor of Technology"
- ✅ Deterministic candidate_id: `16aeb433bd473c2c`
- ✅ Overall confidence: 0.9125

---

## Phase 13: Tests
**Status:** ✅ Complete
**Timestamp:** 2026-06-30T00:05:00+05:30

### Changes Made
- Created `tests/unit/test_normalizers.py` — 42 tests for all normalizer functions
  - Name: basic, whitespace, Last/First, salutations, suffixes, None, empty
  - Email: basic, whitespace, invalid, None, dedup, sorted
  - Phone: too short, None, empty, dedup
  - Location: city+state abbrev, city+state+country, city only, None, empty
  - Skill: alias resolution, no alias, None, dedup, sorted
  - Date: ISO, year-month, year, Present, month-year, None, empty
  - Company: alias, no alias, None
  - Degree: abbreviations, passthrough, None
  - Experience: basic, None, empty dict, list sorting
  - Links: valid, invalid URL, None, empty
- Created `tests/unit/test_adapters.py` — 16 tests for CSV, ATS JSON, TXT adapters
  - Valid input, empty files, missing files, header-only CSV, multi-row, semicolon emails
  - Invalid JSON, wrapper format, nested location, experience parsing
  - Valid notes, empty notes, missing file, can_handle
- Created `tests/unit/test_merge_score_provenance.py` — 16 tests
  - Merge: single source, priority, email union, skill dedup, empty, determinism, null fallthrough, exp dedup
  - Confidence: basic scoring, higher trust, empty profile, range check
  - Provenance: entries created, has source, alternatives, timestamps
- Created `tests/unit/test_projection_validation.py` — 12 tests
  - Projection: default config, field selection, renaming, provenance stripped, missing null, missing omit
  - Config validation: invalid path, duplicate names, invalid strategy, invalid normalize
  - Validator: valid output, invalid type
- Created `tests/integration/test_pipeline.py` — 5 tests
  - Full pipeline with sample data, determinism, custom config, single source, missing source graceful
- Created `tests/edge_cases/test_edge_cases.py` — 14 tests
  - Empty files (CSV, JSON, TXT), invalid JSON, missing file
  - Missing GitHub, same email dedup, different names, phone formats, invalid phone
  - Skill aliases, duplicate skills, invalid config, unknown canonical path
  - Missing education, missing dates, no sources
- Fixed TXT adapter name regex (was matching across newlines)

### Test Results
```
118 passed, 0 failed in 0.18s
```

---

## Phase 14: README + Final Polish
**Status:** ✅ Complete
**Timestamp:** 2026-06-30T00:06:00+05:30

### Changes Made
- Created `README.md` — comprehensive docs with architecture, usage, config reference, project structure
- Final demo verification with both default and custom configs

### Final Verification
- ✅ `python main.py --demo` — Valid=True, 0 errors, full profile
- ✅ `python main.py --demo --config custom.json` — Renamed fields, no provenance
- ✅ `python -m pytest tests/ -v` — 118/118 passed
- ✅ Company aliases: Google LLC → Google, Meta Platforms → Meta, Amazon Inc → Amazon
- ✅ Skill aliases: js → javascript, reactjs → react, nodejs → node.js
- ✅ Degree normalization: MS → Master of Science, BTech → Bachelor of Technology
- ✅ Deterministic candidate_id across runs: 16aeb433bd473c2c
- ✅ Overall confidence: 0.9125

---

## Summary

| Metric | Value |
|--------|-------|
| Total files created | 35+ |
| Source adapters | 6 (CSV, JSON, PDF, DOCX, TXT, GitHub) |
| Normalizer functions | 18 |
| Test cases | 118 |
| Test pass rate | 100% |
| Config options | field selection, renaming, normalization, provenance/confidence toggle, missing strategy |
| Pipeline stages | 7 (Ingest → Normalize → Merge → Score → Provenance → Project → Validate) |

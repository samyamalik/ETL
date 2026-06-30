# Multi-Source Candidate Data Transformer: Comprehensive Code Explanation

This document provides a detailed breakdown of the `src` folder, explaining every subfolder and the core logic behind every file and its functions.

---

## 1. `src/schema/`
This folder defines the immutable "Single Source of Truth" data structures used throughout the entire pipeline.

### `canonical.py`
This file defines the internal canonical data model using Python `dataclasses`.
- **`@dataclass(frozen=True)`**: Every class is frozen (immutable). This guarantees determinism because once data is parsed and merged, it cannot be accidentally modified downstream.
- **`Email`, `Phone`, `Skill`, `Experience`, `Education`**: These are complex nested objects. Instead of a phone number being just a string, it is an object containing `number`, `phone_type`, `confidence`, and `source`.
- **`CanonicalProfile`**: The master object. It contains fields like `candidate_id` (a SHA-256 hash ensuring unique identification), `full_name`, and lists of the nested objects above. It also holds `overall_confidence` and `provenance` (the audit trail).

---

## 2. `src/adapters/`
The Ingestion Layer. It extracts raw data from various file formats and APIs and standardizes it into an `ExtractedRecord`.

### `base_adapter.py`
- **`class BaseAdapter(ABC)`**: Defines an Abstract Base Class. It enforces a strict contract.
- **`@abstractmethod def extract(self, source)`**: Every adapter subclass *must* implement this method. It takes a file path or URL and returns a list of `ExtractedRecord` objects.

### `csv_adapter.py`
- **`csv.DictReader`**: Reads the CSV file row by row into dictionaries.
- **Mapping Logic**: Maps common recruiter CSV column headers (like `Applicant Name`, `Current Title`, `Top Skills`) to the canonical fields (`full_name`, `headline`, `skills`). 
- **List Splitting**: Splits comma-separated skills and semicolon-separated emails into Python lists.

### `ats_json_adapter.py`
- **`json.load()`**: Parses the structured JSON file.
- **Validation**: Checks if the JSON is an array of candidates or a single candidate object.
- **Mapping Logic**: Extracts nested data directly, mapping fields like `skills` and `education` iteratively.

### `txt_adapter.py`
- **Regex Parsing**: Because TXT files are unstructured recruiter notes, this adapter relies entirely on Regular Expressions (`re` module).
- **`re.search(r'[\w\.-]+@[\w\.-]+')`**: Extracts any text that looks like an email address.
- **`re.findall(r'(\+?\d[\d\-\(\)\s]{8,}\d)')`**: Extracts anything that looks like a phone number.

### `pdf_adapter.py`
- **`pdfplumber.open(source)`**: Uses the `pdfplumber` library to open the binary PDF file.
- **`page.extract_text()`**: Loops through every page and extracts the raw text.
- **Delegation**: Passes the extracted raw text into the same RegEx logic used by `txt_adapter.py` to find emails, phones, and skills.

### `docx_adapter.py`
- **`docx.Document(source)`**: Uses `python-docx` to read Microsoft Word documents.
- **`paragraph.text`**: Loops through every paragraph to build a massive raw text string.
- **Delegation**: Like the PDF adapter, it uses RegEx to find entities within the raw text.

### `github_adapter.py`
- **`requests.get()`**: Makes HTTP REST API calls to `api.github.com/users/{username}`.
- **Live Data**: Pulls live data such as `name`, `location`, `company`, and `blog` directly from the developer's GitHub profile.

---

## 3. `src/registry.py`
Dynamically manages and maps the adapters.
- **`ADAPTERS` dictionary**: Maps string identifiers (e.g., `"resume_pdf"`) to the actual Python Class (e.g., `PdfAdapter`).
- **`get_adapter(source_type)`**: A factory function. If the pipeline asks for `"resume_pdf"`, it returns an instance of `PdfAdapter`. This prevents tight coupling and makes adding new sources easy.

---

## 4. `src/normalizers/`
The Cleanup Crew. Cleans, standardizes, and normalizes data *before* it gets merged.

### `normalizers.py`
- **`normalize_name(name)`**: 
  - `re.sub(r'[^a-zA-Z\s-]', '', name)`: Removes numbers, emojis, and special characters.
  - Strips out salutations like "Mr.", "Dr.", "PhD".
  - Capitalizes the first letter of each name component (`.title()`).
- **`normalize_email(email)`**: 
  - Converts to strict lowercase (`.lower()`) to prevent deduplication errors.
- **`normalize_phone(phone)`**: 
  - Removes extensions and formats to E.164 standard (e.g., `+15551234567`).
- **`normalize_skill(skill)`**: 
  - Reads `config/company_aliases.yaml`.
  - Converts raw skill strings into canonical lowercase identifiers (e.g., converts "ReactJS" and "React.js" to `"react"`).

---

## 5. `src/merger/`
The Conflict Resolver. Resolves discrepancies between multiple data sources deterministically.

### `merge_engine.py`
- **`load_source_priority()`**: Loads `config/source_priority.yaml` to determine which source is trusted more (e.g., ATS > GitHub > Resume > Recruiter CSV).
- **`merge_records(records)`**: The core loop. It looks at all incoming records for a candidate.
- **Scalar Field Resolution (`_resolve_scalar`)**: For fields like `full_name`, if the ATS and the CSV disagree, it checks the priority map. The ATS value wins because it has a higher priority rank.
- **List Field Resolution (`_resolve_list`)**: For fields like `skills` or `emails`, it performs a Union. It combines all skills from all sources, removes duplicates using the canonical identifier, and sorts them alphabetically so the output is deterministic.
- **`_generate_candidate_id()`**: Creates a stable SHA-256 hash using the candidate's canonical name and primary email.

---

## 6. `src/scoring/`
The Trust Calculator.

### `confidence.py`
- **`score_profile(records)`**: Calculates a 0.0 to 1.0 confidence score for every data point.
- **Formula**: `score = (base_trust * extraction_quality) + agreement_bonus`.
- **`base_trust`**: Pulled from the priority map (e.g., ATS=0.9, Notes=0.4).
- **`extraction_quality`**: Hardcoded based on data type (e.g., emails have strict formats so they get 1.0 quality; scraped names get 0.7 quality).
- **`agreement_bonus`**: If both the Resume and the CSV report the same email address, a +0.10 mathematical bonus is applied for corroboration.

---

## 7. `src/provenance/`
The Audit Trail.

### `tracker.py`
- **`ProvenanceTracker` class**: An append-only log.
- **`log_decision()`**: Every time the `merge_engine` makes a decision, it calls this method.
- **Logging**: It records the `field_path`, the `chosen_value`, the `source` that provided it, and a list of `alternatives_rejected` (values from other sources that lost the priority battle).

---

## 8. `src/projection/`
The Shape Shifter. Molds the canonical profile into the exact JSON format requested by the user.

### `config_schema.py`
- **`load_output_config()`**: Loads the user's custom JSON configuration file.
- **`_validate_config()`**: Checks if the user provided valid keys (e.g., verifying `path`, `from`, `type`, and `on_missing`). Ensures they didn't ask for a canonical field that doesn't exist.

### `engine.py`
- **`project(profile, config)`**: Converts the immutable `CanonicalProfile` into a flat Python dictionary.
- **`_resolve_path()`**: Uses bracket/dot notation string parsing to extract nested data (e.g., resolving `"emails[0].address"` down to just the string `"john@example.com"`).
- **`_coerce_to_string()`**: A type-aware engine. If the config requests `"type": "string"` but the path evaluates to an object (like `{address: "...", source: "..."}`), it automatically unpacks the primary scalar value.
- **Missing Strategy**: Handles the `on_missing` config rule by either outputting `null`, `omit`ting the key entirely, or throwing an `error`.

---

## 9. `src/validation/`
The Bouncer. Ensures the final output is safe and compliant.

### `validator.py`
- **`validate_output(output, config)`**: Runs safety checks on the dictionary produced by the projection engine before it is printed/saved.
- **`_validate_types()`**: Checks the actual Python `type()` of the projected values against the `"type"` requested in the configuration schema (e.g., ensuring a `"string[]"` is actually a `list` of `str`s).
- **`_validate_required_fields()`**: If the config marked `"required": true`, it ensures the value is present and not `null`. Raises a `ValidationError` if it fails.

---

## 10. `src/` Root Orchestration
The central nervous system.

### `pipeline.py`
- **`process_candidate(sources, output_config)`**: The master pipeline function. It executes the entire ETL flow sequentially:
  1. `adapters.extract()`
  2. `normalizers.normalize()`
  3. `merge_engine.merge()`
  4. `confidence.score()`
  5. `tracker.log()`
  6. `projection.project()`
  7. `validator.validate()`

### `errors.py`
- **Custom Exceptions**: Defines `AdapterError`, `NormalizationError`, `MergeError`, etc.
- **`ErrorCollector` class**: Implements the "Accumulator Pattern". Instead of throwing an exception and crashing the whole script when a minor error occurs (like a bad phone number format), it traps the error, logs it, and allows the pipeline to continue running.

### `logger.py`
- **`CustomJsonFormatter`**: Overrides the standard Python logging formatter to output logs as structured JSON.
- Provides traceability via `run_id` and `candidate_id` tracking across asynchronous threaded operations.

"""
Pipeline Orchestrator — runs the full ETL pipeline for one or many candidates.

Pipeline stages:
1. Ingest   → adapters extract SourceRecords
2. Merge    → merge all SourceRecords into one CanonicalProfile
3. Score    → assign confidence scores
4. Provenance → track origin of every value
5. Project  → apply runtime output config
6. Validate → check final output
"""

import uuid
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.registry import AdapterRegistry
from src.adapters.csv_adapter import CsvAdapter
from src.adapters.ats_json_adapter import AtsJsonAdapter
from src.adapters.pdf_adapter import PdfAdapter
from src.adapters.docx_adapter import DocxAdapter
from src.adapters.txt_adapter import TxtAdapter
from src.adapters.github_adapter import GithubAdapter

from src.merger.merge_engine import merge_records
from src.scoring.confidence import score_profile
from src.provenance.tracker import track_provenance
from src.projection.engine import project
from src.projection.config_schema import load_output_config
from src.validation.validator import validate_output
from src.errors import ErrorCollector, ConfigError
from src.logger import logger

import os
from dotenv import load_dotenv

def create_default_registry():
    """Create and return a registry with all default adapters."""
    
    # Automatically load API tokens from .env file into environment variables
    load_dotenv()
    
    registry = AdapterRegistry()
    registry.register(CsvAdapter())
    registry.register(AtsJsonAdapter())
    registry.register(PdfAdapter())
    registry.register(DocxAdapter())
    registry.register(TxtAdapter())
    
    # Check for GitHub token in environment to increase rate limit from 60 to 5000/hr
    gh_token = os.environ.get("GITHUB_TOKEN")
    registry.register(GithubAdapter(api_token=gh_token))
    
    return registry


def process_candidate(sources, output_config=None, registry=None):
    """
    Process a single candidate through the full pipeline.

    Args:
        sources: dict mapping source_type to input_data
                 e.g. {"recruiter_csv": "path/to/file.csv",
                        "ats_json": "path/to/data.json",
                        "github_profile": "username"}
        output_config: dict or path to output config JSON. None = default.
        registry: AdapterRegistry. None = use default.

    Returns:
        dict with keys:
            "output"  — the projected profile (dict)
            "is_valid" — bool
            "errors"  — list of error dicts
            "candidate_id" — str
    """
    correlation_id = str(uuid.uuid4())[:8]
    logger.set_correlation_id(correlation_id)
    errors = ErrorCollector()

    # ── Step 0: Setup registry ──
    if registry is None:
        registry = create_default_registry()

    # ── Step 1: Load output config ──
    try:
        if isinstance(output_config, dict):
            config = load_output_config(config_dict=output_config)
        elif isinstance(output_config, str):
            config = load_output_config(config_path=output_config)
        else:
            config = load_output_config()
    except ConfigError as e:
        logger.error("config", "", str(e))
        return {
            "output": None,
            "is_valid": False,
            "errors": [e.to_dict()],
            "candidate_id": "",
        }

    # ── Step 2: Ingest — extract from all sources ──
    logger.info("pipeline", "", f"Starting pipeline (run={correlation_id})")
    all_records = []

    for source_type, input_data in sources.items():
        adapter = registry.get_adapter(source_type)
        if not adapter:
            errors.add({
                "error_type": "SourceError",
                "message": f"No adapter for source type: {source_type}",
                "source": source_type,
                "field_path": "",
                "severity": "warning",
            })
            continue

        logger.info("ingest", source_type, f"Extracting from {source_type}")
        try:
            records = adapter.extract(input_data)
            for record in records:
                if record.errors:
                    for err in record.errors:
                        errors.add({
                            "error_type": "ParseError",
                            "message": str(err),
                            "source": source_type,
                            "field_path": "",
                            "severity": "warning",
                        })
                all_records.append(record)
        except Exception as e:
            logger.error("ingest", source_type, f"Adapter crashed: {str(e)}")
            errors.add({
                "error_type": "SourceError",
                "message": f"Adapter crashed: {str(e)}",
                "source": source_type,
                "field_path": "",
                "severity": "error",
            })

    if not all_records:
        logger.warning("pipeline", "", "No source records extracted")
        return {
            "output": {},
            "is_valid": False,
            "errors": errors.get_errors() + [{
                "error_type": "SourceError",
                "message": "No data extracted from any source",
                "source": "",
                "field_path": "",
                "severity": "error",
            }],
            "candidate_id": "",
        }

    # ── Step 3: Merge ──
    logger.info("pipeline", "", "Merging records")
    profile = merge_records(all_records)

    # ── Step 4: Provenance ──
    logger.info("pipeline", "", "Tracking provenance")
    profile = track_provenance(profile, all_records)

    # ── Step 5: Score ──
    logger.info("pipeline", "", "Scoring confidence")
    profile = score_profile(profile, all_records)

    logger.set_candidate_id(profile.candidate_id)

    # ── Step 6: Project ──
    logger.info("pipeline", "", "Projecting output")
    try:
        output = project(profile, config)
    except Exception as e:
        logger.error("projection", "", f"Projection failed: {str(e)}")
        errors.add({
            "error_type": "ProjectionError",
            "message": str(e),
            "source": "",
            "field_path": "",
            "severity": "error",
        })
        output = {}

    # ── Step 7: Validate ──
    logger.info("pipeline", "", "Validating output")
    is_valid, validation_errors = validate_output(output, config)
    all_errors = errors.get_errors() + validation_errors

    logger.info("pipeline", "", f"Pipeline complete. Valid={is_valid}, Errors={len(all_errors)}")
    return {
        "output": output,
        "is_valid": is_valid,
        "errors": all_errors,
        "candidate_id": profile.candidate_id,
    }


def process_batch(candidates, output_config=None, max_workers=4):
    """
    Process multiple candidates in parallel.

    Args:
        candidates: list of dicts, each with a "sources" key
                    e.g. [{"sources": {"recruiter_csv": "path.csv", ...}}, ...]
        output_config: shared output config for all candidates
        max_workers: number of parallel workers

    Returns:
        list of result dicts (same format as process_candidate output)
    """
    registry = create_default_registry()
    results = []

    logger.info("batch", "", f"Processing batch of {len(candidates)} candidates with {max_workers} workers")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, candidate in enumerate(candidates):
            sources = candidate.get("sources", {})
            future = executor.submit(
                process_candidate, sources, output_config, registry
            )
            futures[future] = i

        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                results.append({"index": idx, **result})
            except Exception as e:
                logger.error("batch", "", f"Candidate {idx} failed: {str(e)}")
                results.append({
                    "index": idx,
                    "output": None,
                    "is_valid": False,
                    "errors": [{"error_type": "PipelineError", "message": str(e)}],
                    "candidate_id": "",
                })

    # Sort by original index for determinism
    results.sort(key=lambda r: r["index"])
    logger.info("batch", "", f"Batch complete. {len(results)} candidates processed.")
    return results

"""
Main entry point — demonstrates the full pipeline with sample data.

Usage:
    python main.py                          # Default config, all fields
    python main.py --config custom.json     # Custom output config
    python main.py --help                   # Show usage
"""

import sys
import os
import json
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import process_candidate, process_batch
from src.logger import logger


def main():
    parser = argparse.ArgumentParser(
        description="Multi-Source Candidate Data Transformer"
    )
    parser.add_argument(
        "--config",
        help="Path to output config JSON file",
        default=None,
    )
    parser.add_argument(
        "--csv",
        help="Path to recruiter CSV file",
        default=None,
    )
    parser.add_argument(
        "--json",
        help="Path to ATS JSON file",
        default=None,
    )
    parser.add_argument(
        "--notes",
        help="Path to recruiter notes TXT file",
        default=None,
    )
    parser.add_argument(
        "--github",
        help="GitHub username or profile URL",
        default=None,
    )
    parser.add_argument(
        "--pdf",
        help="Path to resume PDF file",
        default=None,
    )
    parser.add_argument(
        "--docx",
        help="Path to resume DOCX file",
        default=None,
    )
    parser.add_argument(
        "--demo",
        help="Run with sample data",
        action="store_true",
    )
    parser.add_argument(
        "--output",
        help="Path to write output JSON file",
        default=None,
    )

    args = parser.parse_args()

    # ── Build sources dict ──
    sources = {}

    if args.demo:
        # Use sample data
        sample_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_data")
        sources["recruiter_csv"] = os.path.join(sample_dir, "candidates.csv")
        sources["ats_json"] = os.path.join(sample_dir, "ats_data.json")
        sources["recruiter_notes"] = os.path.join(sample_dir, "recruiter_notes.txt")
        print("\n=== Running with sample data ===\n")
    else:
        if args.csv:
            sources["recruiter_csv"] = args.csv
        if args.json:
            sources["ats_json"] = args.json
        if args.notes:
            sources["recruiter_notes"] = args.notes
        if args.github:
            sources["github_profile"] = args.github
        if args.pdf:
            sources["resume_pdf"] = args.pdf
        if args.docx:
            sources["resume_docx"] = args.docx

    if not sources:
        print("No sources provided. Use --demo for sample data or --help for options.")
        sys.exit(1)

    # ── Determine config ──
    config_path = args.config
    if config_path and not os.path.isabs(config_path):
        # Check output_configs directory
        config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output_configs")
        full_path = os.path.join(config_dir, config_path)
        if os.path.exists(full_path):
            config_path = full_path

    # ── Run pipeline ──
    result = process_candidate(
        sources=sources,
        output_config=config_path,
    )

    # ── Display results ──
    print("\n" + "=" * 60)
    print("  PIPELINE RESULT")
    print("=" * 60)
    print(f"  Candidate ID : {result['candidate_id']}")
    print(f"  Valid         : {result['is_valid']}")
    print(f"  Errors        : {len(result['errors'])}")
    print("=" * 60)

    if result["output"]:
        output_json = json.dumps(result["output"], indent=2, default=str)
        print("\n📋 Output Profile:\n")
        print(output_json)
    else:
        print("\n❌ No output produced.")

    if result["errors"]:
        print(f"\n⚠️  Errors ({len(result['errors'])}):")
        for err in result["errors"]:
            severity = err.get("severity", "error")
            message = err.get("message", "Unknown error")
            source = err.get("source", "")
            icon = "🔴" if severity == "error" else "🟡"
            print(f"  {icon} [{source}] {message}")

    # ── Write to file if requested ──
    if args.output and result["output"]:
        with open(args.output, "w") as f:
            json.dump(result, f, indent=2, default=str)
        print(f"\n💾 Output saved to: {args.output}")

    print()


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .orchestrator import CoordinatorAgent, validate_project


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Olist multi-agent dispute resolver")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Check 9 CSVs and 50 input cases")
    validate_parser.add_argument("--project-root", default=".")

    run_parser = subparsers.add_parser("run", help="Resolve all 50 official cases")
    run_parser.add_argument("--project-root", default=".")
    run_parser.add_argument(
        "--zip-output",
        default="output_submission.zip",
        help="Path of the submission ZIP; use an empty string to skip ZIP creation",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).resolve()

    if args.command == "validate":
        errors = validate_project(project_root)
        if errors:
            print("PROJECT INVALID")
            for error in errors:
                print(f"- {error}")
            return 2
        print("PROJECT VALID: 9 CSV files and 50 official input cases are present.")
        return 0

    zip_output = Path(args.zip_output) if args.zip_output else None
    if zip_output is not None and not zip_output.is_absolute():
        zip_output = project_root / zip_output
    try:
        metadata = CoordinatorAgent(project_root).run(zip_output=zip_output)
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(str(exc))
        return 2
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    if zip_output is not None:
        print(f"Submission ZIP: {zip_output}")
    return 0

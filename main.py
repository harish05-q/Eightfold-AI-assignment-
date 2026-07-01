"""Command Line Interface for Candidate Transformer."""

import argparse
import json
import logging
import sys
from pathlib import Path

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.models.input import InputManifest
from candidate_transformer.factory import create_standard_orchestrator

def setup_logging(level: int) -> None:
    """Setup standard logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Deterministic pipeline for unifying unstructured candidate data."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to the input manifest JSON file.",
    )
    parser.add_argument(
        "-c", "--config",
        type=Path,
        default=None,
        help="Path to the output config JSON file (optional).",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Path to save the output JSON (default: stdout).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable DEBUG logging.",
    )
    return parser.parse_args()

def main() -> None:
    """CLI entry point."""
    args = parse_args()
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    logger = logging.getLogger("cli")
    
    # 1. Load manifest
    try:
        manifest_text = args.manifest.read_text(encoding="utf-8")
        manifest = InputManifest.model_validate_json(manifest_text)
    except Exception as e:
        logger.error("Failed to load manifest '%s': %s", args.manifest, e)
        sys.exit(1)
        
    # 2. Load config
    config = OutputConfig()
    if args.config:
        try:
            config_text = args.config.read_text(encoding="utf-8")
            config = OutputConfig.model_validate_json(config_text)
        except Exception as e:
            logger.error("Failed to load config '%s': %s", args.config, e)
            sys.exit(1)
            
    # 3. Run pipeline
    logger.info("Initializing pipeline orchestrator...")
    orchestrator = create_standard_orchestrator()
    
    logger.info("Running pipeline...")
    result = orchestrator.run(manifest, config)
    
    # 4. Handle output
    output_data = {
        "run_id": result.run_id,
        "timing": result.timing,
        "warnings": result.warnings,
        "errors": [
            {
                "stage": err.stage,
                "source": err.source,
                "error_type": err.error_type,
                "message": err.message,
                "timestamp": err.timestamp.isoformat()
            }
            for err in result.errors
        ],
        "candidates": result.candidates
    }
    
    out_json = json.dumps(output_data, indent=2)
    
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out_json, encoding="utf-8")
        logger.info("Successfully wrote output to '%s'", args.output)
    else:
        print(out_json)
        
    # Optional: return non-zero exit code if extraction or validation had fatal errors?
    # We will exit 0 since pipeline handled them gracefully and reported them.

if __name__ == "__main__":
    main()

import argparse
import importlib
import logging
import os

from asf_mission_data.logging_utils import configure_logging

# Currently only debug locally.
is_local = not os.environ.get("DATA_ROOT", "").startswith("s3://")
configure_logging(log_level="DEBUG" if is_local else "INFO")

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an ASF Mission Data pipeline.")

    parser.add_argument(
        "pipeline",
        type=str,
        help="The name of the pipeline to run (must match a key in pipelines.yaml eg 'example')",
    )

    parser.add_argument(
        "--stage",
        choices=["all", "bronze", "silver", "gold"],
        default="all",
        help="Which stage(s) to run (default: all).",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args, extra_args = parser.parse_known_args()

    logger.info(f"Pipeline: {args.pipeline} | Stage: {args.stage}")

    module_path = f"asf_mission_data.pipeline.{args.pipeline}.pipeline"
    logger.debug(f"Importing pipeline module: {module_path}")

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.error(f"Error: Pipeline module '{module_path}' not found.")
        return 1

    module.run(stage=args.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

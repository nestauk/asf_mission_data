import argparse
import importlib
import os

from asf_mission_data.logging_utils import setup_logging

# Currently only debug locally.
# NB: If we need DEBUG on AWS to troubleshoot we
# can add a LOG_LEVEL override to the container command
is_local = not os.environ.get("DATA_ROOT", "").startswith("s3://")
log_level = "DEBUG" if is_local else "INFO"
logger = setup_logging(__name__, log_level=log_level)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Write dataset registry for an ASF Mission Data pipeline.")

    parser.add_argument(
        "pipeline",
        type=str,
        help="The name of the pipeline to write registry for (must match a key in pipelines.yaml eg 'example')",
    )

    return parser


def main() -> int:
    parser = build_parser()
    args, extra_args = parser.parse_known_args()

    logger.info(f"Pipeline: {args.pipeline}")

    module_path = f"asf_mission_data.pipeline.{args.pipeline}.pipeline"
    logger.debug(f"Importing pipeline module: {module_path}")

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.error(f"Error: Pipeline module '{module_path}' not found.")
        return 1

    module.render_registry(pipeline=args.pipeline)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

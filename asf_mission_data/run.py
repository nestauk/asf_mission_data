import argparse
import importlib

from asf_mission_data.logging_utils import setup_logging

logger = setup_logging(__name__, log_level="DEBUG")


# def build_parser() -> argparse.ArgumentParser:
#     parser = argparse.ArgumentParser(
#         description="Run an ASF Mission Data pipeline."
#     )

#     parser.add_argument(
#         "--pipeline",
#         type=str,
#         required=True,
#         help="The name of the pipeline to run (must match a key in "
#         "pipelines.yaml e.g., 'energy_price_cap_levels_annex_9').",
#     )

#     parser.add_argument(
#         "--stage",
#         choices=["all", "bronze", "silver", "gold"],
#         default="all",
#         help="Which stage(s) to run (default: all).",
#     )
#     return parser


# def run_pipeline(pipeline_name: str, stage: str) -> None:
#     module_path = f"asf_mission_data.pipeline.{pipeline_name}.pipeline"
#     logger.info(f"Importing pipeline module: {module_path}")

#     module = importlib.import_module(module_path)

#     stages_to_run = ["bronze"] if stage == "all" else [stage]


# def main():
#     parser = build_parser()
#     args = parser.parse_args()

#     logger.info("Pipeline: {args.pipeline} | Stage: {args.stage}")
#     run_pipeline(args.pipeline, args.stage)
#     logger.info("Done")


# if __name__ == "__main__":
#     main()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an ASF Mission Data pipeline.")

    parser.add_argument(
        "pipeline",
        type=str,
        help="The name of the pipeline to run (must match a key in pipelines.yaml e.g., 'energy_price_cap_levels_annex_9').",
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

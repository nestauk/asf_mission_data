# Running Pipelines

This repo supports a few different ways of running a pipeline, but most people only need two:

- run locally while developing
- use the GitHub Actions UI for ad hoc runs in AWS

Everything else should be treated as advanced or debugging-only.

## What To Use When

| I want to... | Use this | Notes |
|---|---|---|
| develop or debug pipeline code | local run | fastest feedback, no AWS dependency |
| test my branch in AWS | build an image, then use `Run pipeline` | standard cloud test path |
| run against the default dev image | `Run pipeline` with `image_tag=dev-latest` | easiest ad hoc cloud run |
| launch from a terminal with more control | `scripts/trigger_pipeline.py` | advanced/debug path |

## Standard Workflow

For most cloud runs, the process is:

1. build a Docker image for the code you want to test
2. copy the image tag from the build workflow summary
3. run the `Run pipeline` workflow with that tag

That is the main team workflow. If you are unsure which path to use, use this one.

## Local Development

Use local mode when developing or debugging pipeline logic.

```bash
export DATA_MODE=LOCAL
export DATA_ROOT=/tmp/pipeline-dev

uv run python -m asf_mission_data.run example --stage all
```

This avoids Docker, ECS, and ECR entirely.

## Build An Image For A Branch

Use the `Build and push Docker Image to ECR` workflow when you want to test branch code in AWS.

### How tags are created

The workflow tags images from the branch name using:

```text
{branch-name-with-/-replaced-by--}-latest
```

Examples:

- `dev` -> `dev-latest`
- `feat/image-check` -> `feat-image-check-latest`
- `alex/test-run` -> `alex-test-run-latest`

The exact image URI is written to the workflow summary at the end of the build.

### Which branches use which tags

- pushes to `dev` automatically build `dev-latest`
- manual workflow runs build a tag for the branch selected in GitHub

Do not guess the tag if you can avoid it. Copy it from the build workflow summary.

## Run A Pipeline In AWS

Use the `Run pipeline` workflow in GitHub Actions for standard ad hoc runs.

Inputs:

- `pipeline`: must match a key in `pipelines.yaml`
- `stage`: one of `all`, `bronze`, `silver`, `gold`
- `image_tag`: the ECR tag to use

Examples:

- use the default dev image:

```text
pipeline=example
stage=all
image_tag=dev-latest
```

- test a branch image:

```text
pipeline=example
stage=all
image_tag=feat-image-check-latest
```

### What the workflow shows you

The workflow now surfaces the important launch details in the Actions UI:

- the resolved task definition
- the container image actually used
- a highlighted error if the requested image tag does not exist in ECR

That means a missing tag fails before registering a new task definition or starting a task.

## Advanced: Trigger From The Terminal

You can also launch the same flow directly:

```bash
uv run python scripts/trigger_pipeline.py example --stage all --image-tag dev-latest
```

Or with a branch image:

```bash
uv run python scripts/trigger_pipeline.py example --stage all --image-tag feat-image-check-latest
```

This script:

- resolves the task definition
- validates that the non-default image tag exists in ECR
- prints the task definition and image URI
- launches the ECS task

Use this when you need CLI control. For most users, the GitHub UI is simpler.

## What Is Supported vs Advanced

Supported for most users:

- local runs via `python -m asf_mission_data.run`
- cloud runs via `Build and push Docker Image to ECR`
- cloud runs via `Run pipeline`

Advanced/debug only:

- direct use of `scripts/trigger_pipeline.py`
- trying to run GitHub Actions workflows locally

This repo does not treat "run the GitHub workflow locally" as a standard path. For normal use, prefer the GitHub UI or the Python trigger script.

## Troubleshooting

### The image tag does not exist

Symptom:

```text
Error resolving task definition: Image tag '...' was not found in ECR repository 'asf-mission-data'
```

What to do:

1. run `Build and push Docker Image to ECR`
2. copy the tag from the workflow summary
3. rerun `Run pipeline` with that exact tag

### I just want the latest shared dev image

Use:

```text
image_tag=dev-latest
```

### I do not know the pipeline name

Check `pipelines.yaml`. The `pipeline` input must match one of its keys.


MOVED OUT FROM README.md

### Running pipelines locally

```bash
# Set local mode (otherwise the default is the dev S3 bucket)
export DATA_MODE=LOCAL
export DATA_ROOT=/tmp/pipeline-dev

# Run the example pipeline
uv run python -m asf_mission_data.run example --stage all

# Check output
ls /tmp/pipeline-dev/
```

Or use the `.env.example` file:

```bash
cp .env.example .env
source .env
uv run python -m asf_mission_data.run example --stage all
```

For the full local-vs-AWS workflow, see [docs/running-pipelines.md](docs/running-pipelines.md).

## Deployment

For the supported ways to build images and run pipelines in AWS, see [docs/running-pipelines.md](docs/running-pipelines.md).

## Docker

Build the image with a canonical tag:

```bash
docker build -t asf-mission-data .
```

Run a pipeline in a local filesystem-backed mode:

```bash
mkdir -p /tmp/asf-mission-data

docker run --rm \
  -e DATA_MODE=LOCAL \
  -e DATA_ROOT=/tmp/asf-mission-data \
  -v /tmp/asf-mission-data:/tmp/asf-mission-data \
  asf-mission-data \
  example --stage all
```

Notes:

- The image tag above is `asf-mission-data`, not `asf_mission_data`.
- If you omit `DATA_MODE`/`DATA_ROOT`, the container defaults to the dev S3 location and expects the corresponding AWS runtime configuration.

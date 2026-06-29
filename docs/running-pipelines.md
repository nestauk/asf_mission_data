# Running Pipelines

This repo supports two main ways to run a pipeline: locally while developing, and via GitHub Actions for AWS runs.

## Quick reference

| I want to... | Use this | Notes |
|---|---|---|
| develop or debug pipeline code | local run | fastest feedback, no AWS dependency |
| run a pipeline using code from a branch | `Build and push Docker Image to ECR` (from your branch), then `Test pipeline in dev` | standard dev test path |
| run a pipeline using code already on `dev` | `Test pipeline in dev` with `image_tag=dev-latest` | quickest dev run; no image build needed |
| run a pipeline in prod | **TODO** `Run pipeline in prod` workflow from `prod` branch | easiest manual pipeline trigger in prod; refreshing data |
| launch a pipeline in AWS from the terminal instead of GitHub UI | `scripts/trigger_pipeline.py` | advanced/debug path |


## Running locally in pipeline development

Use local mode when developing or debugging pipeline logic. Run these commands in your terminal:

```bash
# Set local mode (otherwise the default is the dev S3 bucket)
export DATA_MODE=LOCAL
export DATA_ROOT=/tmp/pipeline-dev

# Run all stages
uv run python -m asf_mission_data.run example --stage all
```

This avoids Docker, ECS, and ECR entirely.

### Stages

Pipelines have two or three stages: **bronze** (raw fetch), **silver** (clean and transform), and optionally **gold** (aggregated outputs). Use `--stage` to control which runs:

- `--stage all` — run every available stage in order
- `--stage bronze` — run only the fetch stage
- `--stage silver` — run only the transform stage
- `--stage gold` — run only the aggregation stage (if the pipeline has one)

When developing, you can run a single stage to avoid re-fetching data you already have.

## Advanced: Running locally in pipeline development with Docker

Use this when you want to test your code inside the container — the same environment it runs in on AWS — without pushing to ECR or triggering a cloud run. This is useful for catching issues specific to the container, such as missing dependencies in the Dockerfile.

First, build the image:

```bash
docker build -t asf-mission-data .
```

Then run a pipeline against your local filesystem:

```bash
mkdir -p /tmp/asf-mission-data

docker run --rm \
  -e DATA_MODE=LOCAL \
  -e DATA_ROOT=/tmp/asf-mission-data \
  -v /tmp/asf-mission-data:/tmp/asf-mission-data \
  asf-mission-data \
  example --stage all
```

The `-v` flag mounts your local directory into the container so output is written to `/tmp/asf-mission-data` on your machine.

Note: the image tag is `asf-mission-data` (hyphen), not `asf_mission_data` (underscore). If you omit `DATA_MODE` and `DATA_ROOT`, the container will try to use the dev S3 bucket instead.

## Running in AWS during pipeline development

Workflows are triggered from the [Actions tab](https://github.com/nestauk/asf_mission_data/actions) in the GitHub repo.

Use the `Test pipeline in dev` workflow for dev runs. It takes three inputs:

- `pipeline` - must match a key in `pipelines.yaml`
- `stage` - one of `all`, `bronze`, `silver`, `gold`
- `image_tag` - ECR tag of the container image to run

Running a pipeline with this workflow will populate data in the `asf-mission-data-dev` S3 bucket.

The workflow summary will show you the resolved task definition, the container image used, and an error if the image tag does not exist in ECR. A missing tag fails before any task is started.

### Which image tag to use?

**If you want to test pipeline code that is already on the `dev` branch**, select the `dev` branch from the dropdown under `Use workflow from` and use the `image_tag=dev-latest`. This is built and pushed automatically from the `dev` branch whenever new code is merged into it.

```text
pipeline=example
stage=all
image_tag=dev-latest
```

**If you want to test pipeline code from a specific branch**, you first need to build an image. Run the `Build and push Docker Image to ECR` workflow and select your branch from the dropdown under `Use workflow from`. The tag is derived from the branch name, e.g.:
- `feat/image-check` → `feat-image-check-latest`
- `alex/test-run` →  `alex-test-run-latest`

Do not guess the tag if you can avoid it. The exact tag is written to the workflow summary, you can copy it from there to use it in `Test pipeline in dev`.

When running the `Test pipeline in dev`, select the `dev` branch from the dropdown under `Use workflow from`, but the `image_tag` should correspond to the branch image.

```text
pipeline=example
stage=all
image_tag=feat-image-check-latest
```

## Running in AWS for a pipeline in production

This writes to the production `asf-mission-data-prod` S3 bucket. Only run this when you intend to refresh production data.

Use the `Run pipeline in prod` workflow in GitHub Actions, **TODO** selecting the `prod` branch from the dropdown under `Use workflow from`. It takes two inputs:

- `pipeline` - must match a key in `pipelines.yaml`
- `stage` - one of `all`, `bronze`, `silver`, `gold`

Data written to the prod bucket is picked up automatically. Infrastructure scans the bucket hourly and runs `CREATE OR REPLACE` on the corresponding DuckLake tables. Those tables are connected to Superset via DuckDB, and changes should appear there after 10 minutes.

## Advanced: Running in AWS from the terminal

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

## Troubleshooting

### I want to check the Docker image was built and pushed to ECR successfully

After the `Build and push Docker Image to ECR` workflow completes, check the `asf-mission-data` [repository in ECR](https://eu-west-2.console.aws.amazon.com/ecr/repositories/private/195787726158/asf-mission-data/_/details?region=eu-west-2) via the AWS console and confirm your tag is listed (either an updated `dev-latest` or a tag corresponding to your feature branch).

---

### I want to watch the logs during a pipeline run in AWS

You can watch the log streams in CloudWatch for each run in the following ECS log groups:

- Dev runs: `asf-mission-data-dev` [ECS log group](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:log-groups/log-group/$252Fecs$252Fasf-mission-data-dev).
- Prod runs: `asf-mission-data-prod` [ECS log group](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:log-groups/log-group/$252Fecs$252Fasf-mission-data-prod).

---

### I want to check the pipeline output landed in S3

After the run completes, check the S3 bucket (`asf-mission-data-dev` for dev runs, or `asf-mission-data-prod` for prod runs) directly in the AWS console to confirm the expected files are present.

---

### The image tag does not exist

Symptom:

```text
Error resolving task definition: Image tag '...' was not found in ECR repository 'asf-mission-data'
```

What to do:

1. run `Build and push Docker Image to ECR`
2. copy the tag from the workflow summary
3. rerun `Test pipeline in dev` with that exact tag

---

### I do not know the pipeline name

Check `pipelines.yaml`. The `pipeline` input must match one of its keys. Pipeline names are the top-level keys, e.g., `example` or `energy_price_cap_levels_annex_9`.

---

*Last updated: 29 June 2026 by Elysia Lucas*

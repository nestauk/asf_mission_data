# Infrastructure

AWS infrastructure for the ASF Mission Data pipelines, managed with AWS CDK (Python). This guide covers what is deployed, how to change it safely, and how GitHub Actions and pipeline runs connect to AWS. For *running* pipelines see [running-pipelines.md](../docs/running-pipelines.md); for *writing* them see [adding-pipelines.md](../docs/adding-pipelines.md).

## Quick reference

| I want to... | Use this | Notes |
|---|---|---|
| see what a change would do in AWS | `cdk diff --context env=dev` from `infrastructure/` | [Preview or deploy](#i-want-to-preview-or-deploy-an-infrastructure-change) |
| deploy an infrastructure change | `cdk deploy --context env=dev`, verify, then `env=prod` | [Preview or deploy](#i-want-to-preview-or-deploy-an-infrastructure-change) |
| change a config value or add an environment | edit `config/dev.py` / `config/prod.py`, then deploy | [Change configuration](#i-want-to-change-an-environments-configuration) |
| fix a workflow that can't authenticate to AWS | check the OIDC role, `AWS_ACCOUNT_ID`, `id-token` permission | [GitHub auth](#how-github-actions-authenticates-to-aws) |
| understand what actually runs my pipeline | ECS Fargate task from the shared task definition | [How pipelines run](#how-pipelines-run-on-aws) |
| put a pipeline on a schedule | not yet possible - currently, all runs are manual | [Schedule a pipeline](#i-want-to-schedule-a-pipeline) |
| find the logs for a run | CloudWatch log group `/ecs/asf-mission-data-{env}` | [Monitoring](#monitoring-logs-and-alerting) |
| know where the data goes after S3 | DuckLake/Superset, in the `nestauk/de_cdp` repo | [Downstream](#downstream-consumers) |

## What's deployed

One CDK app ([`app.py`](app.py)) defining a single stack, `CoreStack`, deployed once per environment as `asf-core-dev` and `asf-core-prod`.

```text
GitHub Actions ────build & push image───▶  ECR: asf-mission-data
      │                                         │
      │  scripts/trigger_pipeline.py            │  image tag {env}-latest
      ▼                                         ▼
ECS Fargate cluster ──runs──▶  task definition asf-mission-data-{env}
asf-mission-data-{env}         (container "app")
                                    │                    │
                                    ▼                    ▼
                          CloudWatch Logs       S3: asf-mission-data-{env}
                    /ecs/asf-mission-data-{env}          │  silver/gold Parquet
                                                         ▼
                                          DuckLake → Superset (nestauk/de_cdp)
```

`CoreStack` creates ([`stacks/core/core_stack.py`](stacks/core/core_stack.py)):

| Resource | Name | Purpose |
|---|---|---|
| S3 bucket | `asf-mission-data-{env}` | Pipeline data (bronze/silver/gold). SSE-S3, public access blocked, SSL enforced, unversioned |
| ECR repository | `asf-mission-data` | Container images for all pipelines. Scan on push, lifecycle rule keeps the last 10 images |
| ECS cluster | `asf-mission-data-{env}` | Fargate (and Fargate Spot) capacity for pipeline tasks; Container Insights disabled |
| ECS task definition | family `asf-mission-data-{env}` | One shared definition; the pipeline to run is chosen by command override at launch |
| GitHub Actions IAM role | `asf-github-actions-{env}` | OIDC-assumed by workflows — see [GitHub auth](#how-github-actions-authenticates-to-aws) |
| Task execution role | `asf-mission-data-{env}-task-execution-role` | Lets the ECS agent pull from ECR and write logs |
| Task role | `asf-mission-data-{env}-task-role` | What pipeline code uses at runtime; read/write on the data bucket |
| Scheduler role | `asf-mission-data-{env}-scheduler-role` | For EventBridge Scheduler to launch tasks — reserved for [future scheduling](#i-want-to-schedule-a-pipeline) |
| Security group | `asf-mission-data-{env}-tasks` | Outbound-only (tasks scrape sources and call S3); no inbound access |
| Log group | `/ecs/asf-mission-data-{env}` | Task logs, one-month retention |

Two structural quirks worth knowing:

- **The ECR repository is shared.** It is created by the *dev* stack only (tagged `Environment: shared`); the prod stack references it by name. Both `dev-latest` and `prod-latest` tags live in the same repository.
- **Networking is the account default VPC** (`vpc-b556bedd` and its subnets, defined in [`config/environments.py`](config/environments.py)). Tasks launch with a public IP for outbound internet access; nothing accepts inbound traffic.

The stack exports its key values as CloudFormation outputs (bucket, ECR URI, role ARNs, cluster ARN, task definition ARN, security group, subnets). `scripts/trigger_pipeline.py` reads these at run time, so renaming exports is a breaking change for pipeline triggering.

## Environments

| Environment | Region | Stack | Data bucket |
|---|---|---|---|
| dev | eu-west-2 | `asf-core-dev` | `asf-mission-data-dev` |
| prod |  eu-west-2 | `asf-core-prod` | `asf-mission-data-prod` |

Both environments live in the same account and region; separation is by resource naming, IAM scoping, and the GitHub-side promotion process ([CONTRIBUTING.md](../docs/CONTRIBUTING.md)).

| Behaviour | Dev | Prod |
|---|---|---|
| Removal policy on bucket | DESTROY | RETAIN |
| Auto-delete S3 objects on stack teardown | Yes | No |
| ECR repository | Created here (shared) | Referenced by name |
| Container `DATA_MODE` | `DEV` | `PROD` |

## Prerequisites

1. AWS CLI configured with credentials for the account
2. Node.js, for the CDK CLI
3. [uv](https://docs.astral.sh/uv/) (the repo's dependency manager)

```bash
# Install the CDK CLI globally
npm install -g aws-cdk

# Install the CDK Python dependencies
uv sync --group infrastructure
```

All CDK commands must be run from the `infrastructure/` directory (where `cdk.json` lives).

## I want to preview or deploy an infrastructure change

Infrastructure changes are shipped by **running `cdk deploy` manually from a developer machine** — there is no CI/CD deployment path yet.

```bash
cd infrastructure

# See what would change (always do this first)
cdk diff --context env=dev

# Deploy to dev, verify behaviour, then deploy to prod
cdk deploy --context env=dev
cdk deploy --context env=prod

# Generate the CloudFormation template without deploying
cdk synth --context env=dev

# List the stacks CDK knows about
cdk list --context env=dev
```

Deploy to dev first and verify (run a pipeline, check the diff did what you expected) before repeating against prod. If the account/region has never been used with CDK you'll be told to bootstrap: `cdk bootstrap aws://195787726158/eu-west-2` — needed once, ever.

## I want to change an environment's configuration

Configuration lives in [`config/`](config/):

- [`environments.py`](config/environments.py) — the `EnvironmentConfig` dataclass: shared defaults (VPC, subnets, project prefix, image retention) and derived names (bucket, cluster, role names) as properties
- [`dev.py`](config/dev.py) / [`prod.py`](config/prod.py) — per-environment values and tags

Change a value, `cdk diff` to confirm the blast radius, then deploy. To add an environment: create `config/{env}.py` with an `EnvironmentConfig`, add it to the `ENVIRONMENTS` dict in `app.py`, and deploy with `--context env={env}`.

One trap: `task_cpu` and `task_memory` in `EnvironmentConfig` are currently **not wired up** — the task definition hardcodes 256 CPU units / 512 MB in `core_stack.py`. Changing the config fields alone does nothing.

## How GitHub Actions authenticates to AWS

Workflows authenticate with **OIDC** — no long-lived AWS keys are stored in GitHub. Each AWS-touching workflow requests a token (`permissions: id-token: write`) and assumes `asf-github-actions-dev` or `asf-github-actions-prod`. The roles trust the pre-existing GitHub OIDC provider in the account, restricted to this repository (`repo:nestauk/asf_mission_data:*`, any branch/workflow), with a one-hour session cap. Sessions are named `GitHubActions-<purpose>-<run id>`, so CloudTrail activity can be traced back to a specific Actions run.

Required GitHub configuration (Settings → Secrets and variables → Actions):

| Level | Kind | Name | Used for |
|---|---|---|---|
| Repository | Secret | `AWS_ACCOUNT_ID` | Building the role ARNs in all four AWS workflows |
| Repository | Variable | `AWS_REGION` | Single source of truth for region (`eu-west-2`); wired into each workflow's `env` block |
| Environment (dev, prod) | Variable | `ENV_NAME` | Environment identity; note it only reaches jobs that declare `environment:` |
| Environment (prod) | Protection rule | required reviewers | The approval gate on `Run pipeline in prod` |

The `prod` GitHub Environment is what makes prod runs wait for a designated reviewer. The `dev` environment exists for symmetry and future protections; no workflow currently declares it.

The role's permissions are scoped to `asf-*` resources: ECR push/pull, bucket read/write, ECS task-definition registration and `RunTask` on the cluster, EventBridge Scheduler management (for future scheduling), plus CloudFormation/IAM management for `asf-*` stacks and roles.

## How pipelines run on AWS

The model is **one image, many pipelines**: the Docker image (built from the repo [`Dockerfile`](../Dockerfile)) contains every pipeline, and the launch-time command override picks which one runs — `["<pipeline>", "--stage", "<stage>"]` against the container's CLI entrypoint.

1. **Images**: `Build and push Docker Image to ECR` builds `linux/amd64` images (matching the task definition's platform) and tags them `<branch-slug>-latest`. Merges to `dev` refresh `dev-latest`; merging `dev` → `prod` re-tags that exact manifest as `prod-latest` (no rebuild).
2. **Task definition**: the shared family `asf-mission-data-{env}` points at the `{env}-latest` image and injects `DATA_MODE`, `DATA_ROOT=s3://asf-mission-data-{env}` and `ASF_ENVIRONMENT`, so pipeline code needs no per-environment configuration of its own.
3. **Launching**: both run workflows call [`scripts/trigger_pipeline.py`](../scripts/trigger_pipeline.py), which reads the `asf-core-{env}` stack outputs (cluster, subnets, security group), and calls `ecs:RunTask`. For a non-default image tag it first validates the tag exists in ECR, then registers a fresh task-definition revision pointing at it.
4. **Compute**: Fargate by default; the trigger script accepts `--capacity-provider FARGATE_SPOT` for interruptible-but-cheaper runs.

Day-to-day usage (which workflow, which image tag, what to check) is covered in [running-pipelines.md](../docs/running-pipelines.md).

## I want to schedule a pipeline

**You can't yet.** All pipeline runs are currently manual, via the GitHub workflows or the trigger script. The `schedule` values in [`pipelines.yaml`](../pipelines.yaml) are declarative intent only — nothing reads them today.

The agreed design (27 July 2026, not yet implemented): `pipelines.yaml` becomes the source of truth; a reconciler script — run by the promote-to-prod workflow after the image re-tag, and manually triggerable — converges EventBridge Scheduler with the file, creating, updating and deleting `asf-`-prefixed schedules to match. Schedules will target the shared task definition via the scheduler role that already exists in the core stack. Scheduling is prod-only; dev runs stay manual by design. The `stack_name` field in `pipelines.yaml` is defunct under this design and will be removed.

<!-- TODO: needs decision — remaining scheduling sub-details: schedule expression syntax and timezone (Europe/London vs UTC); the "not scheduled" convention (`never` vs omitting the field); which stage scheduled runs execute; dedicated schedule group vs `default`; CI validation of pipelines.yaml. -->

## Monitoring, logs and alerting

**Logs**: every task logs to CloudWatch log group `/ecs/asf-mission-data-{env}` ([dev](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:log-groups/log-group/$252Fecs$252Fasf-mission-data-dev) · [prod](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:log-groups/log-group/$252Fecs$252Fasf-mission-data-prod)), one stream per run under the `pipeline/` prefix. Retention is one month.

**Traceability**: workflow-initiated AWS activity is identifiable in CloudTrail by the role session name, which embeds the GitHub Actions run ID.

**Alerting**: none exists yet. `asf_mission_data/alerting.py` is an empty stub, and nothing notifies anyone when a run fails — failed runs are only visible in the workflow summary (for manual runs) and CloudWatch. Treat "check the logs after a prod run" as a required manual step until this changes.

## Downstream consumers

After a pipeline writes silver/gold Parquet to the bucket, consumption is handled by the Data Engineering Core Data Platform ([`nestauk/de_cdp`](https://github.com/nestauk/de_cdp)) — not by anything in this repo. Its DuckLake stack runs DuckDB over a PostgreSQL metadata catalogue and registers tables from the source bucket's `data/silver/` and `data/gold/` latest partitions on an **hourly** cron; Superset then queries those tables through the catalogue. Bronze data is not registered.

> **Known discrepancy** (27 July 2026): all of de_cdp's environment configs — including prod — currently point at `asf-mission-data-dev`. Data written to the **prod** bucket is *not* being picked up, despite what [running-pipelines.md](../docs/running-pipelines.md) says about prod runs appearing in Superset. Until de_cdp is repointed, treat the dev bucket as the one feeding dashboards.

<!-- TODO: follow up with Data Engineering — repoint de_cdp prod at asf-mission-data-prod (de_cdp config/prod.py), then correct or confirm the claims in running-pipelines.md. -->

## Costs

Approximate, using eu-west-2 list prices as of July 2026 — sanity-check against [current AWS pricing](https://aws.amazon.com/fargate/pricing/) before relying on them. There are no always-on compute resources; the standing cost is storage, and the marginal cost is per task-run.

| Resource | Driver | Approximate cost |
|---|---|---|
| Fargate task run | 0.25 vCPU / 0.5 GB, ~$0.047 per vCPU-hour + ~$0.005 per GB-hour | ~$0.001–0.002 per 5-minute run |
| S3 storage | ~$0.024/GB-month | ~$0.25/month per 10 GB |
| ECR storage | $0.10/GB-month, capped at 10 images by lifecycle rule | ~$0.50/month |
| CloudWatch Logs | ~$0.59/GB ingested; storage minor at one-month retention | pennies at current volume |
| EventBridge Scheduler | $1.00 per million invocations (once implemented) | negligible |

Realistic total at current scale (a handful of pipelines, run manually or daily): **single-digit dollars per month per environment**. The levers that change this are run frequency, run duration, and log volume — not the standing infrastructure.

## Troubleshooting

### A workflow fails with "Not authorized to perform sts:AssumeRoleWithWebIdentity"

1. Check the job has `permissions: id-token: write`
2. Check `AWS_ACCOUNT_ID` (repo secret) and `AWS_REGION` (repo variable) are set — an empty region makes the credentials action fail obscurely
3. Check the role's trust policy subject matches `repo:nestauk/asf_mission_data:*` exactly (a repo rename breaks this)

### `cdk synth`/`deploy` fails complaining about environment or bootstrap

- "Need to perform AWS calls... but no credentials configured" — the VPC lookup (`Vpc.from_lookup`) needs valid credentials the first time; afterwards the result is cached in `cdk.context.json` (committed)
- Bootstrap errors — run `cdk bootstrap aws://195787726158/eu-west-2` once

### A task fails to launch

The trigger script prints ECS failure reasons. Common ones: the image tag doesn't exist in ECR (see [running-pipelines.md](../docs/running-pipelines.md#the-image-tag-does-not-exist)), or stack outputs changed and the script resolved stale infrastructure — check `aws cloudformation describe-stacks --stack-name asf-core-{env}`.

### Something was changed in the console and CDK is out of sync

```bash
aws cloudformation detect-stack-drift --stack-name asf-core-dev
aws cloudformation describe-stack-resource-drifts --stack-name asf-core-dev
```

Fix drift by re-deploying from CDK (the code wins), not by editing the template in the console.

---

*Last updated: 27 July 2026 by Alex*

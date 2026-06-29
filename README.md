# ASF Mission Data

Data pipelines for fetching, processing and storing core ASF mission datasets to S3.

## How pipelines work

Each pipeline has two or three stages: **bronze** (fetch and store raw data), **silver** (clean and transform into Parquet), and optionally **gold** (aggregate into dashboard-ready outputs).

Stages are implemented as **[Hamilton](https://hamilton.dagworks.io/)** dataflows, where each function defines a transformation and its arguments declare its dependencies. Hamilton then automatically resolves the execution order of functions into a Directed Acyclic Graph (DAG). This gives us a consistent structure for writing pipelines, makes transforms easy to test in isolation, makes data dependencies explicit, and lets Hamilton render the pipeline as a visual graph. It also has built-in decorators for data quality checks.

In production, pipelines run as Docker containers on AWS ECS, triggered via GitHub Actions. Data is stored in S3 with separate dev and prod buckets.

## Project structure

```
asf_mission_data/           # Python package
├── pipeline/
│   └── <pipeline-name>/    # one directory per pipeline, each with its own README
├── alerting.py             # Slack alerting
├── logging_utils.py        # Logging utilities
├── run.py                  # CLI entrypoint
├── storage.py              # Local and S3 read/write utilities
└── utils.py                # Shared utility functions
.github/workflows/          # CI/CD workflows
docs/                       # Guides and runbooks
infrastructure/             # AWS CDK infrastructure
scripts/                    # Utility scripts
tests/                      # Test suite
Dockerfile                  # Container image for running pipelines in AWS
pipelines.yaml              # Pipeline registry
pyproject.toml              # Project config and dependencies
```

## Docs

| Guide | Covers |
|---|---|
| [Running pipelines](docs/running-pipelines.md) | Local, Docker, GitHub Actions, ad hoc AWS |
| [Development guide](docs/DEVELOPMENT.md) | Editor setup, testing, pre-commit |
| [Adding a pipeline](docs/adding-pipelines.md) | Creating a new ETL pipeline |
| [Contributing](docs/CONTRIBUTING.md) | PR process, code standards |
| [Infrastructure](infrastructure/README.md) | AWS CDK resources and deployment |

Each pipeline has its own README at `asf_mission_data/pipeline/<name>/README.md`. For the full list of existing pipelines, see [`pipelines.yaml`](pipelines.yaml).

## Setup

### Prerequisites

- Python 3.12+ (uv will install this automatically if needed)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency management
- Graphviz, for pipelines that render Hamilton DAG images. The Python `graphviz` package is installed by `uv sync`, but the system `dot` executable must also be available on your `PATH`.

  macOS:

  ```bash
  brew install graphviz
  dot -V
  ```

  Windows:

  ```powershell
  winget install Graphviz.Graphviz
  dot -V
  ```

  If `dot -V` is not found on Windows, restart your terminal and check that the Graphviz `bin` directory is on `PATH`. Chocolatey users can install it with `choco install graphviz`.

### Installation

```bash
# Clone the repo
git clone https://github.com/nestauk/asf_mission_data.git
cd asf_mission_data

# Install dependencies (creates .venv automatically)
uv sync

# Activate virtual environment
source .venv/bin/activate

# Or run commands directly without activating, e.g.
uv run python -m asf_mission_data.run example --stage all
```

## Infrastructure

Infrastructure is managed with [AWS CDK](https://aws.amazon.com/cdk/) (Python).

### Core resources (deployed)

| Resource | Dev | Prod |
|----------|-----|------|
| S3 bucket | `asf-mission-data-dev` | `asf-mission-data-prod` |
| ECR repository | `asf-mission-data` | `asf-mission-data` |
| GitHub Actions IAM role | `asf-github-actions-dev` | `asf-github-actions-prod` |

### Deploying infrastructure

```bash
# Install CDK dependencies
uv sync --extra infrastructure
npm install -g aws-cdk

# Deploy to dev
cd infrastructure
cdk deploy --context env=dev

# Preview changes
cdk diff --context env=dev
```

See [infrastructure/README.md](infrastructure/README.md) for full documentation.

---

*Last updated: 29 June 2026 by Elysia Lucas*

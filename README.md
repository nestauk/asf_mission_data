# ASF Mission Data

ETL pipelines for the ASF Policy Dashboard.

## Quick start

### Prerequisites

- Python 3.12+ (uv will install this automatically if needed)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) for dependency management

### Installation

```bash
# Clone the repo
git clone https://github.com/nestauk/asf_mission_data.git
cd asf_mission_data

# Install dependencies (creates .venv automatically)
uv sync

# Activate virtual environment
source .venv/bin/activate

# Or run commands directly without activating
uv run python -m asf_mission_data.pipeline.example.handler
```

### Running pipelines locally

```bash
# Set local data root (pipelines will read/write here instead of S3)
export DATA_ROOT=/tmp/pipeline-dev

# Run the example pipeline
uv run python -m asf_mission_data.pipeline.example.handler

# Check output
ls /tmp/pipeline-dev/
```

Or use the `.env.example` file:

```bash
cp .env.example .env
source .env
uv run python -m asf_mission_data.pipeline.example.handler
```

## Project structure

```
asf_mission_data/           # Python package (pipeline code)
├── storage.py              # Storage abstraction (local/S3)
├── alerting.py             # Slack alerting utilities
└── pipeline/               # Pipeline implementations
    └── example/            # Template pipeline
infrastructure/             # CDK infrastructure
├── app.py                  # CDK entry point
├── cdk.json                # CDK configuration
├── config/                 # Environment configurations
│   ├── environments.py     # EnvironmentConfig dataclass
│   ├── dev.py              # Dev environment values
│   └── prod.py             # Prod environment values
└── stacks/                 # CDK stacks
    └── core_stack.py       # Shared resources (S3, ECR, IAM)
tests/                      # Test suite
docs/                       # Documentation and runbooks
scripts/                    # Utility scripts
```

## Infrastructure

Infrastructure is managed with [AWS CDK](https://aws.amazon.com/cdk/) (Python).

### Core resources (deployed)

| Resource | Dev | Prod |
|----------|-----|------|
| S3 bucket | `asf-mission-data-dev` | `asf-mission-data-prod` |
| ECR repository | `asf-pipelines-dev` | `asf-pipelines-prod` |
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

## Creating a new pipeline

*(TODO: Document after Hamilton spike — see docs/creating-a-pipeline.md)*

## Pipeline registry

All pipelines are registered in `pipelines.yaml`. Update this file when adding a new pipeline.

## Deployment

*(TODO: Document CI/CD workflow)*

## Runbook

*(TODO: Agree on doc strategy)*

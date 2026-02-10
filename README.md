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
infrastructure/             # CloudFormation templates
├── core/                   # Shared resources (S3, IAM)
└── pipeline/               # Per-pipeline template
tests/                      # Test suite
docs/                       # Documentation and runbooks
scripts/                    # Utility scripts
```

## Creating a new pipeline

*(TODO: Document after Hamilton spike — see docs/creating-a-pipeline.md)*

## Pipeline registry

All pipelines are registered in `pipelines.yaml`. Update this file when adding a new pipeline.

## Deployment

*(TODO: Document CI/CD workflow)*

## Runbook

*(TODO: Agree on doc strategy)*

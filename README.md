# ASF Mission Data Tool

ETL pipelines for the ASF Policy Dashboard.

## Quick start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone the repo
git clone https://github.com/nestauk/asf_mission_data_tool.git
cd asf_mission_data_tool

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Running pipelines locally

*(TODO: This isn't working yet)*

```bash
# Set local data root (pipelines will read/write here instead of S3)
export DATA_ROOT=/tmp/pipeline-dev

# Run the example pipeline
python -m asf_mission_data_tool.pipeline.example.handler

# Check output
ls /tmp/pipeline-dev/
```

## Project structure

```
asf_data_hub/           # Python package
├── storage.py          # Storage abstraction (local/S3)
├── alerting.py         # Slack alerting utilities
└── pipeline/           # Pipeline implementations
    ├── example/        # Template pipeline
    └── energy_cap/     # Energy price cap pipeline
infrastructure/         # CloudFormation templates
tests/                  # Test suite
```

## Creating a new pipeline

See [docs/creating-a-pipeline.md](docs/creating-a-pipeline.md) *(TODO)*

## Pipeline registry

All pipelines are registered in `pipelines.yaml`. Update this file when adding a new pipeline.

## Deployment

*(TODO: Document CI/CD workflow)*

## Runbook

See [docs/runbook.md](docs/runbook.md) for operational procedures.

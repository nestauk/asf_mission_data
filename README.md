# ASF Mission Data

ETL pipelines for the ASF Policy Dashboard.

## Quick start

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

# Or run commands directly without activating
uv run python -m asf_mission_data.run example --stage all
```

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

## Developer setup

### Pre-commit and code formatting

This project uses **pre-commit hooks** and **ruff** to automatically format and lint code. The best experience is to set up your editor to format on save, so issues are fixed before they reach the pre-commit hook.

#### VS Code setup (recommended)

1. **Install the Ruff extension** - Search for "Ruff" in VS Code extensions and install the official Astral extension
2. **Add to `.vscode/settings.json`** (You may need to first select the "Preferences: Open Workspace Settings (JSON)" command in the Command Palette (Mac: ⇧⌘P Win: Ctrl + shift + P)):

```json
{
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.fixAll.ruff": "explicit"
    }
  }
}
```

This auto-formats your Python files every time you save, so ruff issues are fixed before you commit.

#### Command line

You can also manually format/check code:

```bash
# Auto-fix formatting and common issues
uv run ruff format .

# Check for remaining linting issues
uv run ruff check . --fix
```

#### Pre-commit hooks

Pre-commit hooks run automatically when you commit. If you see issues at commit time:

```bash
# Install the pre-commit hooks (one-time setup)
uv run pre-commit install

# This will run on every git commit and auto-fix what it can
# If it makes changes, stage them and commit again

# Test hooks without committing
uv run pre-commit run
# or
uv run pre-commit run --all-files

# Commit without running hooks
git commit --no-verify
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

## Creating a new pipeline

*(TODO: Document after Hamilton spike — see docs/creating-a-pipeline.md)*

## Testing pipelines

For new bronze/silver pipelines in this repo, the recommended baseline is:

- keep bronze tests focused on fetching and storing raw data correctly
- keep silver tests focused on transformation logic and data contracts
- add one local integration test that proves the real pipeline wiring works end to end without using S3

The example pipeline includes a complete test template:

- `tests/pipeline/example/test_bronze.py` shows how to mock an external source and assert the raw file plus metadata are written correctly
- `tests/pipeline/example/test_silver.py` shows how to test silver transform functions, validate a dataframe schema, and run a local integration test against a temporary directory
- `tests/pipeline/example/conftest.py` shows how to share sample input data and set `DATA_MODE=LOCAL` for tests

When adding a new pipeline, aim to include at least:

1. one bronze unit test that mocks the upstream fetch
2. one bronze persistence test that checks the expected file and metadata paths
3. unit tests for each non-trivial silver transform
4. one schema or contract test that rejects invalid data
5. one local integration test that runs the real pipeline against `tmp_path`

This split matters because different failures happen in different places:

- bronze tests catch broken downloads, missing metadata, and incorrect storage paths
- silver unit tests catch parsing and transformation bugs
- schema tests catch subtle bad data before it reaches the canonical output
- integration tests catch wiring mistakes between storage, Hamilton, and parquet writes

Run just the example pipeline tests with:

```bash
uv run pytest tests/pipeline/example
```

Run the full suite with:

```bash
uv run pytest
```

## Pipeline registry

All pipelines are registered in `pipelines.yaml`. Update this file when adding a new pipeline.

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

## Runbook

Start with [docs/running-pipelines.md](docs/running-pipelines.md) for the standard local, GitHub UI, and ad hoc AWS run paths.

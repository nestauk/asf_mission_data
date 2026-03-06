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
      "source.fixAll": "explicit"
    }
  }
}
```

This auto-formats your code every time you save, so ruff issues are fixed before you commit.

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

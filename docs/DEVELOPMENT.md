# Development Guide

Day-to-day workflow for working in this repo: environment setup, notebooks, testing, linting, and type checking. For project structure and architecture, see the [README](../README.md). For adding a new pipeline, see [adding-pipelines.md](../docs/adding-pipelines.md). For running pipelines locally or in AWS, see [running-pipelines.md](../docs/running-pipelines.md).

## Contents

- [Setting up your environment](#setting-up-your-environment)
- [Managing dependencies](#managing-dependencies)
- [Git workflow](#git-workflow)
- [Editor setup](#editor-setup)
- [Linting and formatting](#linting-and-formatting)
- [Type checking](#type-checking)
- [Pre-commit hooks](#pre-commit-hooks)
- [Testing](#testing)
- [Notebooks](#notebooks)
- [Package standards](#package-standards)

## Setting up your environment

```bash
# Install all dependencies including dev tools
uv sync --group dev

# Install pre-commit hooks (see "Pre-commit hooks" below)
uv run pre-commit install
```

If you're running pipelines locally, also copy the example environment file:

```bash
cp .env.example .env
source .env
```

`.env` is gitignored. `.envrc` will auto-source it for you if you use [direnv](https://direnv.net/). See [`.env.example`](../.env.example) for the available variables, and [running-pipelines.md](running-pipelines.md) for how `DATA_MODE`/`DATA_ROOT` affect where a pipeline reads and writes data.

## Managing dependencies

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. Don't manually edit. Use `uv add`/`uv remove`, which update both together.

```bash
# Add a runtime dependency
uv add <package>

# Add a dev-only dependency (linting, testing, notebooks, etc.)
uv add --group dev <package>

# Add an infrastructure-only dependency (CDK, etc.)
uv add --group infrastructure <package>

# Remove a dependency
uv remove <package>
```

These commands update `pyproject.toml`, re-resolve `uv.lock`, and sync your `.venv` in one step.

To pick up newer versions of dependencies you already have:

```bash
# Upgrade everything to the latest versions allowed by pyproject.toml
uv lock --upgrade

# Upgrade a single package
uv lock --upgrade-package <package>

# Then sync your environment to match
uv sync --group dev
```

Always commit `uv.lock` alongside any `pyproject.toml` change. CI and other developers install from the lockfile, they don't re-resolve.

## Git workflow

- `dev` is the integration branch. Branch off `dev` for new work and open a PR back into it. Direct commits to `dev` are blocked by a pre-commit hook (`no-commit-to-branch`).
- `prod` tracks what's live in production. Merging a PR from `dev` into `prod` triggers `promote-to-prod.yaml`, which re-tags the already-tested `dev-latest` ECR image as `prod-latest`. It does not rebuild the image, so what you tested in dev is exactly what runs in prod.
- CI (`run-tests.yaml`) runs `uv run pytest` on every PR into `dev`. Pre-commit checks (see below) also run in CI via `pre-commit.yaml`.

See [CONTRIBUTING.md](CONTRIBUTING.md) for the PR process itself.


## Editor setup

### VS Code (recommended)

1. Install the **Ruff** extension — search for "Ruff" in the VS Code extensions marketplace and install the official Astral extension.
2. Add to `.vscode/settings.json` (Command Palette → "Preferences: Open Workspace Settings (JSON)"):

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

   This formats and fixes Python files on save, so most ruff issues are resolved before you commit.

## Linting and formatting

This project uses **[ruff](https://docs.astral.sh/ruff/)** for both linting and formatting, configured in `pyproject.toml`. Rules currently enabled are pycodestyle, pyflakes, isort, and flake8-bugbear (`E`, `F`, `I`, `W`, `B`); stricter rule sets like type-annotation and docstring checks are left off for now while pipeline patterns are still settling.

```bash
# Auto-fix formatting and common issues
uv run ruff format .

# Check for remaining linting issues
uv run ruff check . --fix
```

Ruff is enforced in CI and pre-commit. A PR with lint or format issues will fail before it can merge.


## Type checking

Type annotations are expected on all functions in the package (see [Package standards](#package-standards) below), and `mypy` is configured in `pyproject.toml` with a fairly strict profile (`disallow_untyped_defs`, `disallow_any_generics`, `warn_return_any`).

```bash
uv run mypy asf_mission_data
```

**Note:** mypy isn't run by pre-commit or CI, so type errors won't block a PR. Run it yourself before opening one if you want to run those checks.


## Pre-commit hooks

Pre-commit hooks run automatically on `git commit` and cover linting/formatting (ruff), secret scanning (gitleaks), config validation (`pyproject.toml`, GitHub workflow YAML), and basic file hygiene (trailing whitespace, large files, merge conflicts, direct commits to `dev`). The full list is in [`.pre-commit-config.yaml`](../.pre-commit-config.yaml).

```bash
# One-time setup
uv run pre-commit install

# Run on staged files only (what happens automatically at commit time)
uv run pre-commit run

# Run on the whole repo
uv run pre-commit run --all-files

# Skip hooks for a commit (avoid unless you have a good reason)
git commit --no-verify
```

If a hook modifies files (e.g. ruff auto-fixes something), the commit is aborted. Stage the changes it made and commit again.


## Testing

Tests live in `tests/`, mirroring the package layout (e.g. `asf_mission_data/storage.py` → `tests/test_storage.py`, pipeline tests under `tests/pipeline/<name>/`).

```bash
# Run the full test suite with coverage
uv run pytest

# Run a single file or test
uv run pytest tests/test_storage.py
uv run pytest tests/test_storage.py -k test_get_data_path_defaults_to_dev_bucket
```

`pytest.ini_options` in `pyproject.toml` runs with `--cov=asf_mission_data --cov-report=term-missing` by default, so every run prints a coverage summary with the line numbers that aren't covered.

For anything that reads environment variables, hits S3, or shells out, use `pytest`'s `monkeypatch` fixture (or `pytest-mock`'s `mocker`) rather than mutating real environment/global state. Existing tests in `tests/test_storage.py` and `tests/test_trigger_pipeline.py` are good examples of the pattern:

```python
def test_get_data_path_defaults_to_dev_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATA_ROOT", raising=False)
    assert get_data_path("data/example/file.csv") == "s3://asf-mission-data-dev/data/example/file.csv"
```

CI runs the same `uv run pytest` command on every PR into `dev`; a failing test blocks the merge.


## Notebooks

JupyterLab is included in the dev dependencies. To launch it:

```bash
uv run jupyter lab
```

Notebooks (`*.ipynb`) are gitignored wherever they live, so put yours anywhere convenient (a `notebooks/` folder at the repo root is a reasonable default). `marimo` is also available as a dev dependency if you prefer its reactive, git-friendly notebook format (`uv run marimo edit`).

Because `uv sync` installs the package in editable mode, you can import directly from it in a notebook:

```python
from asf_mission_data.storage import read_parquet
```

Call the real package functions from your notebook instead of retyping the same logic there. That way there's only one copy of the logic, and moving it into a `.py` module later is just cut-and-paste. Once it's in the package and tested, you're done with the notebook.

## Package standards

When you're ready to move code out of a notebook and into `asf_mission_data/`, it should be:

- **Typed** - all functions have type annotations. This is what `mypy` checks (see [Type checking](#type-checking)) — run it before opening a PR, since it isn't automated yet.
- **Tested** - covered by tests in `tests/`. Aim to cover fetch, transform, and validation logic, not just the happy path.
- **Linted** - passes `ruff format` and `ruff check`. This part *is* enforced automatically by pre-commit and CI.
- **Deterministic** - no hardcoded local paths, no side effects on import. Anything environment-specific (paths, credentials, endpoints) should come from `asf_mission_data.storage` or environment variables, not be hardcoded.

---

*Last updated: 2 July 2026 by Elysia Lucas*

# Development Guide

## Setting up your environment

```bash
# Install all dependencies including dev tools
uv sync --group dev

# Install pre-commit hooks
uv run pre-commit install
```

---

## Starting a notebook

JupyterLab is included in the dev dependencies. To launch it:

```bash
uv run jupyter lab
```

This opens JupyterLab in your browser. Create your notebook inside the `notebooks/` folder.

To import from the package inside a notebook, the package is already available because `uv sync` installs it in editable mode:

```python
from asf_mission_data.transforms import clean_installations
```

This means your notebook is always running against the real package code rather than reimplementing logic inline, which makes the eventual translation to a `.py` module much easier.

---

## `asf_mission_data/` — the package

When you're ready to move code out of a notebook, ideally all code in the package should be:

- **Typed** — all functions should have type annotations
- **Tested** — covered by tests in `tests/`
- **Linted** — passes ruff and mypy checks (enforced by pre-commit)
- **Deterministic** — no hardcoded local paths, no side effects on import

Once the logic is in the package and tested, any notebooks have served their purpose and can be discarded.

---

## Running tests and checks

```bash
# Run the test suite
uv run pytest

# Run all pre-commit checks manually
uv run pre-commit run --all-files
```

BELOW MOVED OUT FROM README.md

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

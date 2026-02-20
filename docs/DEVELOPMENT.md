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

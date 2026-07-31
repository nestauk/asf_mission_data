<!-- PR template for merges to dev -->

---

## Description

<!-- What does this change, and why? -->

Fixes # <!-- Issue number -->

## Type of change

- [ ] New pipeline
- [ ] Change to an existing pipeline
- [ ] Package / infrastructure change
- [ ] Docs only

## Checklist

- [ ] `uv run pytest` passes locally
- [ ] `uv run pre-commit run --all-files` passes (ruff, gitleaks, etc.)
- [ ] If this adds a new pipeline: it's registered in `pipelines.yaml` and has its own `README.md`
- [ ] I've merged the latest `dev` into this branch

## Testing notes

<!-- How did you verify this works? e.g. ran locally with `--stage all`, ran via the "Test pipeline in dev" GitHub Actions workflow -->

## Instructions for reviewer

<!-- Anything they should pay particular attention to -->

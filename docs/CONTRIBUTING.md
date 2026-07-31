# Contributing

This covers the human process for getting a change into production: branching, PRs, and review. For environment setup, testing, linting, and type checking, see [DEVELOPMENT.md](DEVELOPMENT.md).

## Issues

Work is tracked as GitHub issues, labelled along two axes. Apply one `area:` and one `type:` label to every issue. See the [repo's Labels page](https://github.com/nestauk/asf_mission_data/labels) for the full list.

**`area:*`** (which part of the codebase the issue touches):

| Label | Use for |
|---|---|
| `area:architecture` | Technical decisions, standards, conventions, operating model questions |
| `area:data-pipeline` | Work on a specific dataset pipeline |
| `area:platform` | The shared setup that packages, deploys, triggers, and runs pipelines |
| `area:shared-framework` | Reusable pipeline code, helpers, patterns, common building blocks |

**`type:*`** (the nature of the work):

| Label | Use for |
|---|---|
| `type:bug` | Something isn't working |
| `type:chore` | Maintenance work, dependency updates, config tweaks |
| `type:decision` | Architectural/design choices that need discussion or recording |
| `type:documentation` | Improvements or additions to documentation |
| `type:feature` | New capability |

Two standalone labels don't fit either axis: `question` (further information requested) and `wontfix` (won't be worked on).


## Branching

Branch off `dev`. If the work is tracked as an issue, name your branch `<issue-number>-<short-description>` (e.g. `37-etl-code-for-heat-pump-deployment-statistics-data`) and reference the issue in your PR description (`Fixes #<number>`) so it closes automatically on merge. Not every branch needs an issue behind it - a clear, descriptive branch name is what actually matters.

## Developer workflow

End-to-end path from a feature branch to a verified change in production, in two phases.

### Phase 1: land the change on `dev`

1. Branch off `dev` (e.g. `37-my-pipeline-change`).
2. Test the branch before opening a PR:
   - Manually trigger `Build and push Docker Image to ECR` to build an image tagged from your branch.
   - Manually trigger `Test pipeline in dev` against that image tag and spot-check the dev S3 output.
   - Fix any issues before opening a PR.
3. Open a PR into `dev`. The PR body auto-fills from [`.github/pull_request_template.md`](../.github/pull_request_template.md).
   - `run-tests` and `pre-commit` run automatically.
   - Can be approved by anyone; self-merge is allowed.
4. Merge to `dev`. This automatically triggers `Build and push Docker Image to ECR`, refreshing the `dev-latest` image.

### Phase 2: promote `dev` to `prod`

5. Re-verify on dev: manually trigger `Test pipeline in dev` with `image_tag=dev-latest` and spot-check the S3 output again. If it fails, fix it in a new branch and repeat Phase 1 before continuing.
6. Open a PR from `dev` into `prod`. See [Using the prod PR template](#using-the-prod-pr-template) below. The default template that loads here is the *dev* one, so you must switch it manually.
   - `run-tests` and `pre-commit` run automatically.
   - No self-merge and requires approval from a CODEOWNER (Elysia, Dan, or Alex - see [`.github/CODEOWNERS`](../.github/CODEOWNERS)).
7. Approver merges to `prod`. This triggers `promote-to-prod.yaml`, which re-tags the existing `dev-latest` image as `prod-latest` (it does not rebuild).
8. Approver triggers `Run pipeline in prod`, spot-checks the prod S3 output, and confirms the Superset datasets look correct.

There's no separate rollback process. If step 8 turns up a problem, fix it the normal way: branch from `dev`, apply the fix, and repeat both phases to re-promote.

## Using the prod PR template

There is a different PR template that should be used when merging `dev` to `prod`.

[`.github/pull_request_template.md`](../.github/pull_request_template.md) is the repo-wide default and auto-fills *every* new PR, including ones targeting `prod` (GitHub has no way to pick a different template per target branch).

To load [`prod_template.md`](../.github/PULL_REQUEST_TEMPLATE/prod_template.md) instead, open the PR via this URL, which selects it with a `template` query parameter:

```
https://github.com/nestauk/asf_mission_data/compare/prod...dev?quick_pull=1&template=prod_template.md
```

**Already opened the PR with the dev checklist by mistake?** Just replace the body with the prod checklist manually - no need to close and reopen.

## Code standards

See [DEVELOPMENT.md's Package standards](DEVELOPMENT.md#package-standards): typed, tested, linted, deterministic. Ruff and tests are enforced by CI.

---

*Last updated: 2 July 2026 by Elysia Lucas*

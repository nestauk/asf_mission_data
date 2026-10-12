# Bug report: default-tag pipeline runs silently executed a stale image

| | |
|---|---|
| **Date discovered** | October 2026 |
| **Date resolved** | 2026-10-12 (an earlier tag-comparison fix drafted on 2026-10-06 was never committed; superseded by the digest-pinned design below) |
| **Severity** | Medium — no data corruption, but pipeline runs silently executed old code with no error or warning |
| **Affected component** | `scripts/trigger_pipeline.py` (`resolve_task_definition`) |
| **Discovered by** | Elysia, while deploying a bronze-node schema fix |
| **Fixed in** | Digest-pinned `resolve_task_definition` + regression tests in `tests/test_trigger_pipeline.py` |

## Summary

Triggering a pipeline with the default image tag (`dev-latest` or `prod-latest`) did not reliably run the latest image. If anyone had previously run the pipeline with a *non-default* tag (e.g. a feature-branch tag), every subsequent default-tag run kept executing that old branch image instead — with no error, no warning, and nothing in the logs to indicate it. The effect persisted until either another non-default-tag run or a `cdk deploy` happened to overwrite it.

The practical symptom: you merge a fix to `dev`, a fresh `dev-latest` image builds and pushes successfully, you trigger the pipeline... and the logs show the *old, unfixed* code failing with the exact error you just fixed.

## Background:

If you're comfortable with ECS task definitions and ECR tags, skip to [The bug](#the-bug).

### How our pipelines run in AWS

Our pipelines don't run on a server that's always on. Each run works like this:

1. The pipeline code is packaged into a **Docker image** — a frozen snapshot of the code plus everything it needs to run.
2. The image is stored in **ECR** (Elastic Container Registry) — AWS's Docker image store, like a private Docker Hub. Ours is the `asf-mission-data` repository.
3. When someone triggers a run, **ECS Fargate** (AWS's "run a container without managing servers" service) pulls the image from ECR, runs it as a one-off task, and shuts down.

### Image tags, and why `dev-latest` is a moving target

Every image in ECR is identified by a **tag**. Crucially, tags in our repository are *mutable* — they're more like git branch names than git commit hashes:

- Every push to the `dev` branch builds a new image and re-points the `dev-latest` tag at it (`build-and-push.yaml`).
- Feature-branch builds get a tag derived from the branch name, e.g. `56-feature-new-pipeline-latest`.
- Promoting to prod doesn't rebuild anything — it re-points the `prod-latest` tag at the exact image that was tested in dev (`promote-to-prod.yaml`).

So "run `dev-latest`" *should* always mean "run whatever was most recently merged to dev". Fargate pulls the image fresh at task start, so as long as the task is told to run the `dev-latest` tag, it will get the newest image.

### Task definitions: the layer the bug lives in

ECS doesn't accept "run this image" directly. It requires a **task definition** — a saved recipe that says which image to run, with how much CPU/memory, which IAM roles, etc. Think of it as a launch configuration.

Two properties of task definitions matter here:

- They are **immutable and versioned**. You never edit one; you register a new numbered **revision** (`asf-mission-data-dev:6`, `:7`, `:8`, ...). All revisions share a **family** name (`asf-mission-data-{environment}`).
- When you ask ECS about a family *by name*, it gives you the **latest active revision**. Whatever that revision says — including which image tag it points at — is what runs.

Our CDK infrastructure code creates the family with the image set to `{environment}-latest` (`infrastructure/stacks/core/core_stack.py`). So after any `cdk deploy`, the latest revision points at `dev-latest`/`prod-latest`.

But `scripts/trigger_pipeline.py` *also* registers revisions, at run time: when you request a non-default tag (to test a feature branch in AWS), it copies the current revision, swaps the image to your branch tag, and registers that as a new revision. **That new revision is now the family's latest — permanently**, until something registers another one on top of it. Running a feature branch doesn't "temporarily" use that image; it re-points the family.

That's the whole setup. Now the bug is a two-line story.

## The bug

`resolve_task_definition` in `scripts/trigger_pipeline.py` had two paths:

```python
if image_tag == f"{environment}-latest":
    # Default tag: just run whatever revision is currently active.
    return ResolvedTaskDefinition(
        task_definition=current["taskDefinitionArn"],
        app_image=get_app_container_image(current["containerDefinitions"]),
    )

# Non-default tag: register a NEW revision pointing at the requested tag.
new_revision = ecsclient.register_task_definition(...)
```

The default-tag path **assumed** the active revision still pointed at `{environment}-latest`. It never checked. But the non-default path re-points the family every time it runs. So:

1. Someone tests a feature branch in AWS with `--image-tag 56-feature-new-pipeline-latest`. A new revision is registered pointing at that tag. ✅ works.
2. The branch is merged; a fresh `dev-latest` image is built and pushed. The task-definition family **still points at `56-feature-new-pipeline-latest`** — nothing in the build pipeline touches task definitions; it only pushes images.
3. Someone triggers a normal run with the default `dev-latest` tag. The script sees the tag is the default, grabs the active revision, and runs it — which runs the *frozen feature-branch image*, not `dev-latest`. ❌ silently stale.
4. This repeats for every default-tag run until another non-default run or a `cdk deploy` overwrites the revision.

### Why nobody hit it before

Our usual workflow accidentally masked the bug. The habit was: build the feature branch, test it in AWS with its branch tag, *then* merge. Each branch test re-pinned the family to an image containing the newest code — so even though default-tag runs were technically running "the wrong tag", the image contents were effectively current. The bug only surfaced the first time a fix was tested *locally only* and merged straight to dev: nothing re-pinned the family, and the stale pin finally pointed at genuinely old code.

## How it was discovered

Debugging sequence, annotated with what was actually happening:

1. **Prod run of heat pump deployment stats fails with schema drift.** (Genuine, unrelated data issue — not this bug.)
2. **Fix made on a feature branch, verified locally, merged to dev.** New `dev-latest` image built and pushed. ✅
3. **Manual dev trigger via GitHub Actions fails** — CloudWatch logs show the error coming from the *old* line of code that the merge had just fixed. *(The family was pinned to a stale branch tag from an earlier feature test; the run never used `dev-latest`.)*
4. **The dev branch runs fine locally.** *(Local runs don't go through ECS task definitions at all — first hint the code was fine and the AWS execution path wasn't.)*
5. **A throwaway branch `chore-test-dev-rebuild` (identical to dev) is run in AWS via its branch tag — works.** *(A non-default tag takes the register-new-revision path, which always points at the image you asked for. Side effect: the family is now pinned to `chore-test-dev-rebuild-latest`.)*
6. **Promote to prod, trigger prod — works.** *(The prod family hadn't been re-pinned, so it still pointed at `prod-latest`, which now contained the fix.)*
7. **Re-trigger dev with the default tag — "works".** *(False positive: this run actually executed the `chore-test-dev-rebuild-latest` image, which just happened to be identical to dev. The bug was still live.)*

The key diagnostic insight was that "default-tag run fails / identical-code branch-tag run succeeds" is impossible if both runs use the image they claim to — so the default-tag path must not be resolving the image it says it is. Inspecting the active task definition confirmed it:

```bash
aws ecs describe-task-definition --task-definition asf-mission-data-dev \
  --query 'taskDefinition.containerDefinitions[?name==`app`].image'
```

This showed the family pinned to a branch tag, not `dev-latest`.

## How it was resolved

**Root cause in one sentence:** the early-return compared the *requested tag* against the string `{environment}-latest`, when it needed to check which image the active revision *actually* runs.

### Why the obvious fix wasn't enough

The first fix drafted (2026-10-06, never committed) compared the tag pinned on the active revision against the requested tag and re-registered on mismatch. That catches this incident, but a tag-string comparison structurally cannot catch the adjacent case: the revision is pinned to `dev-latest`, but the `dev-latest` *tag has moved* to a newer image since the revision was registered. The strings match; the pin is stale anyway. (Today Fargate happens to re-pull the tag fresh at task start, so that case works by accident — correctness shouldn't depend on pull behavior.)

Both failure modes are the same disease: **deciding what to run via mutable references**. The resolved design (2026-10-12) removes the mutable reference instead of patching the comparison.

### The digest-pinned design

At trigger time, `resolve_task_definition` now:

1. **Resolves the requested tag to its immutable digest** via `ecr.batch_get_image` (`resolve_image_digest` — the same call that previously only validated tag existence; its response always contained the digest, so no new permissions were needed). A missing tag still fails loudly with `Could not find the image tag ...`.
2. **Reuses the active revision only if its pinned digest equals the resolved digest.** Tag-pinned revisions (the state `cdk deploy` leaves behind) can never be digest-verified, so they're always replaced on first run.
3. **Otherwise registers a new revision pinned by digest** — `.../asf-mission-data@sha256:...` — which no later tag mutation can repoint.
4. **Logs both the digest and the requested tag** (stdout and a GitHub Actions annotation), so every run's log answers "which exact build ran?" — the question this bug made unanswerable.

Consequences of the fix:

- A default-tag run on a drifted family **registers a fresh revision pinned to the digest `{environment}-latest` currently points at**, instead of silently running the stale image. The first default-tag run after the fix self-heals any existing drift — no manual remediation needed.
- Repeat runs of an unchanged image reuse the active revision; revisions only accumulate when the image content actually changed (plus one re-registration after each `cdk deploy`, since CDK pins by tag).
- No workflow, CDK, or IAM changes were needed — the GitHub Actions roles already had `ecs:RegisterTaskDefinition` and `ecr:BatchGetImage`.
- New failure mode, by design: requesting a tag that doesn't exist in ECR (e.g. a brand-new environment before any image push) fails loudly instead of silently running whatever was pinned.

Regression tests in `tests/test_trigger_pipeline.py`:

- `test_resolve_task_definition_repoints_family_pinned_to_stale_tag` — the exact bug scenario: family pinned to a branch tag, `dev-latest` requested, assert a new digest-pinned revision is registered.
- `test_resolve_task_definition_repins_when_tag_points_at_new_digest` — the case a tag-string comparison can't catch: revision digest-pinned from an earlier run, tag has moved to a newer image, assert re-registration.
- `test_resolve_task_definition_registers_digest_when_family_pinned_by_tag` — tag-pinned revisions (post-`cdk deploy`) are always replaced by digest-pinned ones.
- `test_resolve_task_definition_reuses_revision_pinned_to_matching_digest` — no redundant revisions when the pinned digest already matches.
- `test_resolve_task_definition_registers_digest_for_feature_tag` — branch-tag runs resolve and pin that branch's digest.

### Deliberately deferred (follow-up issues)

- Moving "re-point what dev runs" into `build-and-push.yaml` as an explicit deploy-on-merge step, so running and deploying are separate actions.
- Immutable per-commit ECR tags (`dev-<sha>`), eliminating moving tags entirely.

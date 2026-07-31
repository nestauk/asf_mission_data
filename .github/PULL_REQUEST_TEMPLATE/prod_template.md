<!-- PR template for promoting from dev to prod -->

---

## Description

<!-- Which pipeline(s) does this promote? What changed? -->

## Type of promotion
- [ ] Existing pipeline - code/data update
- [ ] New pipeline - first promotion to prod

## Instructions for reviewer

<!-- Anything they should pay particular attention to -->

## Checklist

### Pipeline run
- [ ] Manual pipeline run completed successfully on dev after merging to dev (link the run below)
- [ ] Dev S3 output spot-checked; row counts and values look reasonable
- [ ] No unexpected nulls or schema changes in output parquet files

### Image freshness
- [ ] `dev-latest` in ECR was rebuilt from the tip of `dev` that includes this PR's changes
      (check the "Build and push Docker Image to ECR" run in Actions, as promotion only re-tags
      the existing image, it doesn't rebuild)

### Code quality
- [ ] run-tests workflow passed on this PR
- [ ] No hardcoded credentials or environment-specific values

### Breaking changes
- [ ] No breaking schema changes, OR downstream impact documented below
- [ ] No changes to silver/gold dataset column names or types that would break Superset
      <!-- If there are column/type changes, describe them here and provide instructions on changes needed in Superset -->

### After merging
- [ ] Trigger the "Run pipeline in prod" workflow to actually refresh prod data — merging this
      PR only re-tags the image, it does not run the pipeline. Requires approval from at least one of named CODEOWNERS.

## Notes
<!-- Any context the approver should know before merging -->

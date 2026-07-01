## Dev → Prod Promotion Checklist

### Pipeline description
<!-- Which pipeline(s) does this promote? What changed? -->

### Pipeline run
- [ ] Manual pipeline run completed successfully on dev after merging to dev
- [ ] Dev S3 output spot-checked; row counts and values look reasonable
- [ ] No unexpected nulls or schema changes in output parquet files

### Code quality
- [ ] run-tests workflow passed on this PR
- [ ] No hardcoded credentials or environment-specific values

### Breaking changes
- [ ] No breaking schema changes, OR downstream impact documented below
- [ ] No changes to silver/gold dataset column names or types that would break Superset
      <!-- If there are column/type changes, describe them here and provide instructions on changes needed in Superset -->

### Notes
<!-- Any context the approver should know before merging -->

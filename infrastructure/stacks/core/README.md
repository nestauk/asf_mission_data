# Core Stack

## Overview

The Core Stack provides shared infrastructure resources for all ASF Mission Data pipelines. It creates the foundational S3 bucket, ECR repository, and GitHub Actions IAM role that pipeline stacks depend on. This stack must be deployed first before any pipeline stacks.

## Architecture
-- # TO DO: add mermaid diagram

## Resources Created

| Resource | Type | Purpose |
|----------|------|---------|
| Data Bucket | `s3.Bucket` | Pipeline data storage (bronze/silver layers) |
| ECR Repository | `ecr.Repository` | Container images for pipeline Lambdas |
| GitHub Actions Role | `iam.Role` | OIDC role for CI/CD deployments |

### S3 Bucket Features

- **Encryption**: S3-managed encryption (SSE-S3)
- **Public Access**: Blocked completely
- **SSL**: Enforced for all requests
- **Versioning**: Disabled (pipeline data is reproducible)
- **Removal Policy**: RETAIN in prod, DESTROY in dev

### ECR Repository Features

- **Image Scanning**: Enabled on push
- **Lifecycle Rules**: Keep last 10 images per repo
- **Removal Policy**: RETAIN in prod, DESTROY in dev

### GitHub Actions Role Permissions

| Permission Set | Resources | Purpose |
|----------------|-----------|---------|
| ECR | Repository ARN | Push/pull container images |
| S3 | Bucket ARN | Read/write pipeline data |
| CloudFormation | `asf-*` stacks | Deploy pipeline stacks |
| Lambda | `asf-*` functions | Create/update pipeline functions |
| IAM | `asf-*` roles | Create Lambda execution roles |
| Scheduler | `asf-*` schedules | Create EventBridge schedules |
| CloudWatch Logs | `asf-*` log groups | Create log groups for Lambdas |

## Configuration

| Parameter | Source | Description |
|-----------|--------|-------------|
| `environment` | `config.environment` | Environment name (dev/prod) |
| `aws_account_id` | `config.aws_account_id` | AWS account ID for ARNs |
| `aws_region` | `config.aws_region` | AWS region |
| `github_org` | `config.github_org` | GitHub organization for OIDC |
| `github_repo` | `config.github_repo` | GitHub repository for OIDC |
| `ecr_max_image_count` | `config.ecr_max_image_count` | Max images to retain in ECR |

### Environment Values

| Environment | S3 Bucket | ECR Repository | IAM Role |
|-------------|-----------|----------------|----------|
| dev | `asf-mission-data-dev` | `asf-mission-data` | `asf-github-actions-dev` |
| prod | `asf-mission-data-prod` | `asf-mission-data` | `asf-github-actions-prod` |

## Dependencies

None - this is the foundation stack that pipeline stacks depend on.

## Exports

The stack exports these values via CloudFormation outputs:

| Output | Export Name | Description |
|--------|-------------|-------------|
| `DataBucketName` | `asf-data-bucket-{env}` | S3 bucket name |
| `DataBucketArn` | `asf-data-bucket-arn-{env}` | S3 bucket ARN |
| `ECRRepositoryUri` | `asf-ecr-uri-{env}` | ECR repository URI |
| `ECRRepositoryArn` | `asf-ecr-arn-{env}` | ECR repository ARN |
| `GitHubActionsRoleArn` | `asf-github-role-arn-{env}` | IAM role ARN |

## Deployment

```bash
# From repository root
cd infrastructure

# Deploy to dev
cdk deploy --context env=dev

# Deploy to prod
cdk deploy --context env=prod

# Preview changes
cdk diff --context env=dev
```

## Accessing Resources

### S3 Bucket

```bash
# List bucket contents
aws s3 ls s3://asf-mission-data-dev/

# Bucket structure
# bronze/           - Raw ingested data
# silver/           - Cleaned/transformed data
```

### ECR Repository

```bash
# List images
aws ecr describe-images --repository-name asf-mission-data

# Login to ECR
aws ecr get-login-password --region eu-west-2 | docker login --username AWS --password-stdin ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com

# Push an image
docker push ACCOUNT_ID.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:latest
```

### IAM Role (for debugging)

```bash
# View role trust policy
aws iam get-role --role-name asf-github-actions-dev --query 'Role.AssumeRolePolicyDocument'

# List attached policies
aws iam list-role-policies --role-name asf-github-actions-dev
```

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| GitHub Actions can't assume role | OIDC subject mismatch | Verify repo name matches exactly in trust policy |
| ECR push fails with 403 | Missing ECR auth | Run `aws ecr get-login-password` before push |
| S3 access denied | IAM policy issue | Check role has `s3:*` on bucket ARN |
| Stack deletion fails | Bucket not empty | Empty bucket first or set `auto_delete_objects=True` |
| CDK deploy fails | Missing permissions | Ensure deployer has CloudFormation + IAM permissions |

### OIDC Authentication Fails

If GitHub Actions can't authenticate:

1. Verify the OIDC provider exists in AWS IAM
2. Check the trust policy subject claim:
   ```
   repo:nestauk/asf_mission_data:*
   ```
3. Ensure workflow has `id-token: write` permission
4. Check the audience is `sts.amazonaws.com`

## Cost Estimate

| Resource | Monthly Cost | Notes |
|----------|--------------|-------|
| S3 Storage | ~$0.23 | 10 GB at $0.023/GB |
| S3 Requests | ~$0.07 | 10K PUT, 50K GET |
| ECR Storage | ~$0.50 | 5 GB (10 images) at $0.10/GB |
| IAM Role | $0.00 | Free |
| **Total** | **~$0.80/month** | Core stack only |

See `infrastructure/README.md` for full cost breakdown including pipeline resources.

## Owner

TBD - assign a team member as point of contact for this stack.

---

## Code Reference

- Stack implementation: `stacks/core/core_stack.py`
- Configuration: `config/environments.py` → `EnvironmentConfig`
- CDK entry point: `app.py`

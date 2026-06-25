# Infrastructure

AWS CDK infrastructure for the ASF Mission Data pipelines.

## Overview

This infrastructure supports serverless ETL pipelines that run on AWS Lambda with container images stored in ECR and data stored in S3.

### Architecture

```text
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  GitHub Actions │────▶│    ECR Repo     │────▶│     Lambda      │
│   (CI/CD)       │     │  (Container     │     │   (Pipeline     │
│                 │     │   Images)       │     │    Execution)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                                               │
        │                                               ▼
        │                                       ┌─────────────────┐
        └──────────────────────────────────────▶│    S3 Bucket    │
                                                │  (Bronze/Silver │
                                                │     Data)       │
                                                └─────────────────┘
```

## Stacks

### CoreStack (`asf-core-{env}`)

Shared infrastructure deployed once per environment. Creates:

| Resource | Purpose |
|----------|---------|
| **S3 Bucket** | Pipeline data storage (bronze/silver layers) |
| **ECR Repository** | Container images for pipeline Lambdas |
| **IAM Role** | GitHub Actions OIDC role for CI/CD deployments |

The GitHub Actions role has permissions to:
- Push/pull images to ECR
- Read/write to the S3 data bucket
- Deploy CloudFormation stacks (for pipeline stacks)
- Create/manage Lambda functions and execution roles
- Create/manage EventBridge schedules
- Create/manage CloudWatch log groups

## Environments

| Environment | AWS Account | Region | Stack Name |
|-------------|-------------|--------|------------|
| dev | 195787726158 | eu-west-2 | `asf-core-dev` |
| prod | 195787726158 | eu-west-2 | `asf-core-prod` |

### Environment differences

| Setting | Dev | Prod |
|---------|-----|------|
| Removal policy | DESTROY | RETAIN |
| Auto-delete S3 objects | Yes | No |
| Auto-delete ECR images | Yes | No |

## Cost Estimate

Estimated monthly costs for the CoreStack resources (eu-west-2 pricing, March 2026).

### CoreStack resources (always running)

| Resource | Unit | Price | Estimated Usage | Monthly Cost |
|----------|------|-------|-----------------|--------------|
| **S3 Storage** | GB/month | $0.023 | 10 GB | $0.23 |
| **S3 Requests** | 1K PUT/GET | $0.005/$0.0004 | 10K PUT, 50K GET | $0.07 |
| **ECR Storage** | GB/month | $0.10 | 5 GB (10 images) | $0.50 |
| **IAM Role** | - | Free | - | $0.00 |

**CoreStack total: ~$0.80/month**

### Pipeline resources (per pipeline, when deployed)

| Resource | Unit | Price | Estimated Usage | Monthly Cost |
|----------|------|-------|-----------------|--------------|
| **Lambda** | 1M requests | $0.20 | 1K invocations | $0.0002 |
| **Lambda Compute** | GB-second | $0.0000167 | 1K x 30s x 1GB | $0.50 |
| **CloudWatch Logs** | GB ingested | $0.57 | 0.5 GB | $0.29 |
| **CloudWatch Logs Storage** | GB/month | $0.03 | 1 GB | $0.03 |
| **EventBridge Scheduler** | 1M invocations | $1.00 | 720 (hourly) | $0.0007 |

**Per pipeline total: ~$0.82/month** (assuming hourly schedule, 30s avg runtime)

### Example scenarios

| Scenario | Pipelines | Schedule | Est. Monthly Cost |
|----------|-----------|----------|-------------------|
| Dev (minimal) | 2 | Daily | ~$1.50 |
| Dev (active) | 5 | Hourly | ~$5.00 |
| Prod | 10 | Mixed | ~$10-20 |

### Cost optimization notes

- ECR lifecycle policy limits images to 10 per repo (saves ~$0.10/image/month)
- Lambda costs scale with execution time; optimize pipeline code for faster runs
- CloudWatch Logs retention can be reduced from default (never expires) to save costs

## Prerequisites

1. **AWS CLI** configured with appropriate credentials
2. **Node.js** (for CDK CLI)
3. **Python 3.12+** with project dependencies

```bash
# Install CDK CLI globally
npm install -g aws-cdk

# Install Python dependencies
uv sync --extra infrastructure
```

## Usage

All CDK commands should be run from the `infrastructure/` directory (where `cdk.json` lives).

### Deploy

```bash
# Deploy to dev
cdk deploy --context env=dev

# Deploy to prod
cdk deploy --context env=prod
```

### Preview changes

```bash
# Show what would change
cdk diff --context env=dev
```

### Synthesize CloudFormation

```bash
# Generate CloudFormation template without deploying
cdk synth --context env=dev
```

### List stacks

```bash
cdk list --context env=dev
```

## Configuration

Environment configurations are in `config/`:

- `config/environments.py` - `EnvironmentConfig` dataclass with shared logic
- `config/dev.py` - Dev environment values
- `config/prod.py` - Prod environment values

### Adding a new environment

1. Create `config/{env}.py` with an `EnvironmentConfig` instance
2. Add it to the `ENVIRONMENTS` dict in `app.py`
3. Deploy: `cdk deploy --context env={env}`

## Project structure

```text
infrastructure/
├── app.py                  # CDK entry point
├── cdk.json                # CDK configuration
├── config/
│   ├── environments.py     # EnvironmentConfig dataclass
│   ├── dev.py              # Dev environment config
│   └── prod.py             # Prod environment config
└── stacks/
    └── core/               # Core stack
        ├── core_stack.py   # Stack implementation
        └── README.md       # Stack documentation
```

## CI/CD Integration

GitHub Actions authenticates to AWS using OIDC (no long-lived credentials). The trust policy restricts access to:

- Repository: `nestauk/asf_mission_data`
- Any branch/workflow (configured via `repo:org/repo:*` subject claim)

### Required GitHub secrets/variables

| Type | Name | Description |
|------|------|-------------|
| Secret | `AWS_ACCOUNT_ID` | AWS account ID |
| Secret | `MISSION_DATA_BUCKET` | S3 bucket name |
| Variable | `AWS_REGION` | AWS region (eu-west-2) |
| Variable | `ENV_NAME` | Environment name (dev/prod) |

## Troubleshooting

### "Unable to assume role" in GitHub Actions

1. Verify the OIDC provider exists in the AWS account
2. Check the IAM role trust policy matches the repository name exactly
3. Ensure the workflow has `id-token: write` permission

### CDK bootstrap required

If you see bootstrap errors, the AWS account needs CDK bootstrapping:

```bash
cdk bootstrap aws://ACCOUNT_ID/eu-west-2
```

Note: This only needs to be done once per account/region.

### Stack drift

If resources were modified outside CDK:

```bash
# Check for drift
aws cloudformation detect-stack-drift --stack-name asf-core-dev
aws cloudformation describe-stack-resource-drifts --stack-name asf-core-dev
```

MOVED OUT FROM README

## Infrastructure

Infrastructure is managed with [AWS CDK](https://aws.amazon.com/cdk/) (Python).

### Core resources (deployed)

| Resource | Dev | Prod |
|----------|-----|------|
| S3 bucket | `asf-mission-data-dev` | `asf-mission-data-prod` |
| ECR repository | `asf-mission-data` | `asf-mission-data` |
| GitHub Actions IAM role | `asf-github-actions-dev` | `asf-github-actions-prod` |

### Deploying infrastructure

```bash
# Install CDK dependencies
uv sync --extra infrastructure
npm install -g aws-cdk

# Deploy to dev
cd infrastructure
cdk deploy --context env=dev

# Preview changes
cdk diff --context env=dev
```

See [infrastructure/README.md](infrastructure/README.md) for full documentation.

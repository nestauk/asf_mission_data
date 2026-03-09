#!/usr/bin/env python3
"""
ASF Mission Data - Infrastructure

CDK entry point for ASF Policy Dashboard pipeline infrastructure.

Examples:
    # Deploy core stack to dev
    cdk deploy --context env=dev

    # Diff before deploying
    cdk diff --context env=dev

    # Deploy to production
    cdk deploy --context env=prod
"""

import os

import aws_cdk as cdk
from config.dev import DEV_CONFIG
from config.prod import PROD_CONFIG
from stacks.core import CoreStack

ENVIRONMENTS = {
    "dev": DEV_CONFIG,
    "prod": PROD_CONFIG,
}


def create_stacks(app: cdk.App, env_name: str) -> None:
    """Create all stacks for a specific environment."""
    config = ENVIRONMENTS[env_name]

    aws_env = cdk.Environment(
        account=config.aws_account_id,
        region=config.aws_region,
    )

    # =================================================================
    # Core Stack (S3, ECR, GitHub Actions IAM)
    # =================================================================
    core = CoreStack(
        app,
        f"asf-core-{env_name}",
        config=config,
        env=aws_env,
        description=f"ASF Policy Dashboard - Core Infrastructure ({env_name})",
    )

    # Apply tags to all resources in the stack
    for key, value in config.tags.items():
        cdk.Tags.of(core).add(key, value)


# =================================================================
# Entry Point
# =================================================================
app = cdk.App()

# Determine environment: CDK context > env var > default (dev)
target_env = app.node.try_get_context("env") or os.getenv("DEPLOY_ENV", "dev")

if target_env not in ENVIRONMENTS:
    raise ValueError(
        f"Unknown environment: {target_env}. Valid environments: {', '.join(ENVIRONMENTS.keys())}"
    )

create_stacks(app, target_env)

app.synth()

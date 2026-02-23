"""
Core Stack - Shared infrastructure for ASF Policy Dashboard pipelines.

Creates:
- S3 bucket for pipeline data (bronze/silver layers)
- ECR repository for pipeline container images
- IAM role for GitHub Actions deployments (OIDC)

This stack is deployed once per environment. Individual pipeline
are deployed via the GitHub Actions CI/CD,
using the IAM role created here
"""

import aws_cdk as cdk
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_iam as iam
from aws_cdk import aws_s3 as s3
from config.environments import EnvironmentConfig
from constructs import Construct


class CoreStack(Stack):
    """Core infrastructure for ASF Policy Dashboard pipelines"""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: EnvironmentConfig,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config

        # =================================================================
        # S3 Bucket
        # =================================================================
        # RETAIN in prod (protect data), DESTROY in dev (clean teardown)
        removal_policy = (
            RemovalPolicy.RETAIN if config.environment == "prod" else RemovalPolicy.DESTROY
        )

        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name=config.data_bucket_name,
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=removal_policy,
            auto_delete_objects=config.environment
            != "prod",  # Leave objects in prod for safety even if we tear down the stack
        )

        # =================================================================
        # ECR Repository for Pipeline Images
        # =================================================================
        self.ecr_repo = ecr.Repository(
            self,
            "PipelineRepo",
            repository_name=config.ecr_repo_name,
            image_scan_on_push=True,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    description="Keep last 10 images",
                    max_image_count=10,
                )
            ],
            removal_policy=removal_policy,
            empty_on_delete=config.environment != "prod",  # Don't delete images in prod for safety
        )

        # =================================================================
        # GitHub Actions OIDC Role
        # =================================================================
        # References the pre-existing OIDC in the AWS account for GitHub Actions
        github_provider_arn = (
            f"arn:aws:iam::{config.aws_account_id}"
            f":oidc-provider/token.actions.githubusercontent.com"
        )

        self.github_actions_role = iam.Role(
            self,
            "GitHubActionsRole",
            role_name=config.github_actions_role_name,
            assumed_by=iam.FederatedPrincipal(
                github_provider_arn,
                conditions={
                    "StringEquals": {
                        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
                    },
                    "StringLike": {
                        "token.actions.githubusercontent.com:sub": config.github_oidc_subject,
                    },
                },
                assume_role_action="sts:AssumeRoleWithWebIdentity",
            ),
            max_session_duration=cdk.Duration.hours(1),
        )

        # -----------------------------------------------------------------
        # ECR Permissions
        # -----------------------------------------------------------------
        self.ecr_repo.grant_pull_push(self.github_actions_role)

        # ECR auth token (needed for docker login)
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRAuth",
                actions=["ecr:GetAuthorizationToken"],
                resources=["*"],
            )
        )

        # -----------------------------------------------------------------
        # S3 Permissions
        # -----------------------------------------------------------------
        self.data_bucket.grant_read_write(self.github_actions_role)

        # -----------------------------------------------------------------
        # CloudFormation Permissions (for deploying pipeline stacks)
        # -----------------------------------------------------------------
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudFormation",
                actions=[
                    "cloudformation:CreateStack",
                    "cloudformation:UpdateStack",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeStacks",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:GetTemplate",
                    "cloudformation:ValidateTemplate",
                ],
                resources=[
                    f"arn:aws:cloudformation:{config.aws_region}:{config.aws_account_id}:stack/{config.project_prefix}-*/*"
                ],
            )
        )

        # -----------------------------------------------------------------
        # Lambda Permissions
        # -----------------------------------------------------------------
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="Lambda",
                actions=[
                    "lambda:CreateFunction",
                    "lambda:UpdateFunctionCode",
                    "lambda:UpdateFunctionConfiguration",
                    "lambda:GetFunction",
                    "lambda:DeleteFunction",
                    "lambda:AddPermission",
                    "lambda:RemovePermission",
                    "lambda:InvokeFunction",
                    "lambda:TagResource",
                    "lambda:ListTags",
                    "lambda:UntagResource",
                ],
                resources=[
                    f"arn:aws:lambda:{config.aws_region}:{config.aws_account_id}:function:{config.project_prefix}-*"
                ],
            )
        )

        # -----------------------------------------------------------------
        # IAM Permissions (for creating Lambda execution roles)
        # -----------------------------------------------------------------
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="IAMRoles",
                actions=[
                    "iam:CreateRole",
                    "iam:DeleteRole",
                    "iam:GetRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                ],
                resources=[f"arn:aws:iam::{config.aws_account_id}:role/{config.project_prefix}-*"],
            )
        )

        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="IAMPassRole",
                actions=["iam:PassRole"],
                resources=[f"arn:aws:iam::{config.aws_account_id}:role/{config.project_prefix}-*"],
                conditions={
                    "StringEquals": {
                        "iam:PassedToService": [
                            "lambda.amazonaws.com",
                            "scheduler.amazonaws.com",
                        ]
                    }
                },
            )
        )

        # -----------------------------------------------------------------
        # EventBridge Scheduler Permissions
        # -----------------------------------------------------------------
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="Scheduler",
                actions=[
                    "scheduler:CreateSchedule",
                    "scheduler:UpdateSchedule",
                    "scheduler:DeleteSchedule",
                    "scheduler:GetSchedule",
                    "scheduler:TagResource",
                    "scheduler:UntagResource",
                ],
                resources=[
                    f"arn:aws:scheduler:{config.aws_region}:{config.aws_account_id}:schedule/default/{config.project_prefix}-*"
                ],
            )
        )

        # -----------------------------------------------------------------
        # CloudWatch Logs Permissions
        # -----------------------------------------------------------------
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudWatchLogs",
                actions=[
                    "logs:CreateLogGroup",
                    "logs:DeleteLogGroup",
                    "logs:PutRetentionPolicy",
                    "logs:TagResource",
                    "logs:UntagResource",
                    "logs:DescribeLogGroups",
                ],
                resources=[
                    f"arn:aws:logs:{config.aws_region}:{config.aws_account_id}:log-group:/aws/lambda/{config.project_prefix}-*"
                ],
            )
        )

        # =================================================================
        # Outputs
        # =================================================================
        CfnOutput(
            self,
            "DataBucketName",
            value=self.data_bucket.bucket_name,
            description="S3 bucket for pipeline data",
            export_name=f"{config.project_prefix}-data-bucket-{config.environment}",
        )

        CfnOutput(
            self,
            "DataBucketArn",
            value=self.data_bucket.bucket_arn,
            description="S3 bucket ARN",
            export_name=f"{config.project_prefix}-data-bucket-arn-{config.environment}",
        )

        CfnOutput(
            self,
            "ECRRepositoryUri",
            value=self.ecr_repo.repository_uri,
            description="ECR repository URI for pipeline images",
            export_name=f"{config.project_prefix}-ecr-uri-{config.environment}",
        )

        CfnOutput(
            self,
            "ECRRepositoryArn",
            value=self.ecr_repo.repository_arn,
            description="ECR repository ARN",
            export_name=f"{config.project_prefix}-ecr-arn-{config.environment}",
        )

        CfnOutput(
            self,
            "GitHubActionsRoleArn",
            value=self.github_actions_role.role_arn,
            description="IAM role ARN for GitHub Actions",
            export_name=f"{config.project_prefix}-github-role-arn-{config.environment}",
        )

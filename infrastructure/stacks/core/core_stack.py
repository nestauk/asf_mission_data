"""
Core Stack - All infrastructure for ASF Policy Dashboard pipelines.

Creates:
- S3 bucket for pipeline data (bronze/silver layers)
- ECR repository for pipeline container images
- IAM role for GitHub Actions deployments (OIDC)
- ECS cluster with Fargate/Fargate Spot capacity
- ECS task definition with container pointing at ECR image
- IAM roles for task execution, task runtime, and EventBridge scheduling
- Security group for outbound-only access
- CloudWatch log group

This stack is deployed once per environment.
"""

import aws_cdk as cdk
from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
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
        is_prod = config.environment == "prod"

        # RETAIN in prod (protect data), DESTROY in dev (clean teardown)
        removal_policy = RemovalPolicy.RETAIN if is_prod else RemovalPolicy.DESTROY

        # =================================================================
        # S3 Bucket
        # =================================================================

        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            bucket_name=config.data_bucket_name,
            versioned=False,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=removal_policy,
            auto_delete_objects=config.environment != "prod",  # Leave objects in prod for safety even if we tear down the stack
        )

        # =================================================================
        # ECR Repository for Pipeline Images
        # =================================================================
        # Share one ECR repository across environments so app stacks can
        # consistently reference `asf-mission-data`
        if config.environment == "dev":
            self.ecr_repo = ecr.Repository(
                self,
                "PipelineRepo",
                repository_name=config.ecr_repo_name,
                image_scan_on_push=True,
                lifecycle_rules=[
                    ecr.LifecycleRule(
                        description=f"Keep last {config.ecr_max_image_count} images",
                        max_image_count=config.ecr_max_image_count,
                    )
                ],
                removal_policy=removal_policy,
                empty_on_delete=config.environment != "prod",  # Don't delete images in prod for safety
            )

            # This repository is shared across environments, so its tag
            # reflects that rather than inheriting the stack-wide env tag.
            cdk.Tags.of(self.ecr_repo).add("Environment", "shared", priority=300)
        else:
            self.ecr_repo = ecr.Repository.from_repository_name(
                self,
                "PipelineRepo",
                config.ecr_repo_name,
            )

        # =================================================================
        # GitHub Actions OIDC Role
        # =================================================================
        # References the pre-existing OIDC in the AWS account for GitHub Actions
        github_provider_arn = f"arn:aws:iam::{config.aws_account_id}:oidc-provider/token.actions.githubusercontent.com"

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

        # ECR describe (needed for CI/CD checks)
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECRDescribe",
                actions=["ecr:DescribeRepositories"],
                resources=[self.ecr_repo.repository_arn],
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
                    "cloudformation:Create*",
                    "cloudformation:Describe*",
                    "cloudformation:Cancel*",
                    "cloudformation:List*",
                    "cloudformation:Get*",
                    "cloudformation:Update*",
                    "cloudformation:Delete*",
                    "cloudformation:ExecuteChangeSet",
                ],
                resources=[f"arn:aws:cloudformation:{config.aws_region}:{config.aws_account_id}:stack/{config.project_prefix}-*/*"],
            )
        )

        # Can't be given a resource-level permission FYI
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="CloudformationValidation",
                actions=["cloudformation:ValidateTemplate"],
                resources=["*"],
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
                resources=[f"arn:aws:lambda:{config.aws_region}:{config.aws_account_id}:function:{config.project_prefix}-*"],
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
                    "iam:PutRolePolicy",
                    "iam:DeleteRolePolicy",
                    "iam:GetRolePolicy",
                    "iam:TagRole",
                    "iam:UntagRole",
                    "iam:AttachRolePolicy",
                    "iam:DetachRolePolicy",
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
                            "ecs-tasks.amazonaws.com",
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
                    f"arn:aws:scheduler:{config.aws_region}:{config.aws_account_id}:schedule/default/{config.project_prefix}-*"  # noqa: E501
                ],
            )
        )
        # -----------------------------------------------------------------
        # ECS Permissions (for triggering pipeline tasks)
        # -----------------------------------------------------------------

        # Task definition IAM policies don't support resource-level
        # permissions so we *have to* allow on all resources
        # this is sneaky because you could add an arn under resource
        # and it would just fail silently when the role tries to use it
        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECSTaskDefinition",
                effect=iam.Effect.ALLOW,
                actions=[
                    "ecs:DescribeTaskDefinition",
                    "ecs:RegisterTaskDefinition",
                    "ecs:ListTaskDefinitions",
                ],
                resources=["*"],
            )
        )

        self.github_actions_role.add_to_policy(
            iam.PolicyStatement(
                sid="ECSRunTask",
                actions=["ecs:RunTask"],
                conditions={
                    "ArnEquals": {
                        "ecs:cluster": f"arn:aws:ecs:{config.aws_region}:{config.aws_account_id}:cluster/{config.ecs_cluster_name}"  # noqa: E501
                    }
                },
                resources=[f"arn:aws:ecs:{config.aws_region}:{config.aws_account_id}:task-definition/{config.project_prefix}-*"],
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
                resources=[f"arn:aws:logs:{config.aws_region}:{config.aws_account_id}:log-group:/aws/lambda/{config.project_prefix}-*"],
            )
        )

        # =================================================================
        # Networking
        # =================================================================
        vpc = ec2.Vpc.from_lookup(self, "Vpc", vpc_id=config.vpc_id)

        self.security_group = ec2.SecurityGroup(
            self,
            "TaskSecurityGroup",
            vpc=vpc,
            description=f"Security group for ASF pipeline tasks ({config.environment})",
            security_group_name=f"asf-mission-data-{config.environment}-tasks",
            allow_all_outbound=True,  # Tasks make outbound HTTP requests (scraping, S3)
        )

        # =================================================================
        # Logging
        # =================================================================
        self.log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/ecs/asf-mission-data-{config.environment}",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        # =================================================================
        # IAM - Task Execution Role
        # =================================================================
        # Assumed by the ECS agent to pull images from ECR and write logs
        self.task_execution_role = iam.Role(
            self,
            "TaskExecutionRole",
            role_name=f"asf-mission-data-{config.environment}-task-execution-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")],
        )

        # =================================================================
        # IAM - Task Role
        # =================================================================
        # Assumed by the container itself — what pipeline code uses when
        # it calls boto3 to read/write S3
        self.task_role = iam.Role(
            self,
            "TaskRole",
            role_name=f"asf-mission-data-{config.environment}-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # S3 read/write/delete for pipeline data (bronze/silver data + heartbeats)
        self.data_bucket.grant_read_write(self.task_role)

        # =================================================================
        # IAM - Scheduler Role
        # =================================================================
        # EventBridge Scheduler needs to call ecs:RunTask and pass the
        # task execution + task roles to the task it creates
        self.scheduler_role = iam.Role(
            self,
            "SchedulerRole",
            role_name=f"asf-mission-data-{config.environment}-scheduler-role",
            assumed_by=iam.ServicePrincipal("scheduler.amazonaws.com"),
        )

        self.scheduler_role.add_to_policy(
            iam.PolicyStatement(
                actions=["ecs:RunTask"],
                resources=[f"arn:aws:ecs:{config.aws_region}:{config.aws_account_id}:task-definition/asf-mission-data-{config.environment}:*"],
            )
        )

        self.scheduler_role.add_to_policy(
            iam.PolicyStatement(
                actions=["iam:PassRole"],
                resources=[
                    self.task_execution_role.role_arn,
                    self.task_role.role_arn,
                ],
            )
        )

        # =================================================================
        # ECS Cluster
        # =================================================================
        self.cluster = ecs.Cluster(
            self,
            "ECSCluster",
            cluster_name=config.ecs_cluster_name,
            vpc=vpc,
            # Container Insights = detailed CPU/memory monitoring. Costs extra.
            # Not worth it for batch tasks that run for 2 seconds.
            container_insights_v2=ecs.ContainerInsights.DISABLED,
            enable_fargate_capacity_providers=True,
        )

        # Default to standard Fargate for predictable launches.
        # Callers can still override with FARGATE_SPOT explicitly.
        self.cluster.add_default_capacity_provider_strategy(
            [
                ecs.CapacityProviderStrategy(
                    capacity_provider="FARGATE",
                    weight=1,
                )
            ]
        )

        # =================================================================
        # ECS Task Definition
        # =================================================================
        # One shared task definition. The container image contains all pipelines.
        # Which pipeline runs is controlled by command override
        # passed at runtime (e.g. ["energy_price_cap", "--stage", "all"])
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=f"asf-mission-data-{config.environment}",
            cpu=256,
            memory_limit_mib=512,
            execution_role=self.task_execution_role,
            task_role=self.task_role,
            runtime_platform=ecs.RuntimePlatform(
                # Must match with the --platform flag in the Docker build workflow
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
                cpu_architecture=ecs.CpuArchitecture.X86_64,
            ),
        )

        self.task_definition.add_container(
            "app",
            image=ecs.ContainerImage.from_ecr_repository(self.ecr_repo, tag=f"{config.environment}-latest"),
            environment={
                "DATA_MODE": "PROD" if is_prod else "DEV",
                "DATA_ROOT": f"s3://asf-mission-data-{config.environment}",
                "ASF_ENVIRONMENT": config.environment,
            },
            # Each task run gets a unique stream e.g. "pipeline/<task-id>"
            logging=ecs.LogDrivers.aws_logs(
                log_group=self.log_group,
                stream_prefix="pipeline",
            ),
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

        CfnOutput(
            self,
            "ClusterArn",
            value=self.cluster.cluster_arn,
            export_name=f"asf-{config.environment}-cluster-arn",
        )

        CfnOutput(
            self,
            "TaskDefinitionArn",
            value=self.task_definition.task_definition_arn,
            export_name=f"asf-{config.environment}-task-definition-arn",
        )

        CfnOutput(
            self,
            "SecurityGroupId",
            value=self.security_group.security_group_id,
            export_name=f"asf-{config.environment}-security-group-id",
        )

        CfnOutput(
            self,
            "SubnetIds",
            value=",".join(config.subnet_ids),
            export_name=f"asf-{config.environment}-subnet-ids",
        )

        CfnOutput(
            self,
            "SchedulerRoleArn",
            value=self.scheduler_role.role_arn,
            export_name=f"asf-{config.environment}-scheduler-role-arn",
        )

"""
ECS Stack - Fargate compute infrastructure for ASF pipeline tasks.

Creates:
- ECS cluster with Fargate/Fargate Spot capacity
- Task definition with container pointing at ECR image
- IAM roles for task execution, task runtime, and EventBridge scheduling
- Security group for outbound-only access
- CloudWatch log group

This stack is deployed once per environment. The core stack must be
deployed first (provides S3 bucket and ECR repository).
"""

import aws_cdk as cdk
from aws_cdk import CfnOutput, Stack
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_iam as iam
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from config.environments import EnvironmentConfig
from constructs import Construct


class EcsStack(Stack):
    """Fargate compute infrastructure for ASF pipeline tasks."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        config: EnvironmentConfig,
        data_bucket: s3.IBucket,
        ecr_repo: ecr.IRepository,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.config = config
        is_prod = config.environment == "prod"

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
        # AWS managed policy assumed by the ECS agent to pull images from ECR and write logs  # noqa: E501
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
        # Assumed by the container itself — what pipeline code uses when it calls boto3 to read/write S3
        self.task_role = iam.Role(
            self,
            "TaskRole",
            role_name=f"asf-mission-data-{config.environment}-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        # S3 read/write/delete for pipeline data (bronze/silver data + heartbeats)
        # Delete is for the overwrite latest pattern where we
        # list and delete before writing new files
        data_bucket.grant_read_write(self.task_role)

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
        # Compute
        # =================================================================
        # =================================================================
        # ECS Cluster
        # =================================================================

        self.cluster = ecs.Cluster(
            self,
            "ECSCluster",
            cluster_name=config.ecs_cluster_name,
            # Container Insights = detailed CPU/memory monitoring. Costs extra.
            # Not worth it for batch tasks that run for 2 seconds.
            # Decided that CloudWatch Logs is enough.
            container_insights_v2=ecs.ContainerInsights.DISABLED,
            enable_fargate_capacity_providers=True,
            default_cloud_map_namespace=None,
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
        # One shared task definition. The container image contains all pipelines
        # Which pipeline runs is controlled by command override
        # passed at runtime (e.g. ["energy_price_cap", "--stage", "all"])
        self.task_definition = ecs.FargateTaskDefinition(
            self,
            "TaskDefinition",
            family=f"asf-mission-data-{config.environment}",
            cpu=config.task_cpu,
            memory_limit_mib=config.task_memory,
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
            image=ecs.ContainerImage.from_ecr_repository(ecr_repo, tag=f"{config.environment}-latest"),
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

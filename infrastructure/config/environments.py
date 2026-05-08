"""
Environment configuration for ASF Policy Dashboard infrastructure.

See the nestauk/de_cdp repo for more information about nesta cdk design
"""

from dataclasses import dataclass, field


@dataclass
class EnvironmentConfig:
    """Configuration for a specific environment (dev/prod)"""

    # Environment identifier
    environment: str  # "dev" or "prod" ("test" for integration tests)

    # AWS
    aws_account_id: str
    aws_region: str

    # GitHub repository (for OIDC trust policy)
    github_org: str = "nestauk"
    github_repo: str = "asf_mission_data"

    # Project Team
    project_prefix: str = "asf"

    # Tagging (applied to all resources)
    tags: dict = field(default_factory=dict)

    ecr_max_image_count: int = 10  # Max number of images to keep in ECR repositories

    # Networking — default VPC and subnets in eu-west-2 for the data science account
    # If we ever move to a multi-account setup where prod uses a different VPC, override them in prod.py
    vpc_id: str = "vpc-0f78e906ab4c3cbe1"
    subnet_ids: list[str] = field(
        default_factory=lambda: [
            "subnet-5cc6e511",
            "subnet-eb6fcb82",
            "subnet-1de6f466",
        ]
    )

    # ECS task sizing
    task_cpu: int = 256  # CPU units (256 = 0.25 vCPU)
    task_memory: int = 512  # Memory in MB
    log_retention_days: int = 30

    # =================================================================
    # Derived properties
    # =================================================================

    @property
    def data_bucket_name(self) -> str:
        """S3 bucket for pipeline data"""
        return f"{self.project_prefix}-mission-data-{self.environment}"

    @property
    def ecr_repo_name(self) -> str:
        """ECR repository for pipeline container images"""
        return "asf-mission-data"

    @property
    def github_actions_role_name(self) -> str:
        """IAM role name for GitHub Actions deployments"""
        return f"{self.project_prefix}-github-actions-{self.environment}"

    @property
    def ecs_cluster_name(self) -> str:
        """ECS cluster name for pipeline tasks"""
        return f"{self.project_prefix}-mission-data-{self.environment}"

    @property
    def github_oidc_subject(self) -> str:
        """OIDC subject claim pattern for GitHub Actions"""
        return f"repo:{self.github_org}/{self.github_repo}:*"

"""
Environment configuration for ASF Policy Dashboard infrastructure.

See the nestauk/de_cdp repo for more information about nesta cdk design
"""

from dataclasses import dataclass, field


@dataclass
class EnvironmentConfig:
    """Configuration for a specific environment (dev/prod)"""

    # Environment identifier
    environment: str  # "dev" or "prod"

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
        return f"{self.project_prefix}-pipelines-{self.environment}"

    @property
    def github_actions_role_name(self) -> str:
        """IAM role name for GitHub Actions deployments"""
        return f"{self.project_prefix}-github-actions-{self.environment}"

    @property
    def github_oidc_subject(self) -> str:
        """OIDC subject claim pattern for GitHub Actions"""
        return f"repo:{self.github_org}/{self.github_repo}:*"

    def resource_name(self, name: str) -> str:
        """Generate a consistent resource name based on project prefix and environment"""
        return f"{self.project_prefix}-{name}-{self.environment}"

    def stack_resource_arn(self, service: str, resource_type: str) -> str:
        """Generate ARN pattern for resources in this project"""
        return f"arn:aws:{service}:{self.aws_region}:{self.aws_account_id}:{resource_type}/{self.project_prefix}-*"  # noqa: E501

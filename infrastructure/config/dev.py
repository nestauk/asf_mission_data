"""Development environment configuration."""

from config.environments import EnvironmentConfig

DEV_CONFIG = EnvironmentConfig(
    environment="dev",
    # AWS data science account
    aws_account_id="195787726158",
    aws_region="eu-west-2",
    # GitHub
    github_org="nestauk",
    github_repo="asf_mission_data",
    # Tags
    tags={
        "Environment": "dev",
        "Project": "asf-policy-dashboard",
        "Team": "asf",
        "ManagedBy": "cdk",
    },
    # ECR Max Num Images
    ecr_max_image_count=10,
)

"""Production environment configuration."""

from config.environments import EnvironmentConfig

PROD_CONFIG = EnvironmentConfig(
    environment="prod",
    # AWS Data Science account
    aws_account_id="195787726158",
    aws_region="eu-west-2",
    # GitHub
    github_org="nestauk",
    github_repo="asf_mission_data",
    # Tags
    tags={
        "Environment": "prod",
        "Project": "asf-policy-dashboard",
        "Team": "asf",
        "ManagedBy": "cdk",
    },
)

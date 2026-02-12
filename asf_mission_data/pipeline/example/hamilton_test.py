import pandas as pd
import dataclasses


def spend_zero_mean(spend: pd.Series, spend_mean: float) -> pd.Series:
    """Shows function that takes a scalar. In this case to zero mean spend."""
    return spend - spend_mean


def spend_std_dev(spend: pd.Series) -> float:
    """Function that computes the standard deviation of the spend column."""
    return spend.std()


def spend_zero_mean_unit_variance(spend_zero_mean: pd.Series, spend_std_dev: float) -> pd.Series:
    """Function showing one way to make spend have zero mean and unit variance."""
    return spend_zero_mean / spend_std_dev


from hamilton.io.materialization import DataSaver
from hamilton import registry
import boto3


@dataclasses.dataclass
class S3BronzeSaver(DataSaver):
    dataset_name: str
    target_url: str

    @classmethod
    def applicable_types(cls):
        # This saver handles raw bytes downloaded from the web
        return [bytes]

    @classmethod
    def name(cls):
        return "s3_bronze"

    def save_data(self, data: bytes) -> dict:
        # 1. Your logic from `save_to_s3_bronze` goes here:
        # - Check S3 for existing file/size
        # - Prompt user (or use a flag)
        # - s3_client.put_object(data)

        # 2. Your decorator logic goes here:
        # - Create TOML metadata
        # - s3_client.put_object(toml)

        # Return metadata about where it was saved
        return {"s3_path": f"s3://bucket/bronze/{self.dataset_name}/..."}


# Register it so Hamilton knows about "to.s3_bronze"
registry.register_adapter(S3BronzeSaver)

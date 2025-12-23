import io
import re
from typing import Optional

import boto3
import pandas


def read_table(
    key: str,
    sheet_name: str | int,
    skiprows: int,
) -> pandas.DataFrame:
    """Read Excel sheet from s3."""
    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket="asf-mission-data-tool", Key=key)
    content = io.BytesIO(obj["Body"].read())
    return pandas.read_excel(content, sheet_name=sheet_name, skiprows=skiprows)


def standardise_column_names(read_table: pandas.DataFrame, table_name: str) -> pandas.DataFrame:
    """Standardises column names across all tables by applying specific formatting rules."""
    if table_name == "Table 1.1":
        # Check if format of column names are as expected by this function
        if not read_table.columns.str.contains("\n").any():
            raise ValueError("Expected newline characters in column names for Table 1.1")
        if not read_table.columns.str.contains("Of which:").any():
            raise ValueError("Expected 'Of which:' in column names for Table 1.1")
        if not read_table.columns.str.contains("Total: Government-supported heat pump installations").any():
            raise ValueError(
                "Expected 'Total: Government-supported heat pump installations' in column names for Table 1.1"
            )

        read_table.columns = (
            read_table.columns.str.strip()
            .str.replace("\n", "", regex=True)
            .str.replace("Of which:", "", regex=False)
            .str.replace(
                "Total: Government-supported heat pump installations",
                "All schemes",
                regex=False,
            )
        )

    elif table_name == "Table 1.2":
        # Check if format of column names are as expected by this function
        if not read_table.columns.str.contains("\n").any():
            raise ValueError("Expected newline characters in column names for Table 1.2")
        if not read_table.columns.str.contains("Government-supported heat pump installations:").any():
            raise ValueError("Expected 'Government-supported heat pump installations:' in column names for Table 1.2")

        read_table.columns = (
            read_table.columns.str.strip()
            .str.replace("\n", "", regex=True)
            .str.replace("Government-supported heat pump installations:", "", regex=False)
            .str.capitalize()
        )
    elif table_name == "Table 1.3":
        pass
    else:
        raise ValueError("Sheet name does not correspond to a table in the dataset file.")
    return read_table


def check_missing_values(standardise_column_names: pandas.DataFrame, table_name: str) -> pandas.DataFrame:
    """Checks for missing values in a given dataframe and raises an error if any are found."""
    if standardise_column_names.isnull().values.any():
        raise ValueError(f"Error: {table_name} contains missing values.")
    return standardise_column_names


def expand_quarter_string(check_missing_values: pandas.DataFrame, table_name: str) -> pandas.DataFrame:
    """Converts a quarter string (e.g., "2018 Q1: January to March") into structured components:
    quarter, year, start date, and end date. Tailored to the DESNZ Heat Pump Deployment Quarterly Statistics data tables."""

    def convert_quarter_string(
        quarter_str: str,
    ) -> tuple[str, str, Optional[pandas.Timestamp], Optional[pandas.Timestamp]]:
        # Validate that input string is in expected format
        pattern = r"^\d{4} Q[1-4]: .+"
        if quarter_str != "Unknown" and not re.match(pattern, quarter_str):
            raise ValueError(
                f"Invalid quarter format: {quarter_str}. Expected format 'YYYY QX: <Month range of quarter>'."
            )

        # Handle Unknown cases
        if "Unknown" in quarter_str:
            return "Unknown", pandas.NA, None, None

        year, quarter_number = quarter_str.split(" Q")
        year = int(year)
        quarter = int(quarter_number[0])

        start_dates = {
            1: f"{year}-01-01",
            2: f"{year}-04-01",
            3: f"{year}-07-01",
            4: f"{year}-10-01",
        }

        end_dates = {
            1: f"{year}-03-31",
            2: f"{year}-06-30",
            3: f"{year}-09-30",
            4: f"{year}-12-31",
        }

        return (
            f"Q{quarter}",
            year,
            pandas.to_datetime(start_dates[quarter]),
            pandas.to_datetime(end_dates[quarter]),
        )

    check_missing_values[["Installation quarter [note 4]", "Year", "Start of quarter", "End of quarter"]] = (
        check_missing_values["Installation quarter [note 4]"].apply(lambda x: pandas.Series(convert_quarter_string(x)))
    )
    check_missing_values["Year"] = check_missing_values["Year"].astype(pandas.Int64Dtype())

    return check_missing_values


def melt_dataframe(
    expand_quarter_string: pandas.DataFrame,
    table_name: str,
    id_vars: list,
    value_name: str,
    var_name: Optional[str],
    value_vars: Optional[list],
) -> pandas.DataFrame:
    """Transforms a given dataframe from wide format to long format."""
    try:
        if value_vars:
            dataframe_long = expand_quarter_string.melt(id_vars=id_vars, value_vars=value_vars, value_name=value_name)
        else:
            dataframe_long = expand_quarter_string.melt(id_vars=id_vars, var_name=var_name, value_name=value_name)
    except KeyError as e:
        raise KeyError(f"One of the specified 'id_vars' or columns to melt does not exist in {table_name}: {e}")
    return dataframe_long


def rename_columns(melt_dataframe: pandas.DataFrame, column_map: dict) -> pandas.DataFrame:
    """Renames columns in given dataframe based on mapping provided in `column_map`."""
    melt_dataframe = melt_dataframe.rename(columns=column_map)
    return melt_dataframe


def assert_dtypes(rename_columns: pandas.DataFrame, table_name: str, expected_dtypes: dict) -> pandas.DataFrame:
    """Ensures that specified columns in a given dataframe have the expected data types."""
    for col, dtype in expected_dtypes.items():
        if col not in rename_columns.columns:
            raise KeyError((f"Expected column '{col}' not found in the dataframe for table '{table_name}'"))
        if rename_columns[col].dtype != dtype:
            try:
                rename_columns[col] = rename_columns[col].astype(dtype)
            except ValueError as e:
                raise ValueError(f"Unable to cast column '{col}' to type '{dtype}' in table '{table_name}'") from e
    return rename_columns


def save_table(
    assert_dtypes: pandas.DataFrame,
    dataset_key: str,
) -> None:
    """"""
    s3_client = boto3.client("s3")
    bucket_name = "asf-mission-data-tool"

    with io.BytesIO() as parquet_buffer:
        assert_dtypes.to_parquet(parquet_buffer, engine="pyarrow", index=False)
        parquet_buffer.seek(0)

        s3_client.put_object(
            Bucket=bucket_name,
            Key=dataset_key,
            Body=parquet_buffer.getvalue(),
        )
    return None

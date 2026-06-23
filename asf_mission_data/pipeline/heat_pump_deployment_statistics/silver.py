"""Hamilton nodes for silver-layer of the Heat Pump Deployment Statistics pipeline"""

import logging

import pandas as pd
from hamilton.function_modifiers import check_output, check_output_custom

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.heat_pump_deployment_statistics.config import (
    AREA_CODES_LOOKUP,
    GEOGRAPHIC_LEVEL_MAP,
    TABLE_1_1_VALUE_VARS,
    TABLE_1_2_VALUE_VARS,
)
from asf_mission_data.pipeline.heat_pump_deployment_statistics.schemas import (
    SILVER_TABLE_1_1_SCHEMA,
    SILVER_TABLE_1_2_SCHEMA,
    WIDE_TABLE_1_1_SCHEMA,
    WIDE_TABLE_1_2_SCHEMA,
)
from asf_mission_data.pipeline.heat_pump_deployment_statistics.validators import (
    StartStringValidator,
)

logger = logging.getLogger(__name__)


# Common silver nodes
def bronze_heat_pump_deployment_statistics_file(dataset_prefix: str) -> str:
    """Locate the latest bronze-layer Excel file for the Heat Pump Deployment Statistics pipeline.

    Args:
        dataset_prefix (str): Prefix used to locate the bronze dataset.

    Returns:
        str: URI or file path to the latest bronze Excel file.
    """
    return storage.locate_latest(dataset_prefix, "file", "bronze")


def bronze_heat_pump_deployment_statistics_metadata(
    dataset_prefix: str,
) -> dict[str, str]:
    """Load metadata associated with the latest bronze dataset.

    Args:
        pipeline_name (str): Pipeline identifier used to locate metadata.

    Returns:
        dict: Dictionary containing metadata fields such as publication date and source information.
    """
    metadata_uri = storage.locate_latest(dataset_prefix, "metadata", "bronze")
    return storage.read_json(metadata_uri)


def notes_lookup(
    bronze_heat_pump_deployment_statistics_file: str,
) -> dict[str, str]:
    """Create lookup for the numbered 'Notes' in the Heat Pump Deployment Statistics Excel workbook.
    'Notes' are located in a separate sheet from the data tables.

    Args:
        bronze_heat_pump_deployment_statistics_file (str): URI or file path to the latest bronze Excel file.

    Returns:
        dict[str, str]: Dictionary with note number-note text as key-value pairs.
    """
    notes_df = storage.read_excel_sheet(bronze_heat_pump_deployment_statistics_file, sheet_name="Notes")
    header_row = notes_df[notes_df["Notes"].str.contains("Note number", na=False)].index[0]
    df = notes_df.iloc[header_row + 1 :].copy()
    df.columns = notes_df.iloc[header_row]
    df = df.reset_index(drop=True)
    df.columns.name = None
    notes = dict(zip(df["Note number"], df["Note text"], strict=False))
    logger.debug("Loaded %d heat pump notes from workbook", len(notes))
    return notes


def latest_publication_date(
    bronze_heat_pump_deployment_statistics_metadata: dict[str, str],
) -> str:
    """Return publication date of latest bronze file from metadata."""
    return bronze_heat_pump_deployment_statistics_metadata.get("publication_date")


# Helpers for all silver tables
def _clean_table(df_raw: pd.DataFrame, first_col: str) -> pd.DataFrame:
    """Extract and clean target table from a raw Excel sheet dataframe.

    Args:
        df_raw (pd.DataFrame): Raw dataframe read from a sheet in the Excel file.
        first_col (str): Expected first column name of the raw sheet dataframe.

    Returns:
        pd.DataFrame: Cleaned dataframe containing only target data and stripped
            column names.
    """
    # Locate row index with target table columns
    header_row = df_raw[df_raw[first_col].str.contains("Installation quarter", na=False)].index[0]

    # Create new df with target data only
    df = df_raw.iloc[header_row + 1 :].copy()
    df.columns = df_raw.iloc[header_row]
    df = df.reset_index(drop=True)
    df.columns.name = None

    # Clean up column names
    df.columns = df.columns.str.strip().str.replace("\n", "", regex=True)
    return df


def _apply_notes(df: pd.DataFrame, notes_lookup: dict[str, str]) -> pd.DataFrame:
    """Adds a 'Notes' column to the cleaned dataframe and uses a lookup to
    populate with the note text corresponding to the not number specified in the
    Installation Quarter column.

    Args:
        df (pd.DataFrame): Cleaned dataframe containing sheet data.
        notes_lookup (dict[str, str]): Dictionary with note number-note text as key-value pairs.
            Read from the 'Notes' sheet in the Excel workbook.

    Returns:
        pd.DataFrame: Cleaned dataframe with a new 'Notes' column.
    """
    df = df.copy()
    df["Notes"] = ""

    for col in df.columns:
        match = pd.Series(col).str.extract(r"\[(note \d+)\]").iloc[0, 0]

        if pd.notna(match):
            df["Notes"] += " " + notes_lookup.get(match, "")
            df = df.rename(columns={col: col.replace(f"[{match}]", "").strip()})

    df["Note ref"] = df["Installation quarter"].str.extract(r"\[(note \d+)\]")
    df["Note text"] = df["Note ref"].map(notes_lookup)

    df["Notes"] = df["Notes"] + " " + df["Note text"].fillna("")

    df["Installation quarter"] = df["Installation quarter"].str.replace(r"\[note \d+\]", "", regex=True).str.strip()

    return df.drop(columns=["Note ref", "Note text"])


def _add_quarter_dates(df: pd.DataFrame) -> pd.DataFrame:
    """Add start and end date columns derived from the 'Installation quarter' column.

    Args:
        df (pd.DataFrame): Cleaned dataframe containing an 'Installation quarter' column.
            Installation quarter values expected to contain string with format YYYY Qn.

    Returns:
        pd.DataFrame: Dataframe with added 'Installation quarter start' and 'Installation
            quarter end' timestamp columns.
    """
    if "Installation quarter" not in df.columns:
        raise ValueError("Expected column 'Installation quarter' not found. Has the source file structure changed?")

    df = df.copy()

    q_start = {"Q1": 1, "Q2": 4, "Q3": 7, "Q4": 10}
    q_end = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12}

    df[["Installation quarter start", "Installation quarter end"]] = (
        df["Installation quarter"]
        .str.extract(r"(\d{4}) (Q[1-4])")
        .apply(
            lambda x: pd.Series(
                [
                    pd.Timestamp(year=int(x[0]), month=q_start[x[1]], day=1),
                    pd.Timestamp(year=int(x[0]), month=q_end[x[1]], day=1) + pd.offsets.MonthEnd(0),
                ]
            ),
            axis=1,
        )
    )

    return df


def _append_metadata(
    df: pd.DataFrame,
    metadata: dict[str, str],
    table_name: str,
    data_source: str,
) -> pd.DataFrame:
    """Add 'metadata' column, populated with an enriched metadata dictionary to include silver table-specific
        fields. Each row has the same metadata dict attached.

    Args:
        df (pd.DataFrame): Silver table dataframe in tidy format.
        metadata (dict[str, str]): Latest bronze metadata.
        table_name (str): Name of the table, extracted from Excel sheet.
        data_source (str): Cited source, extracted from Excel sheet.

    Returns:
        pd.DataFrame: Silver dataframe with 'metadata' column containing enriched metadata.
    """

    df = df.copy()
    metadata_copy = metadata.copy()
    metadata_copy["table_name"] = table_name
    metadata_copy["data_source"] = data_source
    metadata_copy["citation"] = (
        f"Source: {metadata_copy.get('publisher', '')}, {metadata_copy.get('filename', '')}. "
        f"{metadata_copy['table_name']}. Published {metadata_copy.get('publication_date', '')}, "
        f"{metadata_copy.get('page_url', '')}."
    )
    df["metadata"] = [metadata_copy] * len(df)

    return df


# Table 1.1


def table_1_1_df_raw(bronze_heat_pump_deployment_statistics_file: str, sheet_name: str) -> pd.DataFrame:
    """Raw Excel sheet for Table 1.1 as dataframe.

    Args:
        bronze_heat_pump_deployment_statistics_file (str): Path to latest bronze Excel file.
        sheet_name (str): Name of Table 1.1 sheet in the Excel workbook.

    Returns:
        pd.DataFrame: Dataframe containing raw sheet data.
    """
    return storage.read_excel_sheet(bronze_heat_pump_deployment_statistics_file, sheet_name)


@check_output_custom(StartStringValidator("Table 1.1"))
def table_1_1_name(table_1_1_df_raw: pd.DataFrame) -> str:
    """Extracted full name of Table 1.1. Expected to be the first cell of the sheet."""
    return table_1_1_df_raw.columns[0]


@check_output_custom(StartStringValidator("Source:"))
def table_1_1_data_source(table_1_1_df_raw: pd.DataFrame) -> str:
    """Extracted source citation in Table 1.1. Expected to be in the first column."""
    mask = table_1_1_df_raw.iloc[:, 0].astype(str).str.startswith("Source:", na=False)

    if not mask.any():
        raise ValueError("No source row found")

    return table_1_1_df_raw.loc[mask].iloc[0, 0]


def table_1_1_df_cleaned(table_1_1_df_raw: pd.DataFrame, table_1_1_name: str) -> pd.DataFrame:
    """Cleaned dataframe containing only target data and stripped column names."""
    return _clean_table(table_1_1_df_raw, table_1_1_name)


def table_1_1_with_notes_df(table_1_1_df_cleaned: pd.DataFrame, notes_lookup: dict) -> pd.DataFrame:
    """Cleaned dataframe with a publisher 'Notes' column."""
    df = _apply_notes(table_1_1_df_cleaned, notes_lookup)
    if df["Notes"].str.strip().eq("").all():
        raise ValueError("Notes column is entirely empty: notes lookup may have failed to match. Has the source file structure changed?")
    return df


@check_output(schema=WIDE_TABLE_1_1_SCHEMA, importance="fail")  # names-only schema ensures valid id_vars and value_vars for melting
def table_1_1_df_datetime_quarters(
    table_1_1_with_notes_df: pd.DataFrame,
) -> pd.DataFrame:
    """Cleaned dataframe with added 'Installation quarter start' and 'Installation quarter
    end' timestamp columns."""
    return _add_quarter_dates(table_1_1_with_notes_df)


def table_1_1_df_melted(
    table_1_1_df_datetime_quarters: pd.DataFrame,
) -> pd.DataFrame:
    """Table 1.1 data in tidy format."""
    df = table_1_1_df_datetime_quarters.copy()
    id_vars = [
        "Installation quarter",
        "Installation quarter start",
        "Installation quarter end",
        "Notes",
    ]
    return pd.melt(
        df,
        id_vars=id_vars,
        value_vars=TABLE_1_1_VALUE_VARS,
        var_name="Type",
        value_name="value",
    )


@check_output(schema=SILVER_TABLE_1_1_SCHEMA, importance="fail")
def silver_table_1_1_df(
    table_1_1_df_melted: pd.DataFrame,
    bronze_heat_pump_deployment_statistics_metadata: dict[str, str],
    table_1_1_name: str,
    table_1_1_data_source: str,
) -> pd.DataFrame:
    """Silver dataframe for Table 1.1 with silver-layer enriched metadata."""
    df = table_1_1_df_melted.copy()
    df["value"] = df["value"].astype(int)
    df = _append_metadata(
        df,
        bronze_heat_pump_deployment_statistics_metadata,
        table_1_1_name,
        table_1_1_data_source,
    )
    df = utils.standardise_column_names(df)

    logger.info(
        "Produced silver table 'table_1_1': rows=%d quarters=%d types=%d null_values=%d",
        len(df),
        df["installation_quarter"].nunique(),
        df["type"].nunique(),
        int(df["value"].isna().sum()),
    )
    logger.debug(
        "Silver table 'table_1_1' rows by type: %s",
        df["type"].value_counts(dropna=False).to_dict(),
    )

    return df


def silver_heat_pump_deployment_statistics_table_1_1_parquet(
    silver_table_1_1_df: pd.DataFrame,
    dataset_prefix: str,
    latest_publication_date: str,
    sheet_name: str,
) -> None:
    """Ingested table to silver-layer storage for Table 1.1 as parquet file."""
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=silver_table_1_1_df,
        df_name=sheet_name.lower().replace(".", "_").replace(" ", "_"),
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
    )


# Table 1.2


def table_1_2_df_raw(bronze_heat_pump_deployment_statistics_file: str, sheet_name: str) -> pd.DataFrame:
    """Raw Excel sheet for Table 1.2 as dataframe.

    Args:
        bronze_heat_pump_deployment_statistics_file (str): Path to latest bronze Excel file.
        sheet_name (str): Name of Table 1.2 sheet in the Excel workbook.

    Returns:
        pd.DataFrame: Dataframe containing raw sheet data.
    """
    return storage.read_excel_sheet(bronze_heat_pump_deployment_statistics_file, sheet_name)


@check_output_custom(StartStringValidator("Table 1.2"))
def table_1_2_name(table_1_2_df_raw: pd.DataFrame) -> str:
    """Extracted full name of Table 1.2. Expected to be the first cell of the sheet."""
    return table_1_2_df_raw.columns[0]


@check_output_custom(StartStringValidator("Source:"))
def table_1_2_data_source(table_1_2_df_raw: pd.DataFrame) -> str:
    """Extract source citation in Table 1.2. Expected to be in the first column."""
    mask = table_1_2_df_raw.iloc[:, 0].astype(str).str.startswith("Source:", na=False)

    if not mask.any():
        raise ValueError("No source row found")

    return table_1_2_df_raw.loc[mask].iloc[0, 0]


def table_1_2_df_cleaned(table_1_2_df_raw: pd.DataFrame, table_1_2_name: str) -> pd.DataFrame:
    """Cleaned dataframe containing only target data and stripped column names."""
    return _clean_table(table_1_2_df_raw, table_1_2_name)


def table_1_2_with_notes_df(table_1_2_df_cleaned: pd.DataFrame, notes_lookup: dict) -> pd.DataFrame:
    """Cleaned dataframe with a publisher 'Notes' column."""
    return _apply_notes(table_1_2_df_cleaned, notes_lookup)


@check_output(schema=WIDE_TABLE_1_2_SCHEMA, importance="fail")  # names-only schema ensures valid id_vars and value_vars for melting
def table_1_2_df_datetime_quarters(
    table_1_2_with_notes_df: pd.DataFrame,
) -> pd.DataFrame:
    """Cleaned dataframe with added 'Installation quarter start' and 'Installation quarter
    end' timestamp columns."""
    return _add_quarter_dates(table_1_2_with_notes_df)


def table_1_2_df_melted(
    table_1_2_df_datetime_quarters: pd.DataFrame,
) -> pd.DataFrame:
    """Table 1.2 data in tidy format."""
    df = table_1_2_df_datetime_quarters.copy()
    id_vars = [
        "Installation quarter",
        "Installation quarter start",
        "Installation quarter end",
        "Notes",
    ]
    return pd.melt(
        df,
        id_vars=id_vars,
        value_vars=TABLE_1_2_VALUE_VARS,
        var_name="country_or_region",
        value_name="value",
    )


@check_output(schema=SILVER_TABLE_1_2_SCHEMA, importance="fail")
def silver_table_1_2_df(
    table_1_2_df_melted: pd.DataFrame,
    bronze_heat_pump_deployment_statistics_metadata: dict[str, str],
    table_1_2_name: str,
    table_1_2_data_source: str,
) -> pd.DataFrame:
    """Silver dataframe for Table 1.2 with silver-layer enriched metadata and supporting area code column.
    Area code field is added back in to ensure consistency with other regional datasets."""
    df = table_1_2_df_melted.copy()
    df["value"] = df["value"].astype(int)
    df = _append_metadata(
        df,
        bronze_heat_pump_deployment_statistics_metadata,
        table_1_2_name,
        table_1_2_data_source,
    )
    df["area_code"] = df["country_or_region"].map(AREA_CODES_LOOKUP).fillna("N/A")
    df["geographic_level"] = df["country_or_region"].map(GEOGRAPHIC_LEVEL_MAP)
    df = utils.standardise_column_names(df)

    logger.info(
        "Produced silver table 'table_1_2': rows=%d quarters=%d regions=%d null_values=%d",
        len(df),
        df["installation_quarter"].nunique(),
        df["country_or_region"].nunique(),
        int(df["value"].isna().sum()),
    )
    logger.debug(
        "Silver table 'table_1_2' rows by geographic level: %s",
        df["geographic_level"].value_counts(dropna=False).to_dict(),
    )

    return df


def silver_heat_pump_deployment_statistics_table_1_2_parquet(
    silver_table_1_2_df: pd.DataFrame,
    dataset_prefix: str,
    latest_publication_date: str,
    sheet_name: str,
) -> str:
    """Ingested table to silver-layer storage for Table 1.2 as parquet file."""
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=silver_table_1_2_df,
        df_name=sheet_name.lower().replace(".", "_").replace(" ", "_"),
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
    )

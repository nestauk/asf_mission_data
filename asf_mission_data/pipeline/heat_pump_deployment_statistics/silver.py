import pandas as pd
from hamilton.function_modifiers import (
    check_output,
)

from asf_mission_data import storage, utils
from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.heat_pump_deployment_statistics.schemas import SILVER_TABLE_1_1_SCHEMA

logger = setup_logging(__name__)


# Common silver nodes
def bronze_heat_pump_deployment_statistics_file(dataset_prefix: str) -> str:
    return storage.locate_latest_bronze(dataset_prefix, "file")


def bronze_heat_pump_deployment_statistics_metadata(dataset_prefix: str) -> dict[str, str]:
    metadata_uri = storage.locate_latest_bronze(dataset_prefix, "metadata")
    return storage.read_json(metadata_uri)


def notes_lookup(bronze_heat_pump_deployment_statistics_file: str) -> dict[str, str]:
    notes_df = storage.read_excel_sheet(bronze_heat_pump_deployment_statistics_file, sheet_name="Notes")
    header_row = notes_df[notes_df["Notes"].str.contains("Note number", na=False)].index[0]
    df = notes_df.iloc[header_row + 1 :].copy()
    df.columns = notes_df.iloc[header_row]
    df = df.reset_index(drop=True)
    df.columns.name = None
    return dict(zip(df["Note number"], df["Note text"], strict=False))


def latest_publication_date(bronze_heat_pump_deployment_statistics_metadata: dict[str, str]) -> str:
    return bronze_heat_pump_deployment_statistics_metadata.get("publication_date")


# Helpers for all silver tables
def _clean_table(df_raw: pd.DataFrame, first_col: str) -> pd.DataFrame:
    header_row = df_raw[df_raw[first_col].str.contains("Installation quarter", na=False)].index[0]

    df = df_raw.iloc[header_row + 1 :].copy()
    df.columns = df_raw.iloc[header_row]
    df = df.reset_index(drop=True)
    df.columns.name = None

    df.columns = df.columns.str.strip().str.replace("\n", "", regex=True)
    return df


def _apply_notes(df: pd.DataFrame, notes_lookup: dict[str, str]) -> pd.DataFrame:
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


def _append_metadata(df: pd.DataFrame, metadata: dict[str, str], table_name: str, data_source: str) -> pd.DataFrame:

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
    return storage.read_excel_sheet(bronze_heat_pump_deployment_statistics_file, sheet_name)


def table_1_1_name(table_1_1_df_raw: pd.DataFrame) -> str:
    return table_1_1_df_raw.columns[0]


def table_1_1_data_source(table_1_1_df_raw: pd.DataFrame) -> str:
    return table_1_1_df_raw.loc[3].iloc[0]


def table_1_1_df_cleaned(table_1_1_df_raw: pd.DataFrame, table_1_1_name: str) -> pd.DataFrame:
    return _clean_table(table_1_1_df_raw, table_1_1_name)


def table_1_1_with_notes_df(table_1_1_df_cleaned: pd.DataFrame, notes_lookup: dict) -> pd.DataFrame:
    return _apply_notes(table_1_1_df_cleaned, notes_lookup)


def table_1_1_df_datetime_quarters(table_1_1_with_notes_df: pd.DataFrame) -> pd.DataFrame:
    return _add_quarter_dates(table_1_1_with_notes_df)


def table_1_1_df_melted(table_1_1_df_datetime_quarters: pd.DataFrame) -> pd.DataFrame:
    df = table_1_1_df_datetime_quarters.copy()
    id_vars = ["Installation quarter", "Installation quarter start", "Installation quarter end", "Notes"]
    value_vars = ["Air source heat pump installations", "Ground/water source heat pump installations", "Total heat pump installations"]
    return pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name="Type", value_name="value")


@check_output(schema=SILVER_TABLE_1_1_SCHEMA, importance="fail")
def silver_table_1_1_df(
    table_1_1_df_melted: pd.DataFrame,
    bronze_heat_pump_deployment_statistics_metadata: dict[str, str],
    table_1_1_name: str,
    table_1_1_data_source: str,
) -> pd.DataFrame:
    df = table_1_1_df_melted.copy()
    df["value"] = df["value"].astype(int)
    df = _append_metadata(df, bronze_heat_pump_deployment_statistics_metadata, table_1_1_name, table_1_1_data_source)
    return df


def silver_heat_pump_deployment_statistics_table_1_1_parquet(
    silver_table_1_1_df: pd.DataFrame, dataset_prefix: str, latest_publication_date: str, sheet_name: str
) -> str:
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=silver_table_1_1_df,
        df_name=sheet_name.lower().replace(".", "_").replace(" ", "_"),
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
    )


# Table 1.2
def table_1_2_df_raw(bronze_heat_pump_deployment_statistics_file: str, sheet_name: str) -> pd.DataFrame:
    return storage.read_excel_sheet(bronze_heat_pump_deployment_statistics_file, sheet_name)


def table_1_2_name(table_1_2_df_raw: pd.DataFrame) -> str:
    return table_1_2_df_raw.columns[0]


def table_1_2_data_source(table_1_2_df_raw: pd.DataFrame) -> str:
    return table_1_2_df_raw.loc[3].iloc[0]


def area_codes_lookup(table_1_2_df_raw: pd.DataFrame) -> dict[str, str]:
    area_codes_row = table_1_2_df_raw[table_1_2_df_raw[table_1_2_name].str.contains("Area Codes and Country or Region", na=False)].index[0]
    region_names_row = table_1_2_df_raw[table_1_2_df_raw[table_1_2_name].str.contains("Installation quarter", na=False)].index[0]
    area_codes = table_1_2_df_raw.iloc[area_codes_row, 1:]  # skip first column (header)
    region_names = table_1_2_df_raw.iloc[region_names_row, 1:]  # skip first column
    region_names = region_names.str.replace("\n", " ", regex=True).str.strip()
    mask = area_codes.notna()
    area_codes = area_codes[mask]
    region_names = region_names[mask]
    return dict(zip(region_names, area_codes, strict=False))


def table_1_2_df_cleaned(table_1_2_df_raw: pd.DataFrame, table_1_2_name: str) -> pd.DataFrame:
    return _clean_table(table_1_2_df_raw, table_1_2_name)


def table_1_2_with_notes_df(table_1_2_df_cleaned: pd.DataFrame, notes_lookup: dict) -> pd.DataFrame:
    return _apply_notes(table_1_2_df_cleaned, notes_lookup)


def table_1_2_df_datetime_quarters(table_1_2_with_notes_df: pd.DataFrame) -> pd.DataFrame:
    return _add_quarter_dates(table_1_2_with_notes_df)


def table_1_2_df_melted(table_1_2_df_datetime_quarters: pd.DataFrame) -> pd.DataFrame:
    df = table_1_2_df_datetime_quarters.copy()
    id_vars = ["Installation quarter", "Installation quarter start", "Installation quarter end", "Notes"]
    value_vars = [
        "United Kingdom",
        "England and Wales",
        "England",
        "North East",
        "North West",
        "Yorkshire and The Humber",
        "East Midlands",
        "West Midlands",
        "East",
        "London",
        "South East",
        "South West",
        "Wales",
        "Scotland",
        "Northern Ireland",
        "Unknown",
    ]
    return pd.melt(df, id_vars=id_vars, value_vars=value_vars, var_name="Country or Region", value_name="value")


# TODO output validation here
def silver_table_1_2_df(
    table_1_2_df_melted: pd.DataFrame,
    bronze_heat_pump_deployment_statistics_metadata: dict[str, str],
    table_1_2_name: str,
    table_1_2_data_source: str,
    area_codes_lookup: dict[str, str],
) -> pd.DataFrame:
    df = table_1_2_df_melted.copy()
    df["value"] = df["value"].astype(int)
    df = _append_metadata(df, bronze_heat_pump_deployment_statistics_metadata, table_1_2_name, table_1_2_data_source)
    df["Area code"] = df["Country or Region"].map(area_codes_lookup).fillna("N/A")
    return df


def silver_heat_pump_deployment_statistics_table_1_2_parquet(
    silver_table_1_2_df: pd.DataFrame, dataset_prefix: str, latest_publication_date: str, sheet_name: str
) -> str:
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=silver_table_1_2_df,
        df_name=sheet_name.lower().replace(".", "_").replace(" ", "_"),
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
    )

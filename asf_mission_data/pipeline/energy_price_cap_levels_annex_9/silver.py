"""Hamilton nodes for silver-layer of the Energy Price Cap Levels Annex 9 pipeline."""

import logging

import pandas as pd
from hamilton.function_modifiers import (
    check_output,
    check_output_custom,
    extract_columns,
    parameterize,
    source,
    value,
)

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    PRICE_CAP_PERIOD_PUBLICATION_DATES,
)
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.schemas import (
    SILVER_1C_CONSUMPTION_ADJUSTED_LEVELS_SCHEMA,
)
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.validators import (
    PriceCapValidator,
)

logger = logging.getLogger(__name__)

# ----------------------------------
# Common silver nodes
# ----------------------------------


def bronze_energy_price_cap_annex_9_file(dataset_prefix: str) -> str:
    """Latest bronze-level dataset for Energy Price Cap Annex 9."""
    return storage.locate_latest_bronze(dataset_prefix, "file")


def excel_sheet_df(bronze_energy_price_cap_annex_9_file: str, sheet_name: str) -> pd.DataFrame:
    """Load the a target worksheet from the bronze Excel file."""
    return storage.read_excel_sheet(bronze_energy_price_cap_annex_9_file, sheet_name)


def bronze_energy_price_cap_annex_9_metadata(dataset_prefix: str) -> dict:
    """Load metadata associated with the latest bronze dataset."""
    metadata_uri = storage.locate_latest_bronze(dataset_prefix, "metadata")
    return storage.read_json(metadata_uri)


@check_output_custom(PriceCapValidator(PRICE_CAP_PERIOD_PUBLICATION_DATES))
def latest_price_cap_period(
    bronze_energy_price_cap_annex_9_metadata: dict[str, str],
) -> str:
    """Extract the latest price cap period from the bronze metadata."""
    period = bronze_energy_price_cap_annex_9_metadata.get("price_cap_period")
    if not period:
        raise KeyError("'price_cap_period' missing from bronze metadata.")
    return period


# ----------------------------------
# Silver dataset 1
# 1c Consumption adjusted levels table
# ----------------------------------


# Helper for payment method and fuel combinations
PAYMENT_KEYS = ["other_payment_method", "standard_credit", "ppm"]
FUEL_KEYS = [
    "electricity_single_rate",
    "electricity_multi_register",
    "gas",
    "dual_fuel",
]
PAYMENT_METHOD_LOOKUP = {
    "other_payment_method": "Other Payment Method",
    "standard_credit": "Standard Credit",
    "ppm": "PPM",
}
FUEL_TYPE_LOOKUP = {
    "electricity_single_rate": "Electricity: Single-Rate Metering Arrangement",
    "electricity_multi_register": "Electricity: Multi-Register Metering Arrangement",
    "gas": "Gas",
    "dual_fuel": "Dual fuel (implied)",
}


def _construct_node_name(fuel_key: str, payment_key: str, step: str) -> str:
    """Generate a standardised Hamilton node name for a given fuel type, payment method, and processing step.

    The format of the node name is: `{fuel_key}_{payment_key}_{step}`.
    This helps create unique and predictable node identifiers in the pipeline.

    Args:
        fuel_key (str): Identifier from FUEL_KEYS (e.g., "electricity_single_rate").
        payment_key (str): Identifier from PAYMENT_KEYS (e.g., "standard_credit").
        step (str): Description of the node step (e.g., "tidy_df", "melted_df").

    Returns:
        str: Concatenated node name combining fuel, payment method, and step.
    """
    return f"{fuel_key}_{payment_key}_{step}"


def _get_payment_method_table_range(excel_sheet_df: pd.DataFrame, payment_method: str) -> tuple[int, int]:
    """Identify the row range corresponding to a payment method tariff table.

    The function finds the start row where the payment method header appears
    and the end row corresponding to the second occurrence of "Total inc VAT",
    which marks the end of the typical consumption section.

    Args:
        tariff_tables_excel_sheet_df (pd.DataFrame): Raw tariff tables sheet.
        payment_method (str): Payment method label (e.g. "Standard Credit").

    Returns:
        tuple[int, int]: Tuple containing start and end row indices of the payment method table.
    """

    # Find the first row of the payment method section
    header_matches = excel_sheet_df.index[excel_sheet_df["Unnamed: 1"] == payment_method].tolist()

    if not header_matches:
        raise ValueError(f"Could not find payment method header '{payment_method}'.")

    start_index = header_matches[0]

    # Only dual fuel tables have Total inc VAT row
    dual_fuel_cols = excel_sheet_df.columns[(excel_sheet_df == "Dual fuel (implied)").any(axis=0)].to_list()

    if not dual_fuel_cols:
        raise KeyError("Could not find a column containing 'Dual fuel'.")

    dual_fuel_header_column = dual_fuel_cols[0]

    # Find row indices for "Total inc VAT" that occur after the start index
    possible_table_end_indices = excel_sheet_df.index[
        (excel_sheet_df[dual_fuel_header_column] == "Total inc VAT") & (excel_sheet_df.index > start_index)
    ].tolist()

    # Expect that there are at least 2 Total inc VAT occurences after each payment method header
    # One in the Nil Consumption table and one in the Typical Consumption table
    if len(possible_table_end_indices) < 2:
        raise IndexError(
            f"Expected at least 2 'Total inc VAT' rows after {payment_method} at index {start_index},"
            f"but found only {len(possible_table_end_indices)}."
        )

    # Expect that second occurrence of "Total inc VAT" after start index is the
    # last row of the "Typical consumption" table for each payment method
    end_index = possible_table_end_indices[1]

    return start_index, end_index


@parameterize(
    raw_other_payment_method_table_df={"payment_method": value("Other Payment Method")},
    raw_standard_credit_table_df={"payment_method": value("Standard Credit")},
    raw_ppm_table_df={"payment_method": value("PPM")},
)
def raw_payment_method_table_df(excel_sheet_df: pd.DataFrame, payment_method: str) -> pd.DataFrame:
    """Extract the raw tariff table for a specific payment method.

    Args:
        tariff_tables_excel_sheet_df (pd.DataFrame): Raw tariff tables sheet.
        payment_method (str): Payment method label to extract.

    Returns:
        pd.DataFrame: DataFrame containing the table slice for the specified payment method.
    """
    start_index, end_index = _get_payment_method_table_range(excel_sheet_df, payment_method)

    df_slice = excel_sheet_df.loc[start_index:end_index, :].copy()

    # Check slice is expected payment method section
    header = str(df_slice.iloc[0, 1]).strip()
    if header != payment_method:
        raise ValueError(f"Slice Error: Expected header '{payment_method}' at top of dataframe slice, but found '{header}'")

    logger.debug(
        "Extracted %s table: rows %s to %s (%d rows, %d columns)", payment_method, start_index, end_index, len(df_slice), len(df_slice.columns)
    )

    return df_slice


@parameterize(
    cleaned_other_payment_method_table_df={"raw_payment_method_table_df": source("raw_other_payment_method_table_df")},
    cleaned_standard_credit_table_df={"raw_payment_method_table_df": source("raw_standard_credit_table_df")},
    cleaned_ppm_table_df={"raw_payment_method_table_df": source("raw_ppm_table_df")},
)
def cleaned_payment_method_table_df(
    raw_payment_method_table_df: pd.DataFrame,
) -> pd.DataFrame:
    """Remove empty rows and columns from a payment method tariff table.

    Args:
        raw_payment_method_table_df (pd.DataFrame): Raw extracted payment method table.

    Returns:
        pd.DataFrame: Cleaned DataFrame with empty rows and columns removed.
    """

    df_cleaned = raw_payment_method_table_df.dropna(axis="index", how="all").dropna(axis="columns", how="all").reset_index(drop=True)

    return df_cleaned


@parameterize(
    forward_filled_columns_other_payment_method_table_df={"cleaned_payment_method_table_df": source("cleaned_other_payment_method_table_df")},
    forward_filled_columns_standard_credit_table_df={"cleaned_payment_method_table_df": source("cleaned_standard_credit_table_df")},
    forward_filled_columns_ppm_table_df={"cleaned_payment_method_table_df": source("cleaned_ppm_table_df")},
)
def forward_filled_columns_payment_method_table_df(
    cleaned_payment_method_table_df: pd.DataFrame,
) -> pd.DataFrame:
    """Forward-fill column headers across the payment method table.

    Some columns in the Excel sheet contain merged headers. This function
    fills those values horizontally to produce consistent column labels.

    Args:
        cleaned_payment_method_table_df (pd.DataFrame): Silver table with empty rows and columns dropped.

    Returns:
        pd.DataFrame: DataFrame with column values forward-filled.
    """

    df_filled = cleaned_payment_method_table_df.ffill(axis="columns").infer_objects()

    return df_filled


def _get_fuel_columns(forward_filled_columns_payment_method_table_df: pd.DataFrame, fuel: str) -> list[str]:
    """Identify columns associated with a specific fuel type.

    Args:
        forward_filled_columns_payment_method_table_df (pd.DataFrame): Cleaned and forward-filled table.
        fuel (str): Fuel label (e.g. gas).

    Returns:
        list[str]: List of column names corresponding to the specified fuel type.

    Raises:
        ValueError: If no columns are found for the specified fuel type.
    """
    cols = forward_filled_columns_payment_method_table_df.columns[(forward_filled_columns_payment_method_table_df == fuel).any(axis=0)].to_list()

    if not cols:
        raise ValueError(f"Could not find columns for fuel '{fuel}'.")

    return cols


NIL_DF_MAP = {
    _construct_node_name(fuel, payment, "nil_consumption_df"): {
        "forward_filled_columns_payment_method_table_df": source(f"forward_filled_columns_{payment}_table_df"),
        "payment_method": value(payment),
        "fuel": value(FUEL_TYPE_LOOKUP[fuel]),
    }
    for payment in PAYMENT_KEYS
    for fuel in FUEL_KEYS
}


@parameterize(**NIL_DF_MAP)
def fuel_nil_consumption_df(
    forward_filled_columns_payment_method_table_df: pd.DataFrame,
    payment_method: str,
    fuel: str,
) -> pd.DataFrame:
    """Extract the 'Nil consumption' tariff table for a fuel and payment method.

    Args:
        forward_filled_columns_payment_method_table_df (pd.DataFrame): Cleaned and
            forward-filled payment method tariff table.
        payment_method (str): Payment method identifier.
        fuel (str): Fuel type label.

    Returns:
        pd.DataFrame: DataFrame containing nil consumption tariff components.
    """

    fuel_columns = _get_fuel_columns(forward_filled_columns_payment_method_table_df, fuel)

    nil_matches = forward_filled_columns_payment_method_table_df.index[
        forward_filled_columns_payment_method_table_df[fuel_columns[0]] == "Nil consumption"
    ].tolist()
    if not nil_matches:
        raise ValueError(f"Could not find 'Nil consumption' header for fuel '{fuel}'.")
    start_nil_consumption_index = nil_matches[0]

    typical_matches = forward_filled_columns_payment_method_table_df.index[
        forward_filled_columns_payment_method_table_df[fuel_columns[0]] == "Typical consumption"
    ].tolist()
    if not typical_matches:
        raise ValueError(f"Could not find 'Typical consumption' header for fuel '{fuel}'.")
    start_typical_consumption_index = typical_matches[0]

    fuel_nil_df = (
        forward_filled_columns_payment_method_table_df[fuel_columns]
        .loc[
            start_nil_consumption_index : start_typical_consumption_index - 1,
            :,
        ]
        .reset_index(drop=True)
    )
    fuel_nil_df.columns = fuel_nil_df.iloc[0]
    fuel_nil_df = fuel_nil_df.iloc[1:]
    fuel_nil_df = fuel_nil_df.rename(columns={"Nil consumption": "Tariff component"})
    fuel_nil_df["Payment method"] = PAYMENT_METHOD_LOOKUP.get(payment_method)
    fuel_nil_df["Consumption"] = "Nil consumption"
    fuel_nil_df["Fuel"] = fuel
    return fuel_nil_df


TYPICAL_DF_MAP = {
    _construct_node_name(fuel, payment, "typical_consumption_df"): {
        "forward_filled_columns_payment_method_table_df": source(f"forward_filled_columns_{payment}_table_df"),
        "payment_method": value(payment),
        "fuel": value(FUEL_TYPE_LOOKUP[fuel]),
    }
    for payment in PAYMENT_KEYS
    for fuel in FUEL_KEYS
}


@parameterize(**TYPICAL_DF_MAP)
def fuel_typical_consumption_df(
    forward_filled_columns_payment_method_table_df: pd.DataFrame,
    payment_method: str,
    fuel: str,
) -> pd.DataFrame:
    """Extract the 'Typical consumption' tariff table for a fuel and payment method.

    Args:
        forward_filled_columns_payment_method_table_df (pd.DataFrame): Cleaned and
            forward-filled payment method tariff table.
        payment_method (str): Payment method identifier.
        fuel (str): Fuel type label.

    Returns:
        pd.DataFrame: DataFrame containing typical consumption tariff components.
    """

    fuel_columns = _get_fuel_columns(forward_filled_columns_payment_method_table_df, fuel)

    typical_matches = forward_filled_columns_payment_method_table_df.index[
        forward_filled_columns_payment_method_table_df[fuel_columns[0]] == "Typical consumption"
    ].tolist()
    if not typical_matches:
        raise ValueError(f"Could not find 'Typical consumption' header for fuel '{fuel}'.")
    start_typical_consumption_index = typical_matches[0]

    fuel_typical_df = (
        forward_filled_columns_payment_method_table_df[fuel_columns].loc[start_typical_consumption_index:, :].reset_index(drop=True)
    )
    fuel_typical_df.columns = fuel_typical_df.iloc[0]
    fuel_typical_df = fuel_typical_df.iloc[1:]
    fuel_typical_df = fuel_typical_df.rename(columns={"Typical consumption": "Tariff component"})
    fuel_typical_df["Payment method"] = PAYMENT_METHOD_LOOKUP.get(payment_method)
    fuel_typical_df["Consumption"] = "Typical consumption"
    fuel_typical_df["Fuel"] = fuel
    return fuel_typical_df


MELTED_NIL_DF_MAP = {
    _construct_node_name(fuel, payment, "melted_nil_consumption_df"): {
        "fuel_nil_consumption_df": source(_construct_node_name(fuel, payment, "nil_consumption_df")),
    }
    for payment in PAYMENT_KEYS
    for fuel in FUEL_KEYS
}


@parameterize(**MELTED_NIL_DF_MAP)
def melted_fuel_nil_consumption_df(
    fuel_nil_consumption_df: pd.DataFrame,
) -> pd.DataFrame:
    """Convert the nil consumption tariff table to long (tidy) format.

    Args:
        fuel_nil_consumption_df (pd.DataFrame): Nil consumption tariff table.

    Returns:
        pd.DataFrame: Melted DataFrame with charge restriction periods as rows.
    """
    return fuel_nil_consumption_df.melt(
        id_vars=["Payment method", "Fuel", "Consumption", "Tariff component"],
        var_name="28AD Charge Restriction Period",
    )


MELTED_TYPICAL_DF_MAP = {
    _construct_node_name(fuel, payment, "melted_typical_consumption_df"): {
        "fuel_typical_consumption_df": source(_construct_node_name(fuel, payment, "typical_consumption_df")),
    }
    for payment in PAYMENT_KEYS
    for fuel in FUEL_KEYS
}


@parameterize(**MELTED_TYPICAL_DF_MAP)
def melted_fuel_typical_consumption_df(
    fuel_typical_consumption_df: pd.DataFrame,
) -> pd.DataFrame:
    """Convert the typical consumption tariff table to long (tidy) format.

    Args:
        fuel_typical_consumption_df (pd.DataFrame): Typical consumption tariff table.

    Returns:
        pd.DataFrame: Melted DataFrame with charge restriction periods as rows.
    """
    return fuel_typical_consumption_df.melt(
        id_vars=["Payment method", "Fuel", "Consumption", "Tariff component"],
        var_name="28AD Charge Restriction Period",
    )


TIDY_DF_MAP = {
    _construct_node_name(fuel, payment, "tidy_df"): {
        "melted_fuel_nil_consumption_df": source(_construct_node_name(fuel, payment, "melted_nil_consumption_df")),
        "melted_fuel_typical_consumption_df": source(_construct_node_name(fuel, payment, "melted_typical_consumption_df")),
    }
    for payment in PAYMENT_KEYS
    for fuel in FUEL_KEYS
}


@parameterize(**TIDY_DF_MAP)
def fuel_payment_method_tidy_df(
    melted_fuel_nil_consumption_df: pd.DataFrame,
    melted_fuel_typical_consumption_df: pd.DataFrame,
) -> pd.DataFrame:
    """Combine nil and typical consumption tables into a single tidy dataset.

    Args:
        melted_fuel_nil_consumption_df (pd.DataFrame): Melted nil consumption data.
        melted_fuel_typical_consumption_df (pd.DataFrame): Melted typical consumption data.

    Returns:
        pd.DataFrame: Combined tidy DataFrame for a fuel and payment method.
    """
    return pd.concat([melted_fuel_nil_consumption_df, melted_fuel_typical_consumption_df]).dropna(subset={"Tariff component"})


def all_tariff_tables_tidy_df(
    electricity_single_rate_other_payment_method_tidy_df: pd.DataFrame,
    electricity_multi_register_other_payment_method_tidy_df: pd.DataFrame,
    gas_other_payment_method_tidy_df: pd.DataFrame,
    dual_fuel_other_payment_method_tidy_df: pd.DataFrame,
    electricity_single_rate_standard_credit_tidy_df: pd.DataFrame,
    electricity_multi_register_standard_credit_tidy_df: pd.DataFrame,
    gas_standard_credit_tidy_df: pd.DataFrame,
    dual_fuel_standard_credit_tidy_df: pd.DataFrame,
    electricity_single_rate_ppm_tidy_df: pd.DataFrame,
    electricity_multi_register_ppm_tidy_df: pd.DataFrame,
    gas_ppm_tidy_df: pd.DataFrame,
    dual_fuel_ppm_tidy_df: pd.DataFrame,
) -> pd.DataFrame:
    """Concatenate all fuel and payment method tariff tables into a single dataset.

    Returns:
        pd.DataFrame: Unified tidy DataFrame containing all tariff table entries.
    """
    all_dfs = {
        "electricity_single_rate_other_payment_method": electricity_single_rate_other_payment_method_tidy_df,
        "electricity_multi_register_other_payment_method": electricity_multi_register_other_payment_method_tidy_df,
        "gas_other_payment_method": gas_other_payment_method_tidy_df,
        "dual_fuel_other_payment_method": dual_fuel_other_payment_method_tidy_df,
        "electricity_single_rate_standard_credit": electricity_single_rate_standard_credit_tidy_df,
        "electricity_multi_register_standard_credit": electricity_multi_register_standard_credit_tidy_df,
        "gas_standard_credit": gas_standard_credit_tidy_df,
        "dual_fuel_standard_credit": dual_fuel_standard_credit_tidy_df,
        "electricity_single_rate_ppm": electricity_single_rate_ppm_tidy_df,
        "electricity_multi_register_ppm": electricity_multi_register_ppm_tidy_df,
        "gas_ppm": gas_ppm_tidy_df,
        "dual_fuel_ppm": dual_fuel_ppm_tidy_df,
    }

    empty = [name for name, df in all_dfs.items() if df.empty]
    if empty:
        raise ValueError(f"Tariff table(s) are empty: {empty}")

    return pd.concat(all_dfs.values(), ignore_index=True)


@extract_columns(
    "28AD Charge Restriction Period start",
    "28AD Charge Restriction Period end",
    "28AD Charge Restriction Period interval",
)
def charge_restriction_period_dates(
    all_tariff_tables_tidy_df: pd.DataFrame,
) -> pd.DataFrame:
    """Parse charge restriction period strings into interval and date columns.

    Args:
        all_tariff_tables_tidy_df (pd.DataFrame): Combined tariff tables dataset.

    Returns:
        pd.DataFrame: DataFrame containing start date, end date, and interval columns.

    Raises:
        ValueError: If the expected charge restriction period column is missing.
    """
    col = "28AD Charge Restriction Period"
    if col not in all_tariff_tables_tidy_df.columns:
        raise ValueError(f"Expected column '{col}' not found in tariff tables dataframe.")

    intervals = all_tariff_tables_tidy_df[col].apply(utils.convert_energy_price_cap_charge_restriction_period_string_to_interval)

    return pd.DataFrame(
        {
            "28AD Charge Restriction Period start": intervals.apply(lambda x: x.left).dt.normalize(),
            "28AD Charge Restriction Period end": intervals.apply(lambda x: x.right).dt.normalize(),
            "28AD Charge Restriction Period interval": intervals,
        },
        index=all_tariff_tables_tidy_df.index,
    )


@check_output(schema=SILVER_1C_CONSUMPTION_ADJUSTED_LEVELS_SCHEMA, importance="fail")
def all_tariff_tables_tidy_with_metadata_df(
    all_tariff_tables_tidy_df: pd.DataFrame,
    charge_restriction_period_dates: pd.DataFrame,
    bronze_energy_price_cap_annex_9_metadata: dict[str, str],
    sheet_name: str,
) -> pd.DataFrame:
    """Add parsed dates and metadata to the tidy tariff tables dataset.

    Ensures the dataset conforms to the SILVER_1C_CONSUMPTION_ADJUSTED_LEVELS_SCHEMA.

    Returns:
        pd.DataFrame: Validated silver-layer tariff tables dataset.
    """
    df = all_tariff_tables_tidy_df.copy()

    for col_name, series in charge_restriction_period_dates.items():
        df[col_name] = series

    # add a new field to metadata
    silver_energy_price_cap_annex_9_metadata = bronze_energy_price_cap_annex_9_metadata.copy()
    silver_energy_price_cap_annex_9_metadata["excel_sheet_name"] = sheet_name
    # TODO add sheet_name to human-readable citation field

    df["metadata"] = [silver_energy_price_cap_annex_9_metadata] * len(df)

    # Non-numeric values (e.g. blank cells) are coerced to NaN intentionally;
    # nullable=True in SILVER_1C_CONSUMPTION_ADJUSTED_LEVELS_SCHEMA allows these through
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    string_cols = [
        "Payment method",
        "Fuel",
        "Consumption",
        "Tariff component",
        "28AD Charge Restriction Period",
    ]
    for col in string_cols:
        if col in df.columns:
            df[col] = df[col].astype(str)
    return df


def silver_energy_price_cap_annex_9_1c_consumption_adjusted_levels_parquet(
    all_tariff_tables_tidy_with_metadata_df: pd.DataFrame,
    dataset_prefix: str,
    latest_price_cap_period: str,
    sheet_name: str,
) -> None:
    """Persist the silver-layer 1c Consumption adjusted levels dataset to storage as a parquet file."""
    price_cap_period_prefix = f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}"
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=all_tariff_tables_tidy_with_metadata_df,
        df_name=sheet_name.lower().replace(" ", "_"),
        date_stamp=price_cap_period_prefix,
    )

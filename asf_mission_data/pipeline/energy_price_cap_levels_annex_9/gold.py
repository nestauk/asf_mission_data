"""Hamilton nodes for gold-layer of the Energy Price Cap Levels Annex 9 pipeline."""

import logging

import numpy as np
import pandas as pd
from hamilton.function_modifiers import (
    check_output,
    check_output_custom,
)

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import BENCHMARK_CONSUMPTION, COMPONENT_CATEGORY_MAP, VAT
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.schemas import (
    GOLD_1C_CONSUMPTION_ADJUSTED_LEVELS_WITH_VAT_SCHEMA,
    GOLD_ANNUAL_BILL_FIXED_AND_VARIABLE_COMPONENT_CONTRIBUTIONS_SCHEMA,
    GOLD_PRICE_RATIOS_SCHEMA,
    GOLD_TARIFF_COMPONENT_RATES_SCHEMA,
)
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.validators import (
    TariffComponentsTotalValidator,
)

logger = logging.getLogger(__name__)

# ----------------------------------
# Common gold nodes
# ----------------------------------


def silver_energy_price_cap_annex_9_dataset(dataset_prefix: str, silver_table_prefix: str) -> str:
    """Latest silver-level dataset for Energy Price Cap Annex 9."""
    return storage.locate_latest(dataset_prefix, silver_table_prefix, "silver")


def silver_df(silver_energy_price_cap_annex_9_dataset: str) -> pd.DataFrame:
    """Silver Annex 9 dataset loaded as pandas DataFrame."""
    return storage.read_parquet(silver_energy_price_cap_annex_9_dataset)


def latest_price_cap_period(silver_df: pd.DataFrame) -> str:
    """Latest price cap period from the silver DataFrame metadata."""
    metadata_dict = silver_df["metadata"].iloc[0]
    period = metadata_dict.get("price_cap_period")
    if not period:
        raise KeyError("'price_cap_period' missing from silver metadata.")
    return period


# -------------------------------------------------------------
# Gold dataset: Nil and typical consumption components including VAT
# -------------------------------------------------------------


@check_output_custom(
    TariffComponentsTotalValidator(
        value_col="value",
        group_cols=[
            "Consumption",
            "Fuel",
            "Payment method",
            "28AD Charge Restriction Period start",
        ],
    )
)
def consumption_adjusted_levels_with_vat_df(
    silver_df: pd.DataFrame,
) -> pd.DataFrame:
    """Add VAT as a tariff component and uprate the total values to include VAT.

    This function derives VAT-inclusive tariff values from the silver dataset, and
    creates a new tariff component representing VAT (calculated as 5% of the
    `Total_GB average` component) and adds it as a separate row. It also uprates
    the `Total_GB average` values so that they include VAT.

    Args:
        silver_df (pd.DataFrame): Silver-layer Annex 9 DataFrame containing tariff
            components, consumption levels, and annual values before VAT
            adjustments.

    Returns:
        pd.DataFrame: DataFrame containing the original tariff components,
        VAT as a separate component, and updated `Total_GB average` values
        that include VAT.
    """

    # Add VAT as individual tariff component
    if not silver_df["Tariff component"].eq("Total_GB average").any():
        raise ValueError("Expected tariff component 'Total_GB average' not found in silver_df.")

    vat_rows = silver_df[silver_df["Tariff component"] == "Total_GB average"].copy()
    vat_rows["Tariff component"] = "VAT"
    vat_rows["value"] *= VAT

    # Uprate Total_GB average to include VAT
    uprated_silver_df = silver_df.copy()

    uprated_silver_df.loc[
        (uprated_silver_df["Tariff component"] == "Total_GB average"),
        "value",
    ] *= 1 + VAT

    # Remove now redundant "Total inc VAT" rows that were present only in the Dual fuel table
    uprated_silver_df = uprated_silver_df[uprated_silver_df["Tariff component"] != "Total inc VAT"]

    return pd.concat([uprated_silver_df, vat_rows], ignore_index=True)


@check_output(
    schema=GOLD_1C_CONSUMPTION_ADJUSTED_LEVELS_WITH_VAT_SCHEMA,
    importance="fail",
)
def gold_1c_consumption_adjusted_levels_with_vat_df(
    consumption_adjusted_levels_with_vat_df: pd.DataFrame,
    silver_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create the gold-layer dataset for consumption-adjusted tariff levels including VAT.

    Prepares final gold dataframe by attaching the metadata from the silver dataset to
    every row in a `metadata` column.

    Args:
        consumption_adjusted_levels_with_vat_df (pd.DataFrame): DataFrame containing the
        original tariff components, VAT as a separate component, and updated `Total_GB average`
        values that include VAT.
        silver_df (pd.DataFrame): Original silver-layer dataframe containing metadata
        in a `metadata` column, to be propagated to the gold dataset.

    Returns:
        pd.DataFrame: Gold-layer DataFrame containing consumption-adjusted
        tariff levels with VAT, component categories and associated metadata.
    """
    df = consumption_adjusted_levels_with_vat_df.copy()

    # Add component category column
    df["Component category"] = df["Tariff component"].map(COMPONENT_CATEGORY_MAP)

    # Add metadata
    df["metadata"] = [silver_df["metadata"][0]] * len(df)

    # Add change from previous price cap period
    df = df.sort_values("28AD Charge Restriction Period start")
    df["change_from_previous_period"] = df.groupby(["Tariff component", "Fuel", "Payment method", "Consumption"])["value"].diff()
    df["pct_change_from_previous_period"] = (
        df.groupby(["Tariff component", "Fuel", "Payment method", "Consumption"])["value"].pct_change().mul(100).round(2)
    )

    return df


def gold_1c_consumption_adjusted_levels_with_vat_parquet(
    gold_1c_consumption_adjusted_levels_with_vat_df: pd.DataFrame,
    dataset_prefix: str,
    latest_price_cap_period: str,
) -> None:
    """Persist the gold-layer consumption-adjusted tariff levels with VAT as a parquet file."""
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_1c_consumption_adjusted_levels_with_vat_df,
        df_name="1c_consumption_adjusted_levels_with_vat",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )


# -------------------------------------------------------------
# Gold dataset: Unit prices and standing charges by component, standardised units
# -------------------------------------------------------------


@check_output_custom(
    TariffComponentsTotalValidator(
        value_col="value",
        group_cols=[
            "Fuel",
            "Payment method",
            "28AD Charge Restriction Period start",
            "Type",
        ],
    )
)
def tariff_component_rates_df(
    consumption_adjusted_levels_with_vat_df: pd.DataFrame,
) -> pd.DataFrame:
    """Calculate standing charges and unit rates for tariff components.

    The input dataset contains VAT-adjusted annual tariff component values for
    two consumption levels: "Nil consumption" and "Typical consumption". For
    each fuel, the data is pivoted to separate these values and used to derive:

    - Standing charge (p/day): from the nil consumption annual value.
    - Unit price (p/kWh): from the difference between typical and nil
      consumption values divided by the benchmark annual consumption for the
      fuel.

    Benchmark consumption values are taken from ``BENCHMARK_CONSUMPTION``.

    Args:
        consumption_adjusted_levels_with_vat_df (pd.DataFrame): DataFrame
            containing tariff component values with VAT applied.

    Returns:
        pd.DataFrame: Long-format DataFrame containing standing charges and
        unit prices by fuel, payment method, tariff component, and price cap
        period, with columns ``Type``, ``Unit``, and ``value``.
    """

    expected_fuels = set(BENCHMARK_CONSUMPTION.keys())
    found_fuels = set(consumption_adjusted_levels_with_vat_df["Fuel"].unique())
    missing_fuels = expected_fuels - found_fuels
    if missing_fuels:
        raise ValueError(f"Expected fuel(s) not found in data: {missing_fuels}. Found fuels: {found_fuels}.")

    index_cols = [
        "Payment method",
        "Fuel",
        "Tariff component",
        "28AD Charge Restriction Period",
        "28AD Charge Restriction Period start",
        "28AD Charge Restriction Period end",
    ]

    dfs = []

    for fuel, benchmark in BENCHMARK_CONSUMPTION.items():
        fuel_df = consumption_adjusted_levels_with_vat_df.loc[consumption_adjusted_levels_with_vat_df["Fuel"] == fuel]

        pivoted = (
            fuel_df.pivot_table(
                index=index_cols,
                columns="Consumption",
                values="value",
            )
            .rename_axis(None, axis=1)
            .reset_index()
        )

        expected_consumption_cols = {"Nil consumption", "Typical consumption"}
        missing_consumption_cols = expected_consumption_cols - set(pivoted.columns)
        if missing_consumption_cols:
            raise ValueError(f"Expected consumption column(s) missing after pivot for fuel '{fuel}': {missing_consumption_cols}.")

        melted = (
            pivoted.assign(
                standing_charge=pivoted["Nil consumption"] * 100 / 365,  # £/year to p/day
                unit_price=((pivoted["Typical consumption"] - pivoted["Nil consumption"].fillna(0)) / benchmark) * 0.1,  # £/MWh to p/kWh
            )
            .drop(columns=["Nil consumption", "Typical consumption"])
            .fillna({"standing_charge": 0, "unit_price": 0})
            .melt(
                id_vars=index_cols,
                value_vars=["standing_charge", "unit_price"],
                var_name="Type",
                value_name="value",
            )
        )

        melted["Type"] = melted["Type"].replace({"standing_charge": "Standing charge", "unit_price": "Unit price"})

        melted["Unit"] = melted["Type"].map({"Standing charge": "p/day", "Unit price": "p/kWh"})

        dfs.append(melted)

    return pd.concat(dfs, ignore_index=True)


@check_output(schema=GOLD_TARIFF_COMPONENT_RATES_SCHEMA, importance="fail")
def gold_tariff_component_rates_df(
    silver_df: pd.DataFrame,
    tariff_component_rates_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create the gold-layer dataset for standing charge and unit rates for
    each component.

    Prepares final gold dataframe by attaching the metadata from the silver dataset to
    every row in a `metadata` column.

    Args:
        silver_df (pd.DataFrame): Original silver-layer dataframe containing metadata
            in a `metadata` column, to be propagated to the gold dataset.
        tariff_component_rates_df (pd.DataFrame): Processed DataFrame containing tariff
            components with calculated standing charges (p/day) and unit prices (p/kWh) for each fuel,
            payment method, and price cap period.

    Returns:
        pd.DataFrame: Gold-layer DataFrame containing standing charge and unit rates for
            each component and component category, and associated metadata.
    """
    df = tariff_component_rates_df.copy()

    # Add component category column
    df["Component category"] = df["Tariff component"].map(COMPONENT_CATEGORY_MAP)

    # Add metadata
    df["metadata"] = [silver_df["metadata"][0]] * len(df)

    # Add change from previous price cap period
    df = df.sort_values("28AD Charge Restriction Period start")
    df["change_from_previous_period"] = df.groupby(["Tariff component", "Fuel", "Payment method", "Type"])["value"].diff()
    df["pct_change_from_previous_period"] = (
        df.groupby(["Tariff component", "Fuel", "Payment method", "Type"])["value"].pct_change().mul(100).round(2)
    )

    return df


def gold_tariff_component_rates_parquet(
    gold_tariff_component_rates_df: pd.DataFrame,
    dataset_prefix: str,
    latest_price_cap_period: str,
) -> None:
    """Persist the gold-layer standing charge and unit rates for each component
    as a parquet file."""
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_tariff_component_rates_df,
        df_name="tariff_component_rates",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )


# -------------------------------------------------------------
# Gold dataset: Electricity to gas price ratios
# -------------------------------------------------------------


def total_unit_rates_df(
    tariff_component_rates_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract total unit prices for gas and electricity and reshape them for comparison.

    This function filters the tariff component rates to retain only the
    `Total_GB average` component for gas and single-rate electricity. It then
    pivots the data so that the unit prices for each fuel appear as separate
    columns.

    Args:
        tariff_component_rates_df (pd.DataFrame): DataFrame containing standing
            charges and unit prices (p/kWh) for each tariff component, fuel,
            payment method, and price cap period.

    Returns:
        pd.DataFrame: DataFrame with unit prices for gas and single-rate
        electricity in separate columns for each payment method and
        price cap period.
    """
    expected_fuels = {"Gas", "Electricity: Single-Rate Metering Arrangement"}
    found_fuels = set(tariff_component_rates_df["Fuel"].unique())
    missing = expected_fuels - found_fuels
    if missing:
        raise ValueError(f"Missing fuels in tariff_component_rates_df: {missing}. Found fuels: {found_fuels}.")

    totals_df = tariff_component_rates_df[
        (tariff_component_rates_df["Tariff component"] == "Total_GB average")
        & (tariff_component_rates_df["Fuel"].isin(["Gas", "Electricity: Single-Rate Metering Arrangement"]))
        & (tariff_component_rates_df["Type"] == "Unit price")
    ].copy()

    pivoted = (
        totals_df.pivot_table(
            index=[
                "Payment method",
                "28AD Charge Restriction Period",
                "28AD Charge Restriction Period start",
                "28AD Charge Restriction Period end",
            ],
            columns="Fuel",
            values="value",
        )
        .rename(
            columns={
                "Electricity: Single-Rate Metering Arrangement": "Electricity (single rate) unit price",
                "Gas": "Gas unit price",
            }
        )
        .reset_index()
    )

    return pivoted


@check_output(schema=GOLD_PRICE_RATIOS_SCHEMA, importance="fail")
def gold_price_ratios_df(total_unit_rates_df: pd.DataFrame, silver_df: pd.DataFrame) -> pd.DataFrame:
    """Create the gold dataset of electricity-to-gas unit price ratios.

    Computes the ratio of electricity unit price to gas unit price for each
    payment method and price cap period. Metadata from the silver dataset
    is propagated to all rows.

    Args:
        total_unit_rates_df (pd.DataFrame): Electricity and gas unit prices by
            payment method and price cap period.
        silver_df (pd.DataFrame): Silver-layer dataframe containing a `metadata`
            column to attach to the output.

    Returns:
        pd.DataFrame: Dataset containing electricity-to-gas price ratios and
        associated metadata.
    """
    pivoted = total_unit_rates_df.copy()

    # Gas unit price may be zero in edge cases
    # Replace the resulting inf with NaN so downstream charts skip the value
    # rather than rendering a misleading spike
    pivoted["value"] = (pivoted["Electricity (single rate) unit price"] / pivoted["Gas unit price"]).replace([np.inf, -np.inf], np.nan)

    id_cols = [
        "Payment method",
        "28AD Charge Restriction Period",
        "28AD Charge Restriction Period start",
        "28AD Charge Restriction Period end",
    ]

    df = pivoted[id_cols + ["value"]].copy()

    df["Variable"] = "Electricity to gas price ratio"
    df["metadata"] = [silver_df["metadata"][0]] * len(df)

    # Add change from previous price cap period
    df = df.sort_values("28AD Charge Restriction Period start")
    df["change_from_previous_period"] = df.groupby(["Payment method"])["value"].diff()
    df["pct_change_from_previous_period"] = df.groupby(["Payment method"])["value"].pct_change().mul(100).round(2)

    return df.reset_index(drop=True)


def gold_price_ratios_parquet(
    gold_price_ratios_df: pd.DataFrame,
    dataset_prefix: str,
    latest_price_cap_period: str,
) -> None:
    """Persist the gold-layer dataset for electricity-to-gas price ratios as a parquet file."""
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_price_ratios_df,
        df_name="price_ratios",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )


# -------------------------------------------------------------
# Gold dataset: Annual fuel bill breakdown by standing charge vs. consumption-based charge
# -------------------------------------------------------------


@check_output_custom(
    TariffComponentsTotalValidator(
        value_col="value",
        group_cols=[
            "Fuel",
            "Payment method",
            "28AD Charge Restriction Period start",
            "Type",
        ],
    )
)
def annual_bill_fixed_and_variable_contributions_df(
    consumption_adjusted_levels_with_vat_df: pd.DataFrame,
) -> pd.DataFrame:
    """Derive annual fixed and variable bill contributions for tariff components.

    The input dataset contains VAT-adjusted annual tariff component values for
    two consumption levels: "Nil consumption" and "Typical consumption". For
    each fuel, the data is pivoted to separate these values and used to derive:

    - Standing charge (GBP/year): the nil consumption annual value.
    - Consumption-based cost (GBP/year): the difference between typical and
      nil consumption values.

    Args:
        consumption_adjusted_levels_with_vat_df (pd.DataFrame): DataFrame
            containing tariff component values with VAT applied for nil and
            typical consumption levels.

    Returns:
        pd.DataFrame: Long DataFrame containing annual standing charge
        and consumption-based cost contributions by fuel, payment method,
        tariff component, and price cap period, with columns ``Type``,
        ``Unit`` ("GBP/year"), and ``value``.
    """

    expected_fuels = set(BENCHMARK_CONSUMPTION.keys())
    found_fuels = set(consumption_adjusted_levels_with_vat_df["Fuel"].unique())
    missing_fuels = expected_fuels - found_fuels
    if missing_fuels:
        raise ValueError(f"Expected fuel(s) not found in data: {missing_fuels}. Found fuels: {found_fuels}.")

    index_cols = [
        "Payment method",
        "Fuel",
        "Tariff component",
        "28AD Charge Restriction Period",
        "28AD Charge Restriction Period start",
        "28AD Charge Restriction Period end",
    ]

    dfs = []

    for fuel in BENCHMARK_CONSUMPTION.keys():
        fuel_df = consumption_adjusted_levels_with_vat_df.loc[consumption_adjusted_levels_with_vat_df["Fuel"] == fuel]

        pivoted = (
            fuel_df.pivot_table(
                index=index_cols,
                columns="Consumption",
                values="value",
            )
            .rename_axis(None, axis=1)
            .reset_index()
        )

        expected_consumption_cols = {"Nil consumption", "Typical consumption"}
        missing_consumption_cols = expected_consumption_cols - set(pivoted.columns)
        if missing_consumption_cols:
            raise ValueError(f"Expected consumption column(s) missing after pivot for fuel '{fuel}': {missing_consumption_cols}.")

        melted = (
            pivoted.assign(
                standing_charge=pivoted["Nil consumption"].fillna(0),
                consumption_based_cost=(pivoted["Typical consumption"] - pivoted["Nil consumption"].fillna(0)),
            )
            .drop(columns=["Nil consumption", "Typical consumption"])
            .fillna({"standing_charge": 0, "consumption_based_cost": 0})
            .melt(
                id_vars=index_cols,
                value_vars=["standing_charge", "consumption_based_cost"],
                var_name="Type",
                value_name="value",
            )
        )

        melted["Type"] = melted["Type"].replace(
            {
                "standing_charge": "Standing charge",
                "consumption_based_cost": "Consumption-based cost",
            }
        )

        melted["Unit"] = "GBP/year"

        dfs.append(melted)

    return pd.concat(dfs, ignore_index=True)


@check_output(
    schema=GOLD_ANNUAL_BILL_FIXED_AND_VARIABLE_COMPONENT_CONTRIBUTIONS_SCHEMA,
    importance="fail",
)
def gold_annual_bill_fixed_and_variable_component_contributions_df(
    annual_bill_fixed_and_variable_contributions_df: pd.DataFrame,
    silver_df: pd.DataFrame,
) -> pd.DataFrame:
    """Create the gold dataset for annual bill fixed and variable cost contributions.

    This function prepares the final gold-layer DataFrame by copying the
    calculated annual bill contributions and attaching the metadata from the
    silver dataset to each row.

    Args:
        annual_bill_fixed_and_variable_contributions_df (pd.DataFrame): DataFrame containing
            tariff components with annual standing charge contributions and consumption-based
            cost contributions for each fuel, payment method, and price cap period.
        silver_df (pd.DataFrame): Original silver-layer dataframe containing metadata
            in a `metadata` column, to be propagated to the gold dataset.

    Returns:
        pd.DataFrame: Gold-layer DataFrame containing annual bill fixed and
            variable component and component category contributions along with associated metadata.
    """
    df = annual_bill_fixed_and_variable_contributions_df.copy()

    # Add component category column
    df["Component category"] = df["Tariff component"].map(COMPONENT_CATEGORY_MAP)

    # Add metadata
    df["metadata"] = [silver_df["metadata"][0]] * len(df)

    # Add change from previous price cap period
    df = df.sort_values("28AD Charge Restriction Period start")
    df["change_from_previous_period"] = df.groupby(["Tariff component", "Fuel", "Payment method", "Type"])["value"].diff()
    df["pct_change_from_previous_period"] = (
        df.groupby(["Tariff component", "Fuel", "Payment method", "Type"])["value"].pct_change().mul(100).round(2)
    )

    return df


def gold_annual_bill_fixed_and_variable_component_contributions_parquet(
    gold_annual_bill_fixed_and_variable_component_contributions_df: pd.DataFrame,
    dataset_prefix: str,
    latest_price_cap_period: str,
) -> None:
    """Persist the gold-layer dataset for gas and electricity unit prices, electricity-to-gas price ratios
    as a parquet file."""
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_annual_bill_fixed_and_variable_component_contributions_df,
        df_name="annual_bill_fixed_and_variable_component_contributions",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )

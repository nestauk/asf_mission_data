"""Hamilton nodes for gold-layer of the Energy Price Cap Levels Annex 9 pipeline"""

import logging

import pandas as pd
from hamilton.function_modifiers import (
    check_output,
    check_output_custom,
)

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.schemas import (
    GOLD_1C_CONSUMPTION_ADJUSTED_LEVELS_WITH_VAT_SCHEMA,
    GOLD_ANNUAL_BILL_FIXED_AND_VARIABLE_COMPONENT_CONTRIBUTIONS_SCHEMA,
    GOLD_TARIFF_COMPONENT_RATES_SCHEMA,
    GOLD_TOTAL_UNIT_RATES_WITH_RATIOS_SCHEMA,
)
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.validators import TariffComponentsTotalValidator

logger = logging.getLogger(__name__)

# ----------------------------------
# Common gold nodes
# ----------------------------------


def silver_energy_price_cap_annex_9_dataset(dataset_prefix: str, silver_table_prefix: str) -> str:
    """Locate the latest silver-level dataset for Energy Price Cap Annex 9.

    Args:
        dataset_prefix (str): Prefix identifying dataset in storage.
        silver_table_prefix (str): Prefix identifying the silver dataset in storage.

    Returns:
        str: URI or file path to the latest Annex 9 silver dataset.
    """
    return storage.locate_latest_silver(dataset_prefix, silver_table_prefix)


def silver_df(silver_energy_price_cap_annex_9_dataset: str) -> pd.DataFrame:
    """Read Annex 9 dataset into a pandas DataFrame.

    Args:
        silver_energy_price_cap_annex_9_dataset (str): URI or file path to the latest Annex 9 silver dataset.

    Returns:
        pd.DataFrame: Annex 9 silver level dataframe.
    """
    return storage.read_parquet(silver_energy_price_cap_annex_9_dataset)


def latest_price_cap_period(silver_df: pd.DataFrame) -> str:
    """Extract the latest price cap period from the silver DataFrame metadata.

    Args:
        silver_df (pd.DataFrame): Annex 9 silver level dataframe.

    Returns:
        str: Latest price cap period string.
    """
    metadata_dict = silver_df["metadata"][0]
    return metadata_dict.get("price_cap_period")


# -------------------------------------------------------------
# Gold dataset: Nil and typical consumption components including VAT
# -------------------------------------------------------------


@check_output_custom(
    TariffComponentsTotalValidator(
        value_col="value",
        group_cols=["Consumption", "Fuel", "Payment method", "28AD Charge Restriction Period start"],
    )
)
def consumption_adjusted_levels_with_vat_df(silver_df: pd.DataFrame) -> pd.DataFrame:
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
    VAT = 0.05  # TODO move to config

    # Add VAT as individual tariff component
    vat_rows = silver_df[silver_df["Tariff component"] == "Total_GB average"].copy()
    vat_rows["Tariff component"] = "VAT"
    vat_rows["value"] *= VAT

    # Uprate Total_GB average to include VAT
    uprated_silver_df = silver_df.copy()

    uprated_silver_df.loc[
        (uprated_silver_df["Tariff component"] == "Total_GB average"),
        "value",
    ] *= 1 + VAT

    # Remove now redundant "Total inc VAT" rows for Dual fuel
    uprated_silver_df = uprated_silver_df[uprated_silver_df["Tariff component"] != "Total inc VAT"]

    return pd.concat([uprated_silver_df, vat_rows], ignore_index=True)


@check_output(schema=GOLD_1C_CONSUMPTION_ADJUSTED_LEVELS_WITH_VAT_SCHEMA, importance="fail")
def gold_1c_consumption_adjusted_levels_with_vat_df(
    consumption_adjusted_levels_with_vat_df: pd.DataFrame, silver_df: pd.DataFrame
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
        tariff levels with VAT and associated metadata.
    """
    df = consumption_adjusted_levels_with_vat_df.copy()
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df


def gold_1c_consumption_adjusted_levels_with_vat_parquet(
    gold_1c_consumption_adjusted_levels_with_vat_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str
) -> None:
    """Persist the gold-layer consumption-adjusted tariff levels with VAT as a parquet file.

    This function ingests the prepared gold DataFrame into the gold storage
    layer as a parquet dataset. The dataset is stored under `/latest` and a
    `/historical` period-based partition derived from the latest price cap period.

    Args:
        gold_1c_consumption_adjusted_levels_with_vat_df (pd.DataFrame): Gold-layer
            DataFrame containing consumption-adjusted tariff levels including VAT.
        dataset_prefix (str): Dataset identifier used to namespace storage.
        latest_price_cap_period (str): Period used to timestamp the dataset.
    """
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_1c_consumption_adjusted_levels_with_vat_df,
        df_name="1c_consumption_adjusted_levels_with_vat",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )


# -------------------------------------------------------------
# Gold dataset: Unit prices and standing charges by component, standardised units
# -------------------------------------------------------------

# TODO move to config MWh per year
BENCHMARK_CONSUMPTION = {
    "Gas": 11.5,
    "Electricity: Single-Rate Metering Arrangement": 2.7,
    "Electricity: Multi-Register Metering Arrangement": 3.9,
}


@check_output_custom(
    TariffComponentsTotalValidator(
        value_col="value",
        group_cols=["Fuel", "Payment method", "28AD Charge Restriction Period start", "Type"],
    )
)
def tariff_component_rates_df(consumption_adjusted_levels_with_vat_df: pd.DataFrame) -> pd.DataFrame:
    """Derive standing charges and unit rates for each tariff component.

    This function converts annual tariff component values into standardised
    standing charges (p/day) and unit prices (p/kWh). It does this by pivoting
    the VAT-adjusted dataset to separate "Nil consumption" and "Typical consumption"
    values, then calculating:
    - Standing charge: derived from the nil-consumption annual value.
    - Unit price: derived from the difference between typical and nil consumption
      values divided by benchmark annual consumption for the fuel type.

    The calculation is performed separately for each fuel type using predefined
    benchmark consumption values.

    Args:
        consumption_adjusted_levels_with_vat_df (pd.DataFrame): DataFrame containing the original
        tariff components, VAT as a separate component, and updated `Total_GB average` values
        that include VAT.

    Returns:
        pd.DataFrame: DataFrame containing tariff components with calculated
        standing charges (p/day) and unit prices (p/kWh) for each fuel,
        payment method, and price cap period.
    """
    dfs = []
    for fuel, benchmark in BENCHMARK_CONSUMPTION.items():
        fuel_df = consumption_adjusted_levels_with_vat_df[consumption_adjusted_levels_with_vat_df["Fuel"] == fuel].copy()

        if fuel_df.empty:
            continue

        pivoted_df = fuel_df.pivot_table(
            index=[
                "Payment method",
                "Fuel",
                "Tariff component",
                "28AD Charge Restriction Period",
                "28AD Charge Restriction Period start",
                "28AD Charge Restriction Period end",
            ],
            columns="Consumption",
            values="value",
        ).reset_index()

        pivoted_df.columns.name = None

        result = pivoted_df.assign(
            standing_charge=pivoted_df["Nil consumption"] * 100 / 365,
            unit_price=((pivoted_df["Typical consumption"] - pivoted_df["Nil consumption"].fillna(0)) / benchmark) * 0.1,
        ).drop(columns=["Nil consumption", "Typical consumption"])

        result[["standing_charge", "unit_price"]] = result[["standing_charge", "unit_price"]].fillna(0)

        result = result.melt(
            id_vars=[
                "Payment method",
                "Fuel",
                "Tariff component",
                "28AD Charge Restriction Period",
                "28AD Charge Restriction Period start",
                "28AD Charge Restriction Period end",
            ],
            value_vars=["standing_charge", "unit_price"],
            var_name="Type",
            value_name="value",
        )

        result["Type"] = result["Type"].map(
            {
                "standing_charge": "Standing charge",
                "unit_price": "Unit price",
            }
        )

        result["Unit"] = result["Type"].map(
            {
                "Standing charge": "p/day",
                "Unit price": "p/kWh",
            }
        )

        dfs.append(result)

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
    each component and associated metadata.
    """
    df = tariff_component_rates_df.copy()
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df


def gold_tariff_component_rates_parquet(gold_tariff_component_rates_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str) -> None:
    """Persist the gold-layer standing charge and unit rates for each component
    as a parquet file.

    This function ingests the prepared gold DataFrame into the gold storage
    layer as a parquet dataset. The dataset is stored under `/latest` and a
    `/historical` period-based partition derived from the latest price cap period.

    Args:
        gold_tariff_component_rates_df (pd.DataFrame): Gold-layer DataFrame containing standing charge and unit rates for
            each component and associated metadata.
        dataset_prefix (str): Dataset identifier used to namespace storage.
        latest_price_cap_period (str): Period used to timestamp the dataset.
    """
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_tariff_component_rates_df,
        df_name="tariff_component_rates",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )


# -------------------------------------------------------------
# Gold dataset: Total unit prices and price ratios
# -------------------------------------------------------------


def total_unit_rates_df(tariff_component_rates_df: pd.DataFrame) -> pd.DataFrame:
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
    df_filtered = tariff_component_rates_df[
        (tariff_component_rates_df["Tariff component"] == "Total_GB average")
        & (tariff_component_rates_df["Fuel"].isin(["Gas", "Electricity: Single-Rate Metering Arrangement"]))
        & (tariff_component_rates_df["Type"] == "Unit price")
    ].copy()

    unit_price_pivot = (
        df_filtered.pivot_table(
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
                "Electricity: Single-Rate Metering Arrangement": "Electricity (single rate) unit price (p/kWh)",
                "Gas": "Gas unit price (p/kWh)",
            }
        )
        .reset_index()
    )

    return unit_price_pivot


@check_output(schema=GOLD_TOTAL_UNIT_RATES_WITH_RATIOS_SCHEMA, importance="fail")
def gold_total_unit_rates_with_ratios_df(total_unit_rates_df: pd.DataFrame, silver_df: pd.DataFrame) -> pd.DataFrame:
    """Create the gold dataset of total unit rates and electricity-to-gas price ratios.

    This function takes the pivoted unit rate dataset for gas and single-rate
    electricity, calculates the ratio of electricity unit prices to gas unit
    prices, and attaches the metadata from the silver dataset to each row.

    Args:
        total_unit_rates_df (pd.DataFrame): DataFrame with unit prices for gas and single-rate
            electricity in separate columns for each payment method and price cap period.
        silver_df (pd.DataFrame): silver_df (pd.DataFrame): Original silver-layer dataframe containing metadata
        in a `metadata` column, to be propagated to the gold dataset.

    Returns:
        pd.DataFrame: Gold-layer DataFrame containing gas and electricity unit prices, the
        calculated electricity-to-gas price ratio, and associated metadata.
    """
    df = total_unit_rates_df.copy()
    df["Electricity to gas price ratio"] = df["Electricity (single rate) unit price (p/kWh)"] / df["Gas unit price (p/kWh)"]
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df.reset_index(drop=True)


def gold_total_unit_rates_with_ratios_parquet(
    gold_total_unit_rates_with_ratios_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str
) -> None:
    """Persist the gold-layer dataset for gas and electricity unit prices, electricity-to-gas price ratios
    as a parquet file.

    This function ingests the prepared gold DataFrame into the gold storage
    layer as a parquet dataset. The dataset is stored under `/latest` and a
    `/historical` period-based partition derived from the latest price cap period.

    Args:
        gold_total_unit_rates_with_ratios_df (pd.DataFrame): Gold-layer DataFrame containing gas and electricity unit prices,
            the calculated electricity-to-gas price ratio, and associated metadata.
        dataset_prefix (str): Dataset identifier used to namespace storage.
        latest_price_cap_period (str): Period used to timestamp the dataset.
    """
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_total_unit_rates_with_ratios_df,
        df_name="total_unit_rates_with_ratios",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )


# -------------------------------------------------------------
# Gold dataset: Annual fuel bill breakdown by standing charge vs. consumption-based charge
# -------------------------------------------------------------


@check_output_custom(
    TariffComponentsTotalValidator(
        value_col="value",
        group_cols=["Fuel", "Payment method", "28AD Charge Restriction Period start", "Type"],
    )
)
def annual_bill_fixed_and_variable_contributions_df(consumption_adjusted_levels_with_vat_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate annual bill contributions from standing charges and consumption-based costs.

    This function derives the fixed and variable components of the annual
    energy bill for each tariff component. It pivots the VAT-adjusted dataset
    to separate "Nil consumption" and "Typical consumption" values and then
    calculates:
    - Standing charge (GBP/year): taken from the nil-consumption annual value,
      representing the fixed portion of the bill.
    - Consumption-based cost (GBP/year): calculated as the difference between
      the typical-consumption value and the standing charge, representing the
      variable portion of the bill.

    The calculation is performed separately for each fuel type defined in the
    benchmark consumption configuration.

    Args:
        consumption_adjusted_levels_with_vat_df (pd.DataFrame): DataFrame
            containing tariff components with VAT applied.

    Returns:
        pd.DataFrame: DataFrame containing tariff components with annual
        standing charge contributions and consumption-based cost contributions
        for each fuel, payment method, and price cap period.
    """
    dfs = []

    for fuel in BENCHMARK_CONSUMPTION.keys():
        fuel_df = consumption_adjusted_levels_with_vat_df[consumption_adjusted_levels_with_vat_df["Fuel"] == fuel].copy()

        if fuel_df.empty:
            continue

        fuel_df = fuel_df.pivot_table(
            index=[
                "Payment method",
                "Fuel",
                "Tariff component",
                "28AD Charge Restriction Period",
                "28AD Charge Restriction Period start",
                "28AD Charge Restriction Period end",
            ],
            columns="Consumption",
            values="value",
        ).reset_index()

        fuel_df.columns.name = None

        fuel_df = fuel_df.assign(
            standing_charge=fuel_df["Nil consumption"].fillna(0),
            consumption_based_cost=(fuel_df["Typical consumption"] - fuel_df["Nil consumption"].fillna(0)),
        ).drop(columns=["Nil consumption", "Typical consumption"])

        fuel_df[["standing_charge", "consumption_based_cost"]] = fuel_df[["standing_charge", "consumption_based_cost"]].fillna(0)

        fuel_df = fuel_df.melt(
            id_vars=[
                "Payment method",
                "Fuel",
                "Tariff component",
                "28AD Charge Restriction Period",
                "28AD Charge Restriction Period start",
                "28AD Charge Restriction Period end",
            ],
            value_vars=["standing_charge", "consumption_based_cost"],
            var_name="Type",
            value_name="value",
        )

        fuel_df["Type"] = fuel_df["Type"].map(
            {
                "standing_charge": "Standing charge",
                "consumption_based_cost": "Consumption-based cost",
            }
        )

        fuel_df["Unit"] = "GBP/year"

        dfs.append(fuel_df)

    return pd.concat(dfs, ignore_index=True)


@check_output(schema=GOLD_ANNUAL_BILL_FIXED_AND_VARIABLE_COMPONENT_CONTRIBUTIONS_SCHEMA, importance="fail")
def gold_annual_bill_fixed_and_variable_component_contributions_df(
    annual_bill_fixed_and_variable_contributions_df: pd.DataFrame, silver_df: pd.DataFrame
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
            variable component contributions along with associated metadata.
    """
    df = annual_bill_fixed_and_variable_contributions_df.copy()
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df


def gold_annual_bill_fixed_and_variable_component_contributions_parquet(
    gold_annual_bill_fixed_and_variable_component_contributions_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str
) -> None:
    """Persist the gold-layer dataset for gas and electricity unit prices, electricity-to-gas price ratios
    as a parquet file.

    This function ingests the prepared gold DataFrame into the gold storage
    layer as a parquet dataset. The dataset is stored under `/latest` and a
    `/historical` period-based partition derived from the latest price cap period.

    Args:
        gold_annual_bill_fixed_and_variable_component_contributions_df (pd.DataFrame): Gold-layer DataFrame
            containing annual bill fixed and variable component contributions along with associated metadata.
        dataset_prefix (str): Dataset identifier used to namespace storage.
        latest_price_cap_period (str): Period used to timestamp the dataset.
    """
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_annual_bill_fixed_and_variable_component_contributions_df,
        df_name="annual_bill_fixed_and_variable_component_contributions",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )

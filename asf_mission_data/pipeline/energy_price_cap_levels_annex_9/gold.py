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
    return storage.locate_latest_silver(dataset_prefix, silver_table_prefix)


def silver_df(silver_energy_price_cap_annex_9_dataset: str) -> pd.DataFrame:
    return storage.read_parquet(silver_energy_price_cap_annex_9_dataset)


def latest_price_cap_period(silver_df: pd.DataFrame) -> str:
    metadata_dict = silver_df["metadata"][0]
    return metadata_dict.get("price_cap_period")


# -------------------------------------------------------------
# Gold dataset: Nil and typical consumption components including VAT
# -------------------------------------------------------------


@check_output_custom(
    TariffComponentsTotalValidator(
        fixed_col="value",
        group_cols=["Consumption", "Fuel", "Payment method", "28AD Charge Restriction Period start"],
    )
)
def consumption_adjusted_levels_with_vat_df(silver_df: pd.DataFrame) -> pd.DataFrame:
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
    df = consumption_adjusted_levels_with_vat_df.copy()
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df


def gold_1c_consumption_adjusted_levels_with_vat_parquet(
    gold_1c_consumption_adjusted_levels_with_vat_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str
) -> None:

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
        fixed_col="Standing charge (p/day)",
        variable_col="Unit price (p/kWh)",
        group_cols=["Fuel", "Payment method", "28AD Charge Restriction Period start"],
    )
)
def tariff_component_rates_df(consumption_adjusted_levels_with_vat_df: pd.DataFrame) -> pd.DataFrame:

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
            **{
                "Standing charge (p/day)": pivoted_df["Nil consumption"] * 100 / 365,
                "Unit price (p/kWh)": ((pivoted_df["Typical consumption"] - pivoted_df["Nil consumption"].fillna(0)) / benchmark) * 0.1,
            }
        ).drop(columns=["Nil consumption", "Typical consumption"])

        result[["Standing charge (p/day)", "Unit price (p/kWh)"]] = result[["Standing charge (p/day)", "Unit price (p/kWh)"]].fillna(0)

        dfs.append(result)

    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()


@check_output(schema=GOLD_TARIFF_COMPONENT_RATES_SCHEMA, importance="fail")
def gold_tariff_component_rates_df(
    silver_df: pd.DataFrame,
    tariff_component_rates_df: pd.DataFrame,
) -> pd.DataFrame:
    df = tariff_component_rates_df.copy()
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df


def gold_tariff_component_rates_parquet(gold_tariff_component_rates_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str) -> None:

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

    df_filtered = tariff_component_rates_df[
        (tariff_component_rates_df["Tariff component"] == "Total_GB average")
        & (tariff_component_rates_df["Fuel"].isin(["Gas", "Electricity: Single-Rate Metering Arrangement"]))
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
            values="Unit price (p/kWh)",
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
    df = total_unit_rates_df.copy()
    df["Electricity to gas price ratio"] = df["Electricity (single rate) unit price (p/kWh)"] / df["Gas unit price (p/kWh)"]
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df.reset_index(drop=True)


def gold_total_unit_rates_with_ratios_parquet(
    gold_total_unit_rates_with_ratios_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str
) -> None:

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
        fixed_col="Standing charge (GBP/year)",
        variable_col="Consumption-based cost (GBP/year)",
        group_cols=["Fuel", "Payment method", "28AD Charge Restriction Period start"],
    )
)
def annual_bill_fixed_and_variable_contributions_df(consumption_adjusted_levels_with_vat_df: pd.DataFrame) -> pd.DataFrame:

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

        fuel_df["Standing charge (GBP/year)"] = fuel_df["Nil consumption"].fillna(0)
        fuel_df["Consumption-based cost (GBP/year)"] = fuel_df["Typical consumption"] - fuel_df["Standing charge (GBP/year)"]

        fuel_df = fuel_df.drop(columns=["Nil consumption", "Typical consumption"])
        fuel_df[["Standing charge (GBP/year)", "Consumption-based cost (GBP/year)"]] = fuel_df[
            ["Standing charge (GBP/year)", "Consumption-based cost (GBP/year)"]
        ].fillna(0)

        dfs.append(fuel_df)

    return pd.concat(dfs, ignore_index=True)


@check_output(schema=GOLD_ANNUAL_BILL_FIXED_AND_VARIABLE_COMPONENT_CONTRIBUTIONS_SCHEMA, importance="fail")
def gold_annual_bill_fixed_and_variable_component_contributions_df(
    annual_bill_fixed_and_variable_contributions_df: pd.DataFrame, silver_df: pd.DataFrame
) -> pd.DataFrame:
    df = annual_bill_fixed_and_variable_contributions_df.copy()
    df["metadata"] = [silver_df["metadata"][0]] * len(df)
    return df


def gold_annual_bill_fixed_and_variable_component_contributions_parquet(
    gold_annual_bill_fixed_and_variable_component_contributions_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str
) -> None:

    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_annual_bill_fixed_and_variable_component_contributions_df,
        df_name="annual_bill_fixed_and_variable_component_contributions",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )

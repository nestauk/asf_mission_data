"""Hamilton nodes for gold-layer of the Energy Price Cap Levels Annex 9 pipeline"""

import logging
from typing import Type

import pandas as pd
import pandera.pandas as pa
from hamilton.data_quality.base import DataValidator, ValidationResult
from hamilton.function_modifiers import (
    check_output,
    check_output_custom,
    parameterize,
    value,
)
from pandera import Check, Column

from asf_mission_data import storage, utils

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
# Gold dataset 1: Unit prices and standing charges by component
# -------------------------------------------------------------


class TariffComponentsTotalValidator(DataValidator):
    """Checks that tariff components sum to Total_GB average."""

    def __init__(self, importance: str = "fail"):
        super(TariffComponentsTotalValidator, self).__init__(importance=importance)

    def applies_to(self, datatype: Type) -> bool:
        return datatype is pd.DataFrame

    def description(self) -> str:
        return "Checks that tariff components sum to Total_GB average for each fuel/payment/period."

    @classmethod
    def name(cls) -> str:
        return "TariffComponentsTotalValidator"

    def validate(self, data: pd.DataFrame) -> ValidationResult:

        group_cols = [
            "Fuel",
            "Payment method",
            "28AD Charge Restriction Period start",
        ]

        totals = data[data["Tariff component"] == "Total_GB average"]
        components = data[data["Tariff component"] != "Total_GB average"]

        component_sums = components.groupby(group_cols)[["Standing charge (p/day)", "Unit price (p/kWh)"]].sum().reset_index()

        merged = component_sums.merge(
            totals[group_cols + ["Standing charge (p/day)", "Unit price (p/kWh)"]],
            on=group_cols,
            suffixes=("_components", "_total"),
        )

        valid = (
            (merged["Standing charge (p/day)_components"].round(6) == merged["Standing charge (p/day)_total"].round(6))
            & (merged["Unit price (p/kWh)_components"].round(6) == merged["Unit price (p/kWh)_total"].round(6))
        ).all()

        return ValidationResult(
            passes=valid,
            message="Tariff components must sum to Total_GB average.",
        )


@parameterize(
    gas_tariff_rates_df={"fuel": value("Gas"), "benchmark_fuel_consumption": value(11.5)},  # TODO move TDCVs to config
    electricity_single_rate_tariff_rates_df={
        "fuel": value("Electricity: Single-Rate Metering Arrangement"),
        "benchmark_fuel_consumption": value(2.7),
    },
    electricity_multi_rate_tariff_rates_df={
        "fuel": value("Electricity: Multi-Register Metering Arrangement"),
        "benchmark_fuel_consumption": value(3.9),
    },
)
@check_output_custom(TariffComponentsTotalValidator())
def fuel_tariff_rates_df(silver_df: pd.DataFrame, fuel: str, benchmark_fuel_consumption: float) -> pd.DataFrame:

    fuel_df = silver_df[silver_df["Fuel"] == fuel].copy()

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

    # calculate daily standing charge
    # convert from £ per year to p per day
    fuel_df["Standing charge (p/day)"] = fuel_df["Nil consumption"] * 100 / 365

    # calculate unit rates
    # convert from £ per MWh to p per kWH
    fuel_df["Unit price (p/kWh)"] = ((fuel_df["Typical consumption"] - fuel_df["Nil consumption"].fillna(0)) / benchmark_fuel_consumption) * 0.1

    fuel_df = fuel_df.drop(columns=["Nil consumption", "Typical consumption"])

    fuel_df[["Standing charge (p/day)", "Unit price (p/kWh)"]] = fuel_df[["Standing charge (p/day)", "Unit price (p/kWh)"]].fillna(0)

    # adjust Total_GB average to include 5% VAT
    is_total = fuel_df["Tariff component"] == "Total_GB average"
    fuel_df.loc[is_total, "Standing charge (p/day)"] *= 1.05
    fuel_df.loc[is_total, "Unit price (p/kWh)"] *= 1.05

    # create separate VAT component (5% of original Total_GB average before VAT)
    total_df = fuel_df[is_total].copy()
    vat_df = total_df.copy()
    vat_df["Tariff component"] = "VAT"

    # uprate tariff rates
    vat_df["Standing charge (p/day)"] = total_df["Standing charge (p/day)"] / 1.05 * 0.05
    vat_df["Unit price (p/kWh)"] = total_df["Unit price (p/kWh)"] / 1.05 * 0.05

    # Append VAT rows
    fuel_df = pd.concat([fuel_df, vat_df], ignore_index=True)

    return fuel_df


# TODO move to schemas.py
GOLD_TARIFF_COMPONENT_RATES_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "Fuel": Column(
            str, Check.isin(["Gas", "Electricity: Single-Rate Metering Arrangement", "Electricity: Multi-Register Metering Arrangement"])
        ),
        "Tariff component": Column(
            str,
            Check.isin(
                [
                    "AA",
                    "CM",
                    "CO",
                    "DF",
                    "DRC",
                    "EBIT",
                    "HAP",
                    "IC",
                    "Levelisation ",
                    "NC",
                    "OC",
                    "PAAC",
                    "PAP",
                    "PC",
                    "SMNCC",
                    "Total_GB average",
                    "VAT",
                ]
            ),
        ),
        "28AD Charge Restriction Period": Column(str),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "Standing charge (p/day)": Column(float),
        "Unit price (p/kWh)": Column(float),
        "metadata": Column(object),
    },
    strict=True,
)


@check_output(schema=GOLD_TARIFF_COMPONENT_RATES_SCHEMA, importance="fail")
def all_fuel_tariff_rates_df(
    silver_df: pd.DataFrame,
    gas_tariff_rates_df: pd.DataFrame,
    electricity_single_rate_tariff_rates_df: pd.DataFrame,
    electricity_multi_rate_tariff_rates_df: pd.DataFrame,
) -> pd.DataFrame:

    concatenated_df = pd.concat(
        [gas_tariff_rates_df, electricity_single_rate_tariff_rates_df, electricity_multi_rate_tariff_rates_df],
        ignore_index=True,
    )

    concatenated_df["metadata"] = [silver_df["metadata"][0]] * len(concatenated_df)

    return concatenated_df


def gold_tariff_component_rates_parquet(all_fuel_tariff_rates_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str) -> None:

    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=all_fuel_tariff_rates_df,
        df_name="tariff_component_rates_standardised",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )

    # for dev only
    all_fuel_tariff_rates_df.to_csv("gold_1_test.csv", index=False)


# -------------------------------------------------------------
# Gold dataset 2: Total unit prices and price ratios
# -------------------------------------------------------------


def total_unit_rates_df(all_fuel_tariff_rates_df: pd.DataFrame) -> pd.DataFrame:
    df_filtered = all_fuel_tariff_rates_df[
        (all_fuel_tariff_rates_df["Tariff component"] == "Total_GB average")
        & (all_fuel_tariff_rates_df["Fuel"].isin(["Gas", "Electricity: Single-Rate Metering Arrangement"]))
    ]

    unit_price_pivot = df_filtered.pivot_table(
        index=["Payment method", "28AD Charge Restriction Period", "28AD Charge Restriction Period start", "28AD Charge Restriction Period end"],
        columns="Fuel",
        values="Unit price (p/kWh)",
    ).rename(
        columns={
            "Electricity: Single-Rate Metering Arrangement": "Electricity (single rate) unit price (p/kWh)",
            "Gas": "Gas unit price (p/kWh)",
        }
    )

    return unit_price_pivot


# TODO move to schemas.py
GOLD_UNIT_RATES_WITH_RATIOS_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "28AD Charge Restriction Period": Column(str),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "Electricity (single rate) unit price (p/kWh)": Column(float),
        "Gas unit price (p/kWh)": Column(float),
        "Electricity to gas price ratio": Column(float),
        "metadata": Column(object),
    },
    strict=True,
)


@check_output(schema=GOLD_UNIT_RATES_WITH_RATIOS_SCHEMA, importance="fail")
def unit_rates_with_ratios_df(total_unit_rates_df: pd.DataFrame, silver_df: pd.DataFrame) -> pd.DataFrame:

    df = total_unit_rates_df.copy().reset_index()

    df["Electricity to gas price ratio"] = df["Electricity (single rate) unit price (p/kWh)"] / df["Gas unit price (p/kWh)"]

    df["metadata"] = [silver_df["metadata"][0]] * len(df)

    return df


def gold_unit_rates_with_ratios_parquet(unit_rates_with_ratios_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str) -> None:

    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=unit_rates_with_ratios_df,
        df_name="unit_rates_with_ratios",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )

    # for dev only
    unit_rates_with_ratios_df.to_csv("gold_2_test.csv", index=False)


# -------------------------------------------------------------
# Gold dataset 3: Total standing charges
# -------------------------------------------------------------

# TODO move to schemas.py
GOLD_STANDING_CHARGES_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "28AD Charge Restriction Period": Column(str),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "Electricity (single rate) standing charge (p/day)": Column(float),
        "Gas standing charge (p/day)": Column(float),
        "metadata": Column(object),
    },
    strict=True,
)


@check_output(schema=GOLD_STANDING_CHARGES_SCHEMA, importance="fail")
def total_standing_charges_df(all_fuel_tariff_rates_df: pd.DataFrame, silver_df: pd.DataFrame) -> pd.DataFrame:
    df_filtered = all_fuel_tariff_rates_df[
        (all_fuel_tariff_rates_df["Tariff component"] == "Total_GB average")
        & (all_fuel_tariff_rates_df["Fuel"].isin(["Gas", "Electricity: Single-Rate Metering Arrangement"]))
    ]

    standing_charge_pivot = df_filtered.pivot_table(
        index=["Payment method", "28AD Charge Restriction Period", "28AD Charge Restriction Period start", "28AD Charge Restriction Period end"],
        columns="Fuel",
        values="Standing charge (p/day)",
    ).rename(
        columns={
            "Electricity: Single-Rate Metering Arrangement": "Electricity (single rate) standing charge (p/day)",
            "Gas": "Gas standing charge (p/day)",
        }
    )

    standing_charge_pivot["metadata"] = [silver_df["metadata"][0]] * len(standing_charge_pivot)

    return standing_charge_pivot.reset_index()


def gold_standing_charges_parquet(total_standing_charges_df: pd.DataFrame, dataset_prefix: str, latest_price_cap_period: str) -> None:

    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=total_standing_charges_df,
        df_name="standing_charges",
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}",
    )

    # for dev only
    total_standing_charges_df.to_csv("gold_3_test.csv", index=False)


# -------------------------------------------------------------
# Gold dataset 4: Total bill breakdown by standing charge vs. consumption-based charge
# -------------------------------------------------------------

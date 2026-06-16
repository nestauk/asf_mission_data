"""Pandera dataframe schemas used to check Hamilton node outputs in the Energy Price Cap Levels Annex 9 pipeline."""

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import COMPONENT_CATEGORY_MAP

TARIFF_COMPONENTS = list(COMPONENT_CATEGORY_MAP.keys())
COMPONENT_CATEGORIES = list(set(COMPONENT_CATEGORY_MAP.values()))

SILVER_1C_CONSUMPTION_ADJUSTED_LEVELS_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "Fuel": Column(str),
        "Consumption": Column(str, Check.isin(["Nil consumption", "Typical consumption"])),
        "Tariff component": Column(str, Check.isin([c for c in TARIFF_COMPONENTS if c != "VAT"] + ["Total inc VAT"])),
        "28AD Charge Restriction Period": Column(str),
        "value": Column(float, nullable=True),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "28AD Charge Restriction Period interval": Column("interval[datetime64[ns], both]"),
        "metadata": Column(object),
    },
    strict=True,
    coerce=True,
)

GOLD_1C_CONSUMPTION_ADJUSTED_LEVELS_WITH_VAT_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "Fuel": Column(str),
        "Consumption": Column(str, Check.isin(["Nil consumption", "Typical consumption"])),
        "Tariff component": Column(str, Check.isin(TARIFF_COMPONENTS)),
        "Component category": Column(str, Check.isin(COMPONENT_CATEGORIES)),
        "28AD Charge Restriction Period": Column(str),
        "value": Column(float, nullable=True),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "28AD Charge Restriction Period interval": Column("interval[datetime64[ns], both]"),
        "metadata": Column(object),
    },
    strict=True,
)

GOLD_TARIFF_COMPONENT_RATES_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "Fuel": Column(
            str, Check.isin(["Gas", "Electricity: Single-Rate Metering Arrangement", "Electricity: Multi-Register Metering Arrangement"])
        ),
        "Tariff component": Column(str, Check.isin(TARIFF_COMPONENTS)),
        "Component category": Column(str, Check.isin(COMPONENT_CATEGORIES)),
        "28AD Charge Restriction Period": Column(str),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "Type": Column(str),
        "Unit": Column(str),
        "value": Column(float),
        "metadata": Column(object),
    },
    strict=True,
)

GOLD_PRICE_RATIOS_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "28AD Charge Restriction Period": Column(str),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "Variable": Column(str, Check.isin(["Electricity to gas price ratio"])),
        "value": Column(float),
        "metadata": Column(object),
    },
    strict=True,
)

GOLD_ANNUAL_BILL_FIXED_AND_VARIABLE_COMPONENT_CONTRIBUTIONS_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "Fuel": Column(
            str, Check.isin(["Gas", "Electricity: Single-Rate Metering Arrangement", "Electricity: Multi-Register Metering Arrangement"])
        ),
        "Tariff component": Column(str, Check.isin(TARIFF_COMPONENTS)),
        "Component category": Column(str, Check.isin(COMPONENT_CATEGORIES)),
        "28AD Charge Restriction Period": Column(str),
        "28AD Charge Restriction Period start": Column(pd.Timestamp),
        "28AD Charge Restriction Period end": Column(pd.Timestamp),
        "Type": Column(str),
        "Unit": Column(str),
        "value": Column(float),
        "metadata": Column(object),
    },
    strict=True,
)

# Pandera validation schemas for dataframes in the Energy Price Cap Levels Annex 9 pipeline

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

SILVER_1C_CONSUMPTION_ADJUSTED_LEVELS_SCHEMA = pa.DataFrameSchema(
    {
        "Payment method": Column(str, Check.isin(["Other Payment Method", "Standard Credit", "PPM"])),
        "Fuel": Column(str),
        "Consumption": Column(str, Check.isin(["Nil consumption", "Typical consumption"])),
        "Tariff component": Column(
            str,
            Check.isin(
                [
                    "DF",
                    "CM",
                    "AA",
                    "PC",
                    "NC",
                    "OC",
                    "SMNCC",
                    "IC",
                    "PAAC",
                    "PAP",
                    "CO",
                    "DRC",
                    "EBIT",
                    "HAP",
                    "Levelisation ",  # note that this intentionally ends with a blankspace
                    "Total_GB average",
                    "Total inc VAT",
                ]
            ),
        ),
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
        "Tariff component": Column(
            str,
            Check.isin(
                [
                    "DF",
                    "CM",
                    "AA",
                    "PC",
                    "NC",
                    "OC",
                    "SMNCC",
                    "IC",
                    "PAAC",
                    "PAP",
                    "CO",
                    "DRC",
                    "EBIT",
                    "HAP",
                    "Levelisation ",  # note that this intentionally ends with a blankspace
                    "Total_GB average",
                    "VAT",
                ]
            ),
        ),
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

GOLD_TOTAL_UNIT_RATES_WITH_RATIOS_SCHEMA = pa.DataFrameSchema(
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

GOLD_ANNUAL_BILL_FIXED_AND_VARIABLE_COMPONENT_CONTRIBUTIONS_SCHEMA = pa.DataFrameSchema(
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
        "Standing charge (GBP/year)": Column(float),
        "Consumption-based cost (GBP/year)": Column(float),
        "metadata": Column(object),
    },
    strict=True,
)

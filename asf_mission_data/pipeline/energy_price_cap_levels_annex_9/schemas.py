# Pandera validation schemas for dataframes in the Energy Price Cap Levels Annex 9 pipeline

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

SILVER_TARIFF_TABLES_SCHEMA = pa.DataFrameSchema(
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

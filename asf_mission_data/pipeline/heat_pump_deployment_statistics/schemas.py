"""Pandera dataframe schemas used to check Hamilton node outputs in the Heat Pump Deployment Statistics pipeline."""

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

# Names-only schema
WIDE_TABLE_1_1_SCHEMA = pa.DataFrameSchema(
    {
        col: Column(None, nullable=True)
        for col in [
            "Installation quarter",
            "Installation quarter start",
            "Installation quarter end",
            "Notes",
            "Air source heat pump installations",
            "Ground/water source heat pump installations",
            "Total heat pump installations",
        ]
    },
    strict=True,
)

SILVER_TABLE_1_1_SCHEMA = pa.DataFrameSchema(
    {
        "Installation quarter": Column(str, nullable=False),
        "Installation quarter start": Column(pd.Timestamp, nullable=False),
        "Installation quarter end": Column(pd.Timestamp, nullable=False),
        "Notes": Column(str, nullable=True),
        "Type": Column(
            str,
            nullable=False,
            checks=Check.isin(
                [
                    "Air source heat pump installations",
                    "Ground/water source heat pump installations",
                    "Total heat pump installations",
                ]
            ),
        ),
        "value": Column(int, nullable=False, checks=Check.ge(0)),
        "metadata": Column(object, nullable=False),
    },
    strict=True,
)

# Names-only schema
WIDE_TABLE_1_2_SCHEMA = pa.DataFrameSchema(
    {
        col: Column(None, nullable=True)
        for col in [
            "Installation quarter",
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
            "Notes",
            "Installation quarter start",
            "Installation quarter end",
        ]
    },
    strict=True,
)

SILVER_TABLE_1_2_SCHEMA = pa.DataFrameSchema(
    {
        "Installation quarter": Column(str, nullable=False),
        "Installation quarter start": Column(pd.Timestamp, nullable=False),
        "Installation quarter end": Column(pd.Timestamp, nullable=False),
        "Notes": Column(str, nullable=True),
        "Country or Region": Column(
            str,
            nullable=False,
            checks=Check.isin(
                [
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
            ),
        ),
        "value": Column(int, nullable=False, checks=Check.ge(0)),
        "metadata": Column(object, nullable=False),
        "Area code": Column(
            str,
            nullable=False,
            checks=Check.isin(
                [
                    "K02000001",
                    "N/A",
                    "E92000001",
                    "E12000001",
                    "E12000002",
                    "E12000004",
                    "E12000005",
                    "E12000006",
                    "E12000007",
                    "E12000008",
                    "E12000009",
                    "W92000004",
                    "S92000003",
                    "N92000002",
                ]
            ),
        ),
    },
    strict=True,
)

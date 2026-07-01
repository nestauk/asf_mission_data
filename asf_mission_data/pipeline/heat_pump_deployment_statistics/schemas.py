"""Pandera dataframe schemas used to check Hamilton node outputs in the Heat Pump Deployment Statistics pipeline."""

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

from asf_mission_data.pipeline.heat_pump_deployment_statistics.config import (
    AREA_CODES,
    GEOGRAPHIC_LEVELS,
    TABLE_1_1_VALUE_VARS,
    TABLE_1_2_VALUE_VARS,
)

# Names-only schema
WIDE_TABLE_1_1_SCHEMA = pa.DataFrameSchema(
    {
        col: Column(None, nullable=True)
        for col in [
            "Installation quarter",
            "Installation quarter start",
            "Installation quarter end",
            "Notes",
            *TABLE_1_1_VALUE_VARS,
        ]
    },
    strict=True,
)

SILVER_TABLE_1_1_SCHEMA = pa.DataFrameSchema(
    {
        "installation_quarter": Column(str, nullable=False),
        "installation_quarter_start": Column(pd.Timestamp, nullable=False),
        "installation_quarter_end": Column(pd.Timestamp, nullable=False),
        "notes": Column(str, nullable=True),
        "type": Column(str, nullable=False, checks=Check.isin(TABLE_1_1_VALUE_VARS)),
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
            *TABLE_1_2_VALUE_VARS,
            "Notes",
            "Installation quarter start",
            "Installation quarter end",
        ]
    },
    strict=True,
)

SILVER_TABLE_1_2_SCHEMA = pa.DataFrameSchema(
    {
        "installation_quarter": Column(str, nullable=False),
        "installation_quarter_start": Column(pd.Timestamp, nullable=False),
        "installation_quarter_end": Column(pd.Timestamp, nullable=False),
        "notes": Column(str, nullable=True),
        "country_or_region": Column(str, nullable=False, checks=Check.isin(TABLE_1_2_VALUE_VARS)),
        "value": Column(int, nullable=False, checks=Check.ge(0)),
        "metadata": Column(object, nullable=False),
        "area_code": Column(str, nullable=False, checks=Check.isin(AREA_CODES)),
        "geographic_level": Column(str, nullable=False, checks=Check.isin(GEOGRAPHIC_LEVELS)),
    },
    strict=True,
)

import pandas as pd
import pandera.pandas as pa
from pandera import Check, Column

SILVER_TABLE_1_1_SCHEMA = pa.DataFrameSchema(
    {
        "Installation quarter": Column(str),
        "Installation quarter start": Column(pd.Timestamp),
        "Installation quarter end": Column(pd.Timestamp),
        "Notes": Column(str),
        "Type": Column(
            str,
            Check.isin(["Air source heat pump installations", "Ground/water source heat pump installations", "Total heat pump installations"]),
        ),
        "value": Column(int),
        "metadata": Column(object),
    },
    strict=True,
)

# TODO
SILVER_TABLE_1_2_SCHEMA = pa.DataFrameSchema(
    {
        "Installation quarter": Column(str),
        "Installation quarter start": Column(pd.Timestamp),
        "Installation quarter end": Column(pd.Timestamp),
        "Notes": Column(str),
        "Type": Column(
            str,
            Check.isin(["TO DO"]),
        ),
        "value": Column(int),
        "metadata": Column(object),
    },
    strict=True,
)

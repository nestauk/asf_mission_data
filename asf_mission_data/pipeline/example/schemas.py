# Pandera validation schemas for dataframes in the example pipeline

import pandera.pandas as pa
from pandera import Check, Column

SILVER_BANK_HOLIDAYS_SCHEMA = pa.DataFrameSchema(
    {
        "division": Column(
            str,
            Check.isin(["england-and-wales", "scotland", "northern-ireland"]),
        ),
        "title": Column(str),
        "date": Column("datetime64[ns]"),
        "notes": Column(str),
        "bunting": Column(bool),
        "year": Column(int),
    },
    strict=True,
    coerce=True,
)

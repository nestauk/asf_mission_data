# %% [markdown]
# ### Checks for TDCV and electricity VAT changes for Oct - Dec 2026 and Jan - Mar 2027 price cap periods

# %%
import pandas as pd

from asf_mission_data import storage
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    BENCHMARK_CONSUMPTION,
)

# %%
silver_df = storage.read_parquet(
    "s3://asf-mission-data-dev/data/silver/energy_price_cap_levels/annex_9/latest/1c_consumption_adjusted_levels/1c_consumption_adjusted_levels.parquet"
)

# %%
start_date_to_check = "2026-10-01"

# %%
# Levels table checks
gold_levels_df = storage.read_parquet(
    "s3://asf-mission-data-dev/data/gold/energy_price_cap_levels/annex_9/latest/1c_consumption_adjusted_levels_with_vat/1c_consumption_adjusted_levels_with_vat.parquet"
)
df = gold_levels_df

# %%
# VAT check, should be zero
df[
    (df["28AD Charge Restriction Period start"] == pd.to_datetime(start_date_to_check))
    & (df["Consumption"] == "Typical consumption")
    & (df["Payment method"] == "Other Payment Method")
    & (df["Fuel"] == "Electricity: Single-Rate Metering Arrangement")
    & (df["Tariff component"] == "VAT")
]

# %%
# Total bill check, should match final dual fuel bill matches what is published on Ofgem page
df = gold_levels_df
df[
    (df["28AD Charge Restriction Period start"] == pd.to_datetime(start_date_to_check))
    & (df["Consumption"] == "Typical consumption")
    & (df["Payment method"] == "Other Payment Method")
    & (df["Fuel"] == "Dual fuel (implied)")
    & (df["Tariff component"] == "Total_GB average")
]

# %%
# Electricity bill check
df = gold_levels_df
df[
    (df["28AD Charge Restriction Period start"] == pd.to_datetime(start_date_to_check))
    & (df["Consumption"] == "Typical consumption")
    & (df["Payment method"] == "Other Payment Method")
    & (df["Fuel"] == "Electricity: Single-Rate Metering Arrangement")
    & (df["Tariff component"] == "Total_GB average")
]

# %%
# Component rates and standing charges check
gold_tariff_component_rates_df = storage.read_parquet(
    "s3://asf-mission-data-dev/data/gold/energy_price_cap_levels/annex_9/latest/tariff_component_rates/tariff_component_rates.parquet"
)
df = gold_tariff_component_rates_df

# %%
# Electricity checks
df[
    (df["28AD Charge Restriction Period start"] == pd.to_datetime(start_date_to_check))
    & (df["Payment method"] == "Other Payment Method")
    & (df["Fuel"] == "Electricity: Single-Rate Metering Arrangement")
    & (df["Tariff component"] == "Total_GB average")
]

# %%
# Gas checks
df[
    (df["28AD Charge Restriction Period start"] == pd.to_datetime(start_date_to_check))
    & (df["Payment method"] == "Other Payment Method")
    & (df["Fuel"] == "Gas")
    & (df["Tariff component"] == "Total_GB average")
]

# %%
# Check annual_bill_fixed_and_variable_contributions_df
# Consumption-based cost (£/yr) should match the unit rate (incl VAT) * TDCV
gold_annual_bill_fixed_and_variable_contributions_df = storage.read_parquet(
    "s3://asf-mission-data-dev/data/gold/energy_price_cap_levels/annex_9/latest/annual_bill_fixed_and_variable_component_contributions/annual_bill_fixed_and_variable_component_contributions.parquet"
)
df = gold_annual_bill_fixed_and_variable_contributions_df

# %%
# Electricity checks
df[
    (df["28AD Charge Restriction Period start"] == pd.to_datetime(start_date_to_check))
    & (df["Payment method"] == "Other Payment Method")
    & (df["Fuel"] == "Electricity: Single-Rate Metering Arrangement")
    & (df["Tariff component"] == "Total_GB average")
]

# %%
electricity_tdcv = BENCHMARK_CONSUMPTION.get("Electricity: Single-Rate Metering Arrangement") * 1_000  # kWh/year
electricity_unit_rate = 26.322252  # p/kWh
electricity_tdcv * electricity_unit_rate / 100  # should match annual consumption-based cost

# %%
# Gas checks
df[
    (df["28AD Charge Restriction Period start"] == pd.to_datetime(start_date_to_check))
    & (df["Payment method"] == "Other Payment Method")
    & (df["Fuel"] == "Gas")
    & (df["Tariff component"] == "Total_GB average")
]

# %%
gas_tdcv = BENCHMARK_CONSUMPTION.get("Gas") * 1_000  # kWh/year
gas_unit_rate = 7.966458  # p/kWh
gas_tdcv * gas_unit_rate / 100  # should match annual consumption-based cost

# %%

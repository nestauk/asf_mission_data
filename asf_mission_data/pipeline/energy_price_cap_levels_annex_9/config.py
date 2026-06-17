"""
Static configuration values for extracting Energy Price Cap Levels Annex 9 data from Ofgem.
"""

DATASET_PREFIX = "energy_price_cap_levels/annex_9"
PUBLISHER = "Ofgem"
COLLECTION_URL = "https://www.ofgem.gov.uk/energy-regulation/domestic-and-non-domestic/energy-pricing-rules/energy-price-cap/energy-price-cap-default-tariff-levels"
FILE_LINK_TEXT = "Final levelised cap rates model (Annex 9)"

# Regex pattern for expected price cap period dates string format on Ofgem website
PRICE_CAP_PERIOD_STRING_PATTERN = r"(\d{1,2}\s+[A-Za-z]+\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4})"
PRICE_CAP_PERIOD_INTERVAL_PATTERN = (
    r"(?P<start_day>\d{1,2})\s+(?P<start_month>[A-Za-z]+)\s+to\s+(?P<end_day>\d{1,2})\s+(?P<end_month>[A-Za-z]+)\s+(?P<year>\d{4})"
)

PRICE_CAP_PERIOD_PUBLICATION_DATES = {
    "1 January to 31 March 2026": "2025-11-21",
    "1 April to 30 June 2026": "2026-02-25",
    "1 July to 30 September 2026": "2026-05-27",
    "1 October to 31 December 2026": "2026-08-26",
    "1 January to 31 March 2027": "2026-11-25",
    "1 April to 30 June 2027": "2027-02-23",
    "1 July to 30 September 2027": "2027-05-26",
    "1 October to 31 December 2027": "2027-08-25",
    "1 January to 31 March 2028": "2027-11-24",
    "1 April to 30 June 2028": "2028-02-23",
    "1 July to 30 September 2028": "2028-05-31",
    "1 October to 31 December 2028": "2028-08-30",
    "1 January to 31 March 2029": "2028-11-29",
    "1 April to 30 June 2029": "2029-02-28",
    "1 July to 30 September 2029": "2029-05-30",
    "1 October to 31 December 2029": "2029-08-29",
    "1 January to 31 March 2030": "2029-11-28",
    "1 April to 30 June 2030": "2030-02-27",
    "1 July to 30 September 2030": "2030-05-29",
    "1 October to 31 December 2030": "2030-08-28",
}

# Excel sheet name - Silver table Hamilton output node
SILVER_TABLES_NODES_MAP = {"1c Consumption adjusted levels": "silver_energy_price_cap_annex_9_1c_consumption_adjusted_levels_parquet"}

BENCHMARK_CONSUMPTION = {  # MWh per year
    "Gas": 11.5,
    "Electricity: Single-Rate Metering Arrangement": 2.7,
    "Electricity: Multi-Register Metering Arrangement": 3.9,
}

VAT = 0.05

COMPONENT_CATEGORY_MAP = {
    "DF": "Wholesale",  # Direct fuel
    "CM": "Wholesale",  # Capacity market
    "AA": "Other",  # Adjustment allowance
    "PC": "Policy",  # Policy costs
    "NC": "Network",  # Network costs
    "OC": "Operating",  # Operating costs
    "SMNCC": "Operating",  # Smart Meter Net Cost Change
    "IC": "Operating",  # Industry charge
    "PAAC": "Operating",  # Payment method adjustment additional cost
    "PAP": "Operating",  # Payment method adjustment percentage
    "CO": "Operating",  # Core operating costs
    "DRC": "Operating",  # Debt-Related costs
    "EBIT": "Other",  # Earnings Before interest and Tax
    "HAP": "Other",  # Headroom allowance
    "Levelisation ": "Other",  # Levelisation, note that this intentionally ends with a blankspace
    "VAT": "VAT",
    "Total_GB average": "Total_GB average",
}

# Silver table prefix - Gold table Hamilton output node
GOLD_TABLES_NODES_MAP = {
    "1c_consumption_adjusted_levels": [
        "gold_1c_consumption_adjusted_levels_with_vat_parquet",
        "gold_tariff_component_rates_parquet",
        "gold_price_ratios_parquet",
        "gold_annual_bill_fixed_and_variable_component_contributions_parquet",
    ]
}

"""
Configuration constants for the Bank Holidays example pipeline.
"""

PUBLISHER = "GOV.UK"
DATASET_PREFIX = "example"
SOURCE_URL = "https://www.gov.uk/bank-holidays.json"
PAGE_URL = "https://www.gov.uk/bank-holidays"

# Dictionary of all silver table names and their corresponding Hamilton output node
SILVER_TABLES_NODES_MAP = {"UK bank holidays": "silver_bank_holidays_parquet"}

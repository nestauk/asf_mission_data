# UNDER DEVELOPMENT

# Datasets documentation for pipeline: Energy price cap levels Annex 9

This file documents the datasets included in this pipeline, including their source, description, and canonical names.

## Bronze, Silver and Gold

### ETL code in GitHub repo

| Variable | Defined where? | What is this? | Feeds into |
|----------|----------------|---------------|------------|
|`dataset_prefix`| `config.ENERGY_PRICE_CAP_LEVELS_ANNEX_9` | Pipeline identifier. | S3 prefix for all bronze, silver and gold files.

## Bronze

### ETL code in GitHub repo

| Variable | Defined where? | What is this? | Feeds into |
|----------|----------------|---------------|------------|
|`collection_url`| `config.ENERGY_PRICE_CAP_LEVELS_ANNEX_9` | URL of dataset collection webpage. |  N/A
|`file_url`| Scraped from collection webpage in a node in `bronze.py` | URL to download Excel file. |  N/A
|`filename`| Sliced from `file_url`. | Name of Excel file, including .xlsx file extension. | Name of bronze file in S3.  
|`price_cap_period_prefix`| Scraped from collection webpage in a node in `bronze.py` and normalised to ISO date format.| Price cap period that the bronze file pertains to. |S3 prefix partition to organise historical archive of bronze files.

### S3 bucket

`bucket_name` is either `asf-mission-data-dev` or `asf-mission-data-prod`

**Latest**

s3://{`bucket_name`}/data/bronze/latest/file/{`filename`}
s3://{`bucket_name`}/data/bronze/latest/metadata/{`filename`}.metadata.json

**Historical**

s3://{`bucket_name`}/data/bronze/historical/{`price_cap_period_prefix`}/file/{`filename`}
s3://{`bucket_name`}/data/bronze/lhistorical/{price_cap_period_prefix}/metadata/{`filename`}.metadata.json

### DuckLake
N/A.

### Superset
N/A.

### Bronze file registry

| File      | Energy price cap levels Annex 9      |
|-----------|--------------------------------------|
| Output Hamilton node | `bronze.bronze_energy_price_cap_annex_9_file()`
| S3        | {S3 prefix}/Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-vX.XX.xlsx
| DuckLake  | N/A
| Superset  | N/A


## Silver

### ETL code in GitHub repo

| Variable | Defined where? | What is this? | Feeds into |
|----------|----------------|---------------|------------|
|`sheet_name`| xx | xx | xx |
|`price_cap_period_prefix`| Extracted from bronze metadata file. | Price cap period that the silver file pertains to. | S3 prefix partition to organise historical archive of silver files.

### S3 bucket

`bucket_name` is either `asf-mission-data-dev` or `asf-mission-data-prod`

**Latest**

s3://{`bucket_name`}/data/silver/latest/{`sheet_name`}.parquet

**Historical**

s3://{`bucket_name`}/data/silver/historical/{`price_cap_period_prefix`}/{`sheet_name`}.parquet

### DuckLake

TBD.

### Superset

TBD.

### Silver file registry

| Dataset   | 1c Consumption adjusted levels       |
|-----------|--------------------------------------|
| Output Hamilton node | `silver.silver_energy_price_cap_annex_9_1c_consumption_adjusted_levels_parquet()`
| S3        | {S3 prefix}/1c_consumption_adjusted_levels.parquet
| DuckLake  | TBD
| Superset  | TBD

## Gold

### Gold file registry

| Dataset   | Nil and typical consumption components including VAT |
|-----------|--------------------------------------|
| Source silver dataset | 1c_consumption_adjusted_levels.parquet
| Output Hamilton node  | `gold.gold_1c_consumption_adjusted_levels_with_vat_parquet()`
| S3        | {S3 prefix}/`1c_consumption_adjusted_levels_with_vat`.parquet
| DuckLake  | TBD
| Superset  | TBD


| Dataset   |    Unit prices and standing charges by component, standardised units           |
|-----------|--------------------------------------|
| Source silver dataset | 1c_consumption_adjusted_levels.parquet
| Output Hamilton node  | `gold.gold_tariff_component_rates_parquet()`
| S3        | {S3 prefix}/`tariff_component_rates`.parquet
| DuckLake  | TBD
| Superset  | TBD


| Dataset   |    Total unit prices and price ratios           |
|-----------|--------------------------------------|
| Source silver dataset | 1c_consumption_adjusted_levels.parquet
| Output Hamilton node  | `gold.gold_total_unit_rates_with_ratios_parquet()`
| S3        | {S3 prefix}/`total_unit_rates_with_ratios`.parquet
| DuckLake  | TBD
| Superset  | TBD


| Dataset   |    Annual fuel bill breakdown by standing charge vs. consumption-based charge           |
|-----------|--------------------------------------|
| Source silver dataset | 1c_consumption_adjusted_levels.parquet
| Output Hamilton node  | `gold.gold_annual_bill_fixed_and_variable_component_contributions_parquet()`
| S3        | {S3 prefix}/`annual_bill_fixed_and_variable_component_contributions`.parquet
| DuckLake  | TBD
| Superset  | TBD

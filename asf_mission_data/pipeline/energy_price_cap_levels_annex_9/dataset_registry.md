## Bronze
Filename: Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.9.xlsx

## Silver
tables:

### Silver table 1


- **Table name**: 1c Consumption adjusted levels

- **S3 filename**: 1c_consumption_adjusted_levels.parquet

- **DuckLake table name**: EnergyPriceCapLevelsAnnex9_silver_1cConsumptionAdjustedLevels

- **Superset dataset name**: EnergyPriceCapLevelsAnnex9_silver_1cConsumptionAdjustedLevels



## Gold
tables:

### Gold table 1


- **Source silver table**: 1c_consumption_adjusted_levels.parquet

- **S3 filename**: 1c_consumption_adjusted_levels_with_vat.parquet

- **DuckLake table name**: EnergyPriceCapLevelsAnnex9_gold_1cConsumptionAdjustedLevelsWithVat

- **Superset dataset name**: EnergyPriceCapLevelsAnnex9_gold_1cConsumptionAdjustedLevelsWithVat


### Gold table 2


- **Source silver table**: 1c_consumption_adjusted_levels.parquet

- **S3 filename**: tariff_component_rates.parquet

- **DuckLake table name**: EnergyPriceCapLevelsAnnex9_gold_TariffComponentRates

- **Superset dataset name**: EnergyPriceCapLevelsAnnex9_gold_TariffComponentRates


### Gold table 3


- **Source silver table**: 1c_consumption_adjusted_levels.parquet

- **S3 filename**: price_ratios.parquet

- **DuckLake table name**: EnergyPriceCapLevelsAnnex9_gold_PriceRatios

- **Superset dataset name**: EnergyPriceCapLevelsAnnex9_gold_PriceRatios


### Gold table 4


- **Source silver table**: 1c_consumption_adjusted_levels.parquet

- **S3 filename**: annual_bill_fixed_and_variable_component_contributions.parquet

- **DuckLake table name**: EnergyPriceCapLevelsAnnex9_gold_AnnualBillFixedAndVariableComponentContributions

- **Superset dataset name**: EnergyPriceCapLevelsAnnex9_gold_AnnualBillFixedAndVariableComponentContributions

# Energy Price Cap Levels Annex 9

Ingests Ofgem's published "Final levelised cap rates model (Annex 9)" Excel workbook and transforms it into datasets covering tariff component rates, price ratios, and annual bill contributions across fuel types, payment methods, and quarterly price cap periods.

**Source:** Ofgem  
**Update cadence:** Quarterly (two months before start of each price cap period)  
**Pipeline run name:** `energy_price_cap_levels_annex_9`  
**Storage prefix:** `energy_price_cap_levels/annex_9`


## Pipeline stages

### Bronze

- **Source**: [Energy price cap (default tariff) levels webpage](https://www.ofgem.gov.uk/energy-regulation/domestic-and-non-domestic/energy-pricing-rules/energy-price-cap/energy-price-cap-default-tariff-levels)
- **Method**: Web scraping
- **Output**:
  - `Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.10-July-September-2026.xlsx`
  - `Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.10-July-September-2026.xlsx.metadata.json`
- **Validators**:
  - `LatestPriceCapFileUrlValidator` checks the scraped file URL contains the expected publication month for the current price cap period, guarding against scraping the wrong file.
  - `LatestPriceCapValidator` checks the page heading matches the expected price cap period, guarding against scraping the wrong price cap period string.

### Silver

#### `1c_consumption_adjusted_levels`
- **Description**: Tidy format. One row per tariff component per fuel type, payment method, consumption type, and charge restriction period.
- **Input**: `1C Consumption adjusted levels` sheet from bronze Excel file
- **Output**: `1c_consumption_adjusted_levels.parquet`
- **Validators**:
  - `ChargeRestrictionPeriodValidator`checks charge restriction period string formats are valid. - `PriceCapValidator` checks the price cap period in bronze metadata matches the expected current period.
  -  Pandera schema check on final silver table.

### Gold

#### `1c_consumption_adjusted_levels_with_vat`
- **Description**: Silver tariff component data with VAT added as a separate component and `Total_GB average` uprated to include VAT. Includes period-on-period change columns.
- **Input**: `1c_consumption_adjusted_levels` silver table
- **Output**: `1c_consumption_adjusted_levels_with_vat.parquet`
- **Validators**:
  - `TariffComponentsTotalValidator` checks tariff components sum correctly by consumption, fuel, payment method, and period.
  - Pandera schema check on final gold table.

#### `tariff_component_rates`
- **Description**: Standing charges and unit prices for each tariff component, derived from nil and typical consumption values. Includes period-on-period change columns.
- **Input**: `1c_consumption_adjusted_levels` silver table
- **Output**: `tariff_component_rates.parquet`
- **Validators**:
  - `TariffComponentsTotalValidator`.
  - Pandera schema check on final gold table.

#### `price_ratios`
- **Description**: Electricity-to-gas unit price ratio by payment method and price cap period. Includes period-on-period change columns.
- **Input**: `1c_consumption_adjusted_levels` silver table
- **Output**: `price_ratios.parquet`
- **Validators**: Pandera schema check on final gold table.

#### `annual_bill_fixed_and_variable_component_contributions`
- **Description**: Annual bill split into standing charge and consumption-based cost contributions for each tariff component, fuel type, and payment method. Includes period-on-period change columns.
- **Input**: `1c_consumption_adjusted_levels` silver table
- **Output**: `annual_bill_fixed_and_variable_component_contributions.parquet`
- **Validators**:
  - `TariffComponentsTotalValidator`.
  - Pandera schema check on final gold table.

---

## Notes

1. All gold tables are derived from the `1c_consumption_adjusted_levels` silver table.
2. VAT is applied at 5% (`VAT = 0.05`). If this rate changes, update `VAT` in `config.py`.
3. Benchmark consumption values (i.e. the medium Typical Domestic Consumption Value, TDCV) used to back-calculate unit prices and standing charges from Annex 9 are defined in `BENCHMARK_CONSUMPTION` in `config.py`. TDCVs are used to set the energy price cap and help show what an average home spends on gas and electricity. Ofgem updates these every few years to make sure they still reflect how much energy people actually use.
4. `price_ratios` may contain null values if gas unit price is zero for a given period — this is handled intentionally to avoid misleading spikes in downstream charts.
5. Individual tariff components are often grouped into broader categories for ease of communication. Component-category mapping is defined and can be updated in `COMPONENT_CATEGORY_MAP` in `config.py`.

---

*Last updated: 25 June 2026 by Elysia Lucas*

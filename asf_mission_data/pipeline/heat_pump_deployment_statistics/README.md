# Heat Pump Deployment Statistics

Ingests data on the number of heat pumps installed in the UK, only includes those installed in existing properties (retrofit). Excludes installations in new builds or retrofit installs that are not MCS certified.

**Source:** Department for Energy Security and Net Zero, GOV.UK  
**Update cadence:** Quarterly  
**Pipeline run name:** `heat_pump_deployment_statistics`  
**Storage prefix:** `heat_pump_deployment_statistics`  


## Pipeline stages

### Bronze

- **Source**: https://www.gov.uk/api/content/government/collections/heat-pump-deployment-statistics
- **Method**: GOV.UK Content API
- **Output**:
  - `Heat_pump_deployment_quarterly_statistics_United_Kingdom_2026_Q1.xlsx`
  - `Heat_pump_deployment_quarterly_statistics_United_Kingdom_2026_Q1.xlsx.metadata.json`
- **Validators**:
  - `ExcelFileExtensionValidator` checks the downloaded file has a `.xlsx` extension.
  - `WithinThreeCalendarMonthsValidator` checks the publication date returned by the API is within the last 3 calendar months, guarding against stale data.

### Silver

#### `table_1_1`
- **Description**: Tidy format. One row per installation quarter per heat pump type, for the UK.
- **Input**: Content in tab named `Table 1.1` from bronze Excel file
- **Output**: `table_1_1.parquet `
- **Validators**:
  - `StartStringValidator` on table name and source citation.
  - Pandera schema checks on wide and final silver table.

#### `table_1_2`
- **Description**: Tidy format. One row per installation quarter per country/region, for all heat pump types combined.
- **Input**: Content in tab named `Table 1.2` from bronze Excel file
- **Output**: `table_1_2.parquet `
- **Validators**:
  - `StartStringValidator` on table name and source citation.
  - Pandera schema checks on wide and final silver table.

### Gold

#### `table_1_1`
- **Description**: Silver Table 1.1 table augmented with quarter-on-quarter changes by technology type.
- **Input**: `table_1_1` silver table
- **Output**: `table_1_1.parquet`
- **Validators**:
  - Pandera schema check on final gold table.

#### `table_1_2`
- **Description**: Silver Table 1.2 table augmented with quarter-on-quarter changes by country/region.
- **Input**: `table_1_2` silver table
- **Output**: `table_1_2.parquet`
- **Validators**:
  - Pandera schema check on final gold table.

---

## Notes

1. This dataset has 'Official statistics in development' status meaning it is still undergoing methodological development and subject to change.
2. The source Excel workbook contains a `Notes` sheet with numbered footnotes that are referenced inline in the data tables (e.g. `[note 1]`). The pipeline resolves these into a `notes` column in the silver tables. If the workbook structure changes, e.g., if the `Notes` sheet is renamed or the footnote format changes, this logic may break silently.

---

*Last updated: 07 September 2026 by Elysia Lucas*

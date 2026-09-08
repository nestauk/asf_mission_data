# Boiler Upgrade Scheme Statistics

Ingests data on the uptake of the Boiler Upgrade Scheme (BUS) which contributes upfront capital grants for low-carbon tech installations - including air-source heat pumps, ground-source heat pumps, shared ground loops and biomass boilers in domestic and small non-domestic buildings. Data tables are monthly and cumulative analyses.

**Source:** Department for Energy Security and Net Zero, GOV.UK  
**Update cadence:** Monthly
**Pipeline run name:** `boiler_upgrade_scheme_statistics`  
**Storage prefix:** `boiler_upgrade_scheme_statistics`  


## Pipeline stages

### Bronze

- **Source**: https://www.gov.uk/government/collections/boiler-upgrade-scheme-statistics
- **Method**: GOV.UK Content API
- **Output name structure**:
  - `Boiler_Upgrade_Scheme_BUS_Statistics_[Month]_[YYYY].xlsx`
  - `Boiler_Upgrade_Scheme_BUS_Statistics_[Month]_[YYYY].xlsx.metadata.json`
- **Validators**:
  - `ExcelFileExtensionValidator` checks the downloaded file has a `.xlsx` extension.
  - `WithinLastCalendarMonthValidator` checks the publication date returned by the API is within the last month, guarding against stale data.


---

## Notes

1. This dataset has provisional status meaning it is subject to future revisions.

---

*Last updated: 08 September 2026 by Elysia Lucas*

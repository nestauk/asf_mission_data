# Example (UK Bank Holidays)

Ingests the UK bank holidays dataset as a simple pipeline example.

**Source:** GOV.UK  
**Update cadence:** Annually  
**Pipeline run name:**: `example`  
**Storage prefix:** `example`


## Pipeline stages

### Bronze

- **Source**: https://www.gov.uk/bank-holidays.json
- **Method**: HTTP GET request
- **Output**:
  - `bank-holidays.json`
  - `bank-holidays.json.metadata.json`
- **Validators**: None

### Silver

#### `bank_holidays`
- **Description**: One row per bank holiday per UK division.
- **Input**: `bank-holidays.json`
- **Output**: `bank_holidays.parquet`
- **Validators**: Pandera schema check - validates column types and that `division` is one of the three expected values.

---

## Notes

1. There are different bank holidays across England & Wales, Scotland and Northern Ireland. The `division` field therefore corresponds to UK geographical regions and can only be `england-and-wales`, `scotland`, `northern-ireland`.

---

*Last updated: 25 June 2026 by Elysia Lucas*

<!-- Pipeline name -->
# Example (UK Bank Holidays)

<!-- One or two sentences: what dataset this pipeline produces and why it's useful. -->
Ingests the UK bank holidays dataset as a simple pipeline example.

**Source:** <!-- Organisation or publisher e.g. GOVUK, Ofgem, DESNZ -->GOV.UK  
**Update cadence:** <!-- How often new data is published e.g. quarterly, monthly --> Annually  
**Pipeline run name:**: <!-- Name as registered in pipelines.yaml, also the folder name in the repo --> `example`  
**Storage prefix:** <!-- Prefix in S3 as defined in config.DATASET_PREFIX --> `example`


## Pipeline stages

### Bronze

- **Source**: <!-- URL or API the data is fetched from --> https://www.gov.uk/bank-holidays.json
- **Method**: <!-- How it is fetched e.g. HTTP request, GOV.UK Content API, web scraping --> HTTP GET request
- **Output**: <!-- What is written to S3 and in what format -->
  - `bank-holidays.json`
  - `bank-holidays.json.metadata.json`
- **Validators**: <!-- Any data quality checks run at this stage --> None

### Silver

#### <!-- table_name --> `bank_holidays`
- **Description**: <!-- What this table represents in one sentence --> One row per bank holiday per UK division.
- **Input**: <!-- What is read from bronze --> `bank-holidays.json`
- **Output**: <!-- Format, S3 path --> `bank_holidays.parquet`
- **Validators**: <!-- Checks --> Pandera schema check - validates column types and that `division` is one of the three expected values.

---

## Notes

<!-- Add any lookup tables, constants, or field definitions that a reader would want to hand.
     Delete this section if there's nothing worth including. -->

1. There are different bank holidays across England & Wales, Scotland and Northern Ireland. The `division` field therefore corresponds to UK geographical regions and can only be `england-and-wales`, `scotland`, `northern-ireland`.

---

<!-- Date and author -->
*Last updated: 25 June 2026 by Elysia Lucas*

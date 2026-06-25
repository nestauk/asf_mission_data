# [Pipeline name]

<!-- One or two sentences: what dataset this pipeline produces and why it's useful. -->

**Source:** <!-- Organisation or publisher e.g. GOVUK, Ofgem, DESNZ -->  
**Update cadence:**   <!-- How often new data is published e.g. quarterly, monthly -->  
**Pipeline run name:**: <!-- Name as registered in pipelines.yaml, also the folder name in the repo -->  
**Storage prefix:** <!-- Prefix in S3 as defined in config.DATASET_PREFIX -->  


## Pipeline stages

<!-- Delete stages that don't apply. -->

### Bronze

- **Source**: <!-- URL or API the data is fetched from -->
- **Method**: <!-- How it is fetched e.g. HTTP request, GOV.UK Content API, web scraping -->
- **Output**: <!-- What is written to S3 and in what format -->
- **Validators**: <!-- Any data quality checks run at this stage -->

### Silver

#### `table_name_1`
- **Description**: <!-- What this table represents in one sentence -->
- **Input**: <!-- What is read from bronze -->
- **Output**: <!-- Format, S3 path -->
- **Validators**: <!-- Checks -->

#### `table_name_2`
- **Description**: <!-- What this table represents in one sentence -->
- **Input**: <!-- What is read from bronze -->
- **Output**: <!-- Format, S3 path -->
- **Validators**: <!-- Checks -->

### Gold

#### `table_name_1`
- **Description**: <!-- What this table represents in one sentence -->
- **Input**: <!-- What is read from bronze -->
- **Output**: <!-- Format, S3 path -->
- **Validators**: <!-- Checks -->

#### `table_name_2`
- **Description**: <!-- What this table represents in one sentence -->
- **Input**: <!-- What is read from bronze -->
- **Output**: <!-- Format, S3 path -->
- **Validators**: <!-- Checks -->

---

## Notes

<!-- Add any lookup tables, constants, or field definitions that a reader would want to hand.
     Delete this section if there's nothing worth including. -->

---

*Last updated: <!-- DD Month YYYY --> by <!-- Name -->*

# We add this to speed up running things if you have a lot in your python environment.
from hamilton import registry

registry.disable_autoload()
from hamilton import driver

# from hamilton.io.materialization import from_, to
import transformations  # we import the module here!


if __name__ == "__main__":
    initial_columns = {  # load from actuals or wherever -- this is our initial data we use as input.
        # Note: these do not have to be all series, they could be scalar inputs.
        "key": "bronze/heat_pump_deployment_quarterly_statistics/Heat_pump_deployment_quarterly_statistics_United_Kingdom_2025_Q2.xlsx",
        "sheet_name": "Table 1.1",
        "skiprows": 5,
        "table_name": "Table 1.1",
        "id_vars": [
            "Installation quarter [note 4]",
            "Year",
            "Start of quarter",
            "End of quarter",
        ],
        "value_name": "Installations",
        "var_name": "government_scheme",
        "value_vars": None,
        "column_map": {
            "Installation quarter [note 4]": "installation_quarter",
            "Year": "year",
            "Start of quarter": "start_of_quarter",
            "End of quarter": "end_of_quarter",
            "government_scheme": "government_scheme",
            "Installations": "installations",
        },
        "expected_dtypes": {
            "end_of_quarter": "datetime64[ns]",
            "government_scheme": "str",
            "installation_quarter": "str",
            "installations": "int64",
            "start_of_quarter": "datetime64[ns]",
            "year": "Int64",
        },
        "dataset_key": "test/test_hamilton_v2.parquet",
    }
    dr = (
        driver.Builder()
        # .with_config({})  # we don't have any configuration or invariant data for this example.
        .with_modules(transformations)  # we need to tell hamilton where to load function definitions from
        # .with_adapters(base.PandasDataFrameResult())  # we want a pandas dataframe as output
        .build()
    )

    # let's create the dataframe!
    df = dr.execute(["save_table"], inputs=initial_columns)
    # `pip install sf-hamilton[visualization]` earlier you can also do
    # dr.visualize_execution(output_columns,'./my_dag.png', {})
    # dr.display_all_functions("dag.png")

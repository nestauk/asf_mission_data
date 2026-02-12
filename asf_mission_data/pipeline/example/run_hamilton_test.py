from hamilton import driver, base
from asf_mission_data.pipeline.example import hamilton_test

# Create the driver -- passing in the functions module
# and the right adapter for the result - in this case a Pandas DataFrame
dr = (
    driver.Builder().with_modules(hamilton_test).with_adapters(base.PandasDataFrameResult()).build()
)

# Execute the driver -- first argument is final variables
# As well as inputs (loaded above )
df = dr.execute(
    [
        "spend",
        "signups",
        "avg_3wk_spend",
        "spend_per_signup",
        "spend_zero_mean",
        "spend_zero_mean_unit_variance",
    ],
    inputs=load_data().to_dict(orient="series"),
    # uncomment the following to short circuit graph computation and override the value for spend_mean
    # , overrides={"spend_mean": 100.0}
)
print(df.to_string())

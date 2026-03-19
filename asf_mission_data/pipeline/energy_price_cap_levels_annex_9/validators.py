import pandas as pd
from hamilton.data_quality.base import DataValidator, ValidationResult


class TariffComponentsTotalValidator(DataValidator):
    """Checks that tariff components sum to Total_GB average."""

    def __init__(
        self,
        value_col: str,
        group_cols: list[str],
        importance: str = "fail",
    ):
        """
        Args:
            value_col: Name of the numeric value column (e.g., 'value').
            group_cols: Columns to group by.
            importance: 'fail' or 'warn'.
        """
        super().__init__(importance=importance)
        self.value_col = value_col
        self.group_cols = group_cols

    def applies_to(self, datatype: type) -> bool:
        return datatype is pd.DataFrame

    def description(self) -> str:
        return "Checks that tariff components sum to Total_GB average for each group."

    @classmethod
    def name(cls) -> str:
        return "TariffComponentsTotalValidator"

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        # Sum all components except the total
        components_sum = data.loc[data["Tariff component"] != "Total_GB average"].groupby(self.group_cols)[self.value_col].sum().reset_index()

        # Extract totals
        totals = data.loc[data["Tariff component"] == "Total_GB average"][[*self.group_cols, self.value_col]]

        # Merge sums with totals
        merged = components_sum.merge(
            totals,
            on=self.group_cols,
            suffixes=("_components", "_total"),
            how="outer",
        ).fillna(0)

        valid = (merged[f"{self.value_col}_components"].round(6) == merged[f"{self.value_col}_total"].round(6)).all()

        return ValidationResult(
            passes=valid,
            message=f"Tariff components must sum to Total_GB average for column '{self.value_col}'.",
        )

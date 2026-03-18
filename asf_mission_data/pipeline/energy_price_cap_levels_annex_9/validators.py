import pandas as pd
from hamilton.data_quality.base import DataValidator, ValidationResult


class TariffComponentsTotalValidator(DataValidator):
    """Checks that tariff components sum to Total_GB average."""

    def __init__(
        self,
        fixed_col: str,
        group_cols: list[str],
        variable_col: str | None = None,
        importance: str = "fail",
    ):
        """
        Args:
            fixed_col: Name of the fixed component column (e.g., standing charge or 'value').
            group_cols: Columns to group by.
            variable_col: Optional second column to check (e.g., consumption-based cost).
            importance: 'fail' or 'warn'.
        """
        super().__init__(importance=importance)
        self.fixed_col = fixed_col
        self.variable_col = variable_col
        self.group_cols = group_cols

    def applies_to(self, datatype: type) -> bool:
        return datatype is pd.DataFrame

    def description(self) -> str:
        return "Checks that tariff components sum to Total_GB average for each group."

    @classmethod
    def name(cls) -> str:
        return "TariffComponentsTotalValidator"

    def validate(self, data: pd.DataFrame) -> ValidationResult:
        cols_to_check = [self.fixed_col]
        if self.variable_col:
            cols_to_check.append(self.variable_col)

        # Sum all components except the total
        components_sum = data.loc[data["Tariff component"] != "Total_GB average"].groupby(self.group_cols)[cols_to_check].sum().reset_index()

        # Extract totals
        totals = data.loc[data["Tariff component"] == "Total_GB average"][[*self.group_cols, *cols_to_check]]

        # Merge sums with totals
        merged = components_sum.merge(
            totals,
            on=self.group_cols,
            suffixes=("_components", "_total"),
            how="outer",
        ).fillna(0)

        # Compare each column
        valid = True
        for col in cols_to_check:
            valid &= (merged[f"{col}_components"].round(6) == merged[f"{col}_total"].round(6)).all()

        return ValidationResult(
            passes=valid,
            message=f"Tariff components must sum to Total_GB average for columns {cols_to_check}.",
        )

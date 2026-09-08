"""Classes for custom validators used to check Hamilton node outputs in the Boiler Upgrade Scheme Statistics pipeline."""

from datetime import datetime
from typing import Type

from hamilton.data_quality.base import DataValidator, ValidationResult


class ExcelFileExtensionValidator(DataValidator):
    """Checks that the extracted file is an Excel file and has the .xlsx file extension."""

    def __init__(self, importance: str = "fail"):
        super(ExcelFileExtensionValidator, self).__init__(importance=importance)

    def applies_to(self, datatype: Type) -> bool:
        return datatype is str

    def description(self) -> str:
        return "Checks that the extracted file is an Excel file and has the .xlsx file extension."

    @classmethod
    def name(cls) -> str:
        return "ExcelFileExtensionValidator"

    def validate(self, data: str) -> ValidationResult:
        valid = data.lower().endswith(".xlsx")

        message = (f"Invalid file extension: '{data}'. Expected a filename ending with '.xlsx'.") if not valid else "Valid Excel file extension."

        return ValidationResult(passes=valid, message=message)


class WithinLastCalendarMonthValidator(DataValidator):
    """
    Checks that a publication date falls within the current or previous
    calendar month. Assumes data is stale if it's from any month before that.
    """

    def __init__(self, importance: str = "fail"):
        super(WithinLastCalendarMonthValidator, self).__init__(importance=importance)

    def applies_to(self, datatype: Type) -> bool:
        return datatype is str

    def description(self) -> str:
        return "Checks that the extracted publication date is within the current or previous calendar month."

    @classmethod
    def name(cls) -> str:
        return "WithinLastCalendarMonthValidator"

    def validate(self, data: str) -> ValidationResult:
        try:
            if not data:
                return ValidationResult(passes=False, message="Empty date string provided.")

            pub_date = datetime.strptime(data, "%d %B %Y")
            today = datetime.now()

            pub_total_months = (pub_date.year * 12) + pub_date.month
            today_total_months = (today.year * 12) + today.month

            diff = today_total_months - pub_total_months
            valid = 0 <= diff <= 1

            message = (
                f"Date '{data}' is outside the allowed 1-month freshness window."
                if not valid
                else "Date is within the allowed 1-month freshness window."
            )

            return ValidationResult(passes=valid, message=message)

        except Exception as e:
            return ValidationResult(
                passes=False,
                message=f"Failed to parse date '{data}'. Expected format: 'DD Month YYYY'. Error: {e}",
            )

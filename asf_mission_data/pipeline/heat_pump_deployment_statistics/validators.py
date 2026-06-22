"""Classes for custom validators used to check Hamilton node outputs in the Heat Pump Deployment Statistics pipeline."""

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


class WithinThreeCalendarMonthsValidator(DataValidator):
    """
    Checks that a publication date is within the current or previous 3 calendar months.
    Assumes data is stale if older than 3 months (quarterly freshness rule).
    """

    def __init__(self, importance: str = "fail"):
        super(WithinThreeCalendarMonthsValidator, self).__init__(importance=importance)

    def applies_to(self, datatype: Type) -> bool:
        return datatype is str

    def description(self) -> str:
        return "Checks that the extracted publication date is within the current or previous 3 calendar months."

    @classmethod
    def name(cls) -> str:
        return "WithinThreeCalendarMonthsValidator"

    def validate(self, data: str) -> ValidationResult:
        try:
            if not data:
                return ValidationResult(passes=False, message="Empty date string provided.")

            pub_date = datetime.strptime(data, "%d %B %Y")
            today = datetime.now()

            pub_total_months = (pub_date.year * 12) + pub_date.month
            today_total_months = (today.year * 12) + today.month

            valid = (today_total_months - pub_total_months) <= 3

            message = (
                f"Date '{data}' is outside the allowed 3-month freshness window."
                if not valid
                else "Date is within the allowed 3-month freshness window."
            )

            return ValidationResult(passes=valid, message=message)

        except Exception as e:
            return ValidationResult(passes=False, message=f"Failed to parse date '{data}'. Expected format: 'DD Month YYYY'. Error: {e}")


class StartStringValidator(DataValidator):
    """Checks that extracted string includes expected content by checking that it starts with a search string."""

    def __init__(self, expected_start_string: str, importance: str = "fail"):
        super(StartStringValidator, self).__init__(importance=importance)
        self.expected_start_string = expected_start_string

    def applies_to(self, datatype: Type) -> bool:
        return datatype is str

    def description(self) -> str:
        return "Checks that extracted string includes expected content by checking that it starts with a search string."

    @classmethod
    def name(cls) -> str:
        return "StartStringValidator"

    def validate(self, data: str) -> ValidationResult:
        valid = data.lower().startswith(self.expected_start_string.lower())

        message = (
            (f"Unexpected string: '{data}'. Expected a string starting with '{self.expected_start_string}'.")
            if not valid
            else (f"Expected start string '{self.expected_start_string}'. Read '{data}'")
        )

        return ValidationResult(passes=valid, message=message)

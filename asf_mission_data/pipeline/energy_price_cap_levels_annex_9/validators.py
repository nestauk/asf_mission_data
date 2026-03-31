import re
from datetime import datetime
from typing import Type

from hamilton.data_quality.base import DataValidator, ValidationResult

from asf_mission_data import utils


class LatestPriceCapFileUrlValidator(DataValidator):
    """Checks that the price cap file url retrieved is the expected one.

    This is based on the ofgem url structure including the publication month and year.
    """

    def __init__(
        self,
        price_cap_period_publication_dates: dict[str, str],
        importance: str = "fail",
    ):
        super(LatestPriceCapFileUrlValidator, self).__init__(importance=importance)
        self.price_cap_period_publication_dates = price_cap_period_publication_dates

    def applies_to(self, datatype: Type) -> bool:
        """Whether or not this data validator can apply to
        the specified dataset

         :param datatype:
         :return: True if it can be run on the specified type.
        """
        return datatype is str

    def description(self) -> str:
        """Gives a description of this validator.
        :return: The description of the validator as a string
        """
        return "Checks that the price cap file url retrieved is the expected one given the execution date."

    @classmethod
    def name(cls) -> str:
        """Returns the name for this validator."""
        return "LatestPriceCapFileUrlValidator"

    def validate(self, data: str) -> ValidationResult:
        """Actually performs the validation.

        :param data: data to validate
        :return: The result of validation
        """
        # Anticipated date pattern is YYYY-MM
        match = re.search(r"(\d{4}-\d{2})", data)

        if match:
            extracted_date = match.group(1)
        else:
            return ValidationResult(
                passes=False,
                message=f"Unexpected price cap file url, no date component in: {data}",
            )

        # Get expected publication dates is same format as file url date
        PUBLICATION_DATES = (datetime.fromisoformat(v) for v in self.price_cap_period_publication_dates.values())

        # Get expected price cap period
        now = datetime.now()
        latest_publication_date = max((v for v in PUBLICATION_DATES if v <= now))

        # Match anticipated date format
        latest_publication_date_str = latest_publication_date.strftime(format="%Y-%m")

        valid = extracted_date == latest_publication_date_str

        return ValidationResult(
            passes=valid,
            message=f"Expected file url date: {latest_publication_date_str}, saw date {extracted_date}",
        )


class LatestPriceCapValidator(DataValidator):
    """Checks that the price cap period retrieved is the expected one."""

    def __init__(
        self,
        price_cap_period_publication_dates: dict[str, str],
        importance: str = "fail",
    ):
        super(LatestPriceCapValidator, self).__init__(importance=importance)
        self.price_cap_period_publication_dates = price_cap_period_publication_dates

    def applies_to(self, datatype: Type) -> bool:
        """Whether or not this data validator can apply to
        the specified dataset

         :param datatype:
         :return: True if it can be run on the specified type.
        """
        return datatype is str

    def description(self) -> str:
        """Gives a description of this validator.
        :return: The description of the validator as a string
        """
        return "Checks that the price cap period retrieved is the expected one given the execution date."

    @classmethod
    def name(cls) -> str:
        """Returns the name for this validator."""
        return "LatestPriceCapValidator"

    def validate(self, data: str) -> ValidationResult:
        """Actually performs the validation.

        :param data: data to validate
        :return: The result of validation
        """
        extracted_period_interval = utils.convert_energy_price_cap_period_string_to_interval(data)
        INTERVAL_PUBLICATION_DATES = {
            utils.convert_energy_price_cap_period_string_to_interval(k): datetime.fromisoformat(v)
            for k, v in self.price_cap_period_publication_dates.items()
        }

        if extracted_period_interval not in INTERVAL_PUBLICATION_DATES:
            return ValidationResult(
                passes=False,
                message=f"Unrecognised price cap period: {extracted_period_interval}",
            )

        # Look up publication date of extracted price cap period
        publication_date = INTERVAL_PUBLICATION_DATES.get(extracted_period_interval)

        # Get expected price cap period
        now = datetime.now()
        latest_interval = max(
            (k for k, v in INTERVAL_PUBLICATION_DATES.items() if v <= now),
            key=INTERVAL_PUBLICATION_DATES.get,
        )
        latest_publication_date = INTERVAL_PUBLICATION_DATES[latest_interval]

        valid = publication_date == latest_publication_date

        return ValidationResult(
            passes=valid,
            message=f"Expected publication date: {latest_publication_date.strftime(format='%d-%m-%Y')}, "
            f"saw publication date {publication_date.strftime(format='%d-%m-%Y')}",
        )


class PriceCapValidator(DataValidator):
    """Checks that the price cap period extracted is valid."""

    def __init__(
        self,
        price_cap_period_publication_dates: dict[str, str],
        importance: str = "fail",
    ):
        super(PriceCapValidator, self).__init__(importance=importance)
        self.price_cap_period_publication_dates = price_cap_period_publication_dates
        self.expected_period_intervals = {
            utils.convert_energy_price_cap_period_string_to_interval(k) for k in price_cap_period_publication_dates.keys()
        }

    def applies_to(self, datatype: Type) -> bool:
        """Whether or not this data validator can apply to
        the specified dataset

         :param datatype:
         :return: True if it can be run on the specified type.
        """
        return datatype is str

    def description(self) -> str:
        """Gives a description of this validator.
        :return: The description of the validator as a string
        """
        return "Checks that the price cap period extracted is valid"

    @classmethod
    def name(cls) -> str:
        """Returns the name for this validator."""
        return "PriceCapValidator"

    def validate(self, data: str) -> ValidationResult:
        """Actually performs the validation.

        :param data: data to validate
        :return: The result of validation
        """
        extracted_period_interval = utils.convert_energy_price_cap_period_string_to_interval(data)

        if extracted_period_interval not in self.expected_period_intervals:
            valid_values = ", ".join(self.price_cap_period_publication_dates.keys())
            return ValidationResult(
                passes=False,
                message=f"Unrecognised price cap period: '{data}'. Expected one of: {valid_values}",
            )
        return ValidationResult(passes=True, message="Valid price cap period")

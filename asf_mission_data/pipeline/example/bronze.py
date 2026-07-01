# Bronze functions
"""
Bronze stage of the pipeline: Ingest raw data into the bronze layer.

Example downloads the UK government bank holidays JSON as a smoke test
for internet access and S3 writes.
"""

import logging
import urllib.request
from typing import cast

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.gov.uk/bank-holidays.json"


def fetch_raw_data() -> bytes:
    """Download bank holidays JSON from gov.uk."""
    logger.info("Fetching data from %s", SOURCE_URL)
    with urllib.request.urlopen(SOURCE_URL) as response:
        data = cast(bytes, response.read())
    logger.info("Downloaded %d bytes", len(data))
    return data

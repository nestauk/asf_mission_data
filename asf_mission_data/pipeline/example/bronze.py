# Bronze functions
"""
Bronze stage of the pipeline: Ingest raw data into the bronze layer.

Example downloads the UK government bank holidays JSON as a smoke test
for internet access and S3 writes.
"""

import logging

from asf_mission_data.pipeline.example.config import SOURCE_URL
from asf_mission_data.utils import fetch_raw_content

logger = logging.getLogger(__name__)


def fetch_raw_data() -> bytes:
    """Download bank holidays JSON from gov.uk."""
    return fetch_raw_content(SOURCE_URL)

"""
Static configuration values for extracting Energy Price Cap Levels Annex 9 data from Ofgem.

Bronze-layer: Source metadata and lookup parameters required to locate and download the
'Final levelised cap rates model (Annex 9)' from Ofgem's publication page.
- pipeline_name for canonical namespace
- publisher
- collection_url
- file_link_text
"""

ENERGY_PRICE_CAP_LEVELS_ANNEX_9 = {
    "pipeline_name": "energy_price_cap_levels_annex_9",
    "publisher": "Ofgem",
    "collection_url": "https://www.ofgem.gov.uk/energy-regulation/domestic-and-non-domestic/energy-pricing-rules/energy-price-cap/energy-price-cap-default-tariff-levels",
    "file_link_text": "Final levelised cap rates model (Annex 9)",
}

# Regex pattern for expected price cap period dates string format on Ofgem website
PRICE_CAP_PERIOD_STRING_PATTERN = r"(\d{1,2}\s+[A-Za-z]+\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4})"
PRICE_CAP_PERIOD_INTERVAL_PATTERN = (
    r"(?P<start_day>\d{1,2})\s+(?P<start_month>[A-Za-z]+)\s+to\s+(?P<end_day>\d{1,2})\s+(?P<end_month>[A-Za-z]+)\s+(?P<year>\d{4})"
)

PRICE_CAP_PERIOD_PUBLICATION_DATES = {
    "1 January to 31 March 2026": "2025-11-21",
    "1 April to 30 June 2026": "2026-02-25",
    "1 July to 30 September 2026": "2026-05-27",
    "1 October to 31 December 2026": "2026-08-26",
    "1 January to 31 March 2027": "2026-11-25",
    "1 April to 30 June 2027": "2027-02-24",
    "1 July to 30 September 2027": "2027-05-26",
    "1 October to 31 December 2027": "2027-08-25",
    "1 January to 31 March 2028": "2027-11-24",
    "1 April to 30 June 2028": "2028-02-23",
    "1 July to 30 September 2028": "2028-05-31",
    "1 October to 31 December 2028": "2028-08-30",
    "1 January to 31 March 2029": "2028-11-29",
    "1 April to 30 June 2029": "2029-02-28",
    "1 July to 30 September 2029": "2029-05-30",
    "1 October to 31 December 2029": "2029-08-29",
    "1 January to 31 March 2030": "2029-11-28",
    "1 April to 30 June 2030": "2030-02-27",
    "1 July to 30 September 2030": "2030-05-29",
    "1 October to 31 December 2030": "2030-08-28",
}

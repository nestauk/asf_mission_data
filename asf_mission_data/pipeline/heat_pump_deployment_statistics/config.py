"""
Static configuration values for extracting Heat Pump Deployment statistics data from DESNZ.
"""

DATASET_PREFIX = "heat_pump_deployment_statistics"
PUBLISHER = "Department for Energy Security and Net Zero"
COLLECTION_URL = "https://www.gov.uk/government/collections/heat-pump-deployment-statistics"
PAGE_LINK_TEXT = "Heat pump deployment statistics:"
FILE_LINK_TEXT = "Heat pump deployment statistics:"

# Table 1.1
TABLE_1_1_VALUE_VARS = [
    "Air-to-water heat pump installations",
    "Ground/water source heat pump installations",
    "Total heat pump installations",
]

# Table 1.2
GEOGRAPHIC_LEVEL_MAP = {
    "United Kingdom": "United Kingdom",
    "England and Wales": "England and Wales",
    "England": "National",
    "Wales": "National",
    "Scotland": "National",
    "Northern Ireland": "National",
    "North East": "Regional",
    "North West": "Regional",
    "Yorkshire and The Humber": "Regional",
    "East Midlands": "Regional",
    "West Midlands": "Regional",
    "East": "Regional",
    "London": "Regional",
    "South East": "Regional",
    "South West": "Regional",
    "Unknown": "Unknown",
}
TABLE_1_2_VALUE_VARS = list(GEOGRAPHIC_LEVEL_MAP.keys())
GEOGRAPHIC_LEVELS = list(set(GEOGRAPHIC_LEVEL_MAP.values()))
AREA_CODES_LOOKUP = {
    "United Kingdom": "K02000001",
    "England and Wales": "N/A",
    "England": "E92000001",
    "North East": "E12000001",
    "North West": "E12000002",
    "Yorkshire and The Humber": "E12000003",
    "East Midlands": "E12000004",
    "West Midlands": "E12000005",
    "East": "E12000006",
    "London": "E12000007",
    "South East": "E12000008",
    "South West": "E12000009",
    "Wales": "W92000004",
    "Scotland": "S92000003",
    "Northern Ireland": "N92000002",
    "Unknown": "N/A",
}
AREA_CODES = list(set(AREA_CODES_LOOKUP.values()))

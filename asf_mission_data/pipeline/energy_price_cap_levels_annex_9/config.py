"""
Static configuration values for extracting Energy Price Cap Levels Annex 9 data from Ofgem.

Bronze-layer: Source metadata and lookup parameters required to locate and download the
'Final levelised cap rates model (Annex 9)' from Ofgem's publication page.
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

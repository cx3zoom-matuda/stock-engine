from typing import Dict, List

# The 17 core industry sectors defined in MEMORY.md (Section 3)
CORE_SECTORS = [
    "bank",
    "insurance",
    "real_estate",
    "construction",
    "automobile",
    "machinery",
    "electronics",
    "semiconductor",
    "trading_company",
    "retail",
    "shipping",
    "energy",
    "materials",
    "pharma",
    "telecom",
    "defense",
    "railway"
]

# Maps subsectors or specific industry variants to one of the 17 core sectors
SUBSECTOR_TO_SECTOR_MAP = {
    # Core mappings
    "bank": "bank",
    "insurance": "insurance",
    "real_estate": "real_estate",
    "construction": "construction",
    "automobile": "automobile",
    "machinery": "machinery",
    "electronics": "electronics",
    "semiconductor": "semiconductor",
    "trading_company": "trading_company",
    "retail": "retail",
    "shipping": "shipping",
    "energy": "energy",
    "materials": "materials",
    "pharma": "pharma",
    "telecom": "telecom",
    "defense": "defense",
    "railway": "railway",

    # Granular mappings to core sectors
    "housing": "real_estate",
    "growth_tech": "electronics",
    "tech": "electronics",
    "gpu_related": "semiconductor",
    "data_center": "telecom",
    "cloud": "telecom",
    "power_supply": "electronics",
    "cooling": "machinery",
    "mining": "energy",
    "consumer_goods": "retail",
    "restaurant": "retail",
    "domestic_retail": "retail",
    "retail_import": "retail",
    "import_retail": "retail",
    "consumer_staples": "retail",
    "luxury_goods": "retail",
    "oil_services": "energy",
    "airline": "shipping",
    "logistics": "shipping",
    "chemicals": "materials",
    "steel": "materials",
    "utilities": "energy",
    "semiconductor_equipment": "semiconductor",
    "electronics_components": "electronics"
}

# The complete static impact matrix from MEMORY.md (Sections 5 to 14)
# Maps event strings to dictionary of sector/subsector weights
IMPACT_MATRIX = {
    "long_rate_drop": {
        "real_estate": 50,
        "construction": 30,
        "housing": 30,
        "bank": -30,
        "insurance": -20,
        "growth_tech": 20
    },
    "long_rate_spike": {
        "bank": 40,
        "insurance": 30,
        "real_estate": -40,
        "construction": -20,
        "growth_tech": -30
    },
    "inflation_high": {
        "energy": 40,
        "materials": 30,
        "mining": 30,
        "consumer_goods": -30,
        "retail": -20,
        "restaurant": -20
    },
    "inflation_low": {
        "retail": 20,
        "consumer_goods": 30,
        "tech": 10,
        "energy": -20,
        "materials": -20
    },
    "gdp_growth_accelerating": {
        "automobile": 40,
        "machinery": 40,
        "electronics": 30,
        "retail": 20,
        "shipping": 30,
        "construction": 30
    },
    "gdp_growth_slowing": {
        "consumer_staples": 20,
        "pharma": 20,
        "utilities": 20,
        "automobile": -40,
        "machinery": -30,
        "shipping": -30
    },
    "oil_price_spike": {
        "energy": 50,
        "oil_services": 40,
        "airline": -40,
        "shipping": -20,
        "chemicals": -20
    },
    "oil_price_crash": {
        "airline": 30,
        "logistics": 20,
        "chemicals": 20,
        "energy": -40
    },
    "yen_weakening": {
        "automobile": 40,
        "electronics": 40,
        "machinery": 30,
        "tourism": 20,
        "retail_import": -30,
        "airline": -20
    },
    "yen_strengthening": {
        "import_retail": 30,
        "airline": 20,
        "automobile": -40,
        "electronics": -30,
        "machinery": -30
    },
    "semiconductor_capex_cycle": {
        "semiconductor": 50,
        "semiconductor_equipment": 50,
        "electronics_components": 40,
        "materials": 20
    },
    "ai_investment_boom": {
        "semiconductor": 50,
        "gpu_related": 50,
        "data_center": 40,
        "cloud": 40,
        "power_supply": 30,
        "cooling": 20
    },
    "defense_spending_increase": {
        "defense": 50,
        "electronics": 20,
        "materials": 10
    },
    "china_recovery": {
        "machinery": 40,
        "automobile": 30,
        "electronics": 30,
        "luxury_goods": 30,
        "steel": 30
    },
    "china_slowing": {
        "luxury_goods": -40,
        "machinery": -30,
        "steel": -30,
        "automobile": -20,
        "domestic_retail": 10
    },
    "rate_hike": {
        "bank": 30,
        "insurance": 20,
        "real_estate": -30,
        "construction": -20
    },
    "rate_cut": {
        "real_estate": 30,
        "construction": 20,
        "bank": -20,
        "insurance": -10
    },
    "business_expansion": {
        "machinery": 40,
        "automobile": 30,
        "trading_company": 30,
        "materials": 20
    },
    "business_contraction": {
        "machinery": -30,
        "automobile": -30,
        "trading_company": -20,
        "materials": -20
    },
    "labor_market_tightening": {
        "retail": 20,
        "construction": -20,
        "shipping": -15
    },
    "labor_market_slack": {
        "retail": -20
    },
    "yield_curve_inversion": {
        "bank": -20,
        "real_estate": -20
    },
    "yield_curve_steepening": {
        "bank": 20,
        "insurance": 15
    },
    "china_manufacturing_slowdown": {
        "trading_company": -30,
        "shipping": -20,
        "machinery": -30,
        "materials": -20
    },
    "copper_price_spike": {
        "mining": 40,
        "materials": 30,
        "machinery": 20,
        "utilities": -20,
        "construction": -10
    },
    "copper_price_crash": {
        "utilities": 20,
        "mining": -40,
        "materials": -30,
        "machinery": -20
    },
    "gold_price_spike": {
        "mining": 40,
        "materials": 30,
        "bank": -20
    },
    "gold_price_crash": {
        "mining": -30,
        "materials": -20,
        "bank": 10
    },
    "natural_gas_spike": {
        "energy": 40,
        "oil_services": 30,
        "utilities": -30
    },
    "natural_gas_crash": {
        "utilities": 30,
        "energy": -30,
        "oil_services": -20
    },
    "liquidity_expansion": {
        "electronics": 30,
        "semiconductor": 30,
        "real_estate": 40,
        "bank": 20,
        "retail": 20
    },
    "liquidity_contraction": {
        "electronics": -35,
        "semiconductor": -30,
        "real_estate": -40,
        "bank": -20,
        "pharma": 20,
        "retail": -10
    },
    "currency_weakening": {
        "automobile": 40,
        "electronics": 40,
        "machinery": 30,
        "retail": -20,
        "shipping": -15
    },
    "currency_strengthening": {
        "retail": 30,
        "shipping": 20,
        "automobile": -40,
        "electronics": -30,
        "machinery": -30
    }
}

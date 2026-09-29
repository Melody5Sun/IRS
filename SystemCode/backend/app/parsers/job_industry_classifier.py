import re

from app.schemas.profile import TARGET_INDUSTRIES


DEFAULT_INDUSTRY = "Software & IT Services"


COMPANY_INDUSTRIES: dict[str, str] = {
    "alibaba lazada": "E-commerce",
    "amperesand": "IoT & Smart Hardware",
    "applovin": "Internet",
    "autodesk": "Enterprise Software & SaaS",
    "aumovio": "Automotive & Autonomous Driving",
    "blocktech": "Financial Technology (FinTech)",
    "bosch": "Automotive & Autonomous Driving",
    "caladan": "Financial Technology (FinTech)",
    "csit": "Cybersecurity",
    "datadog": "Cloud Computing & Big Data",
    "dbs": "Financial Technology (FinTech)",
    "drw": "Financial Technology (FinTech)",
    "google": "Internet",
    "globalfoundries": "Semiconductors & Integrated Circuits",
    "govtech": "Software & IT Services",
    "grab": "Internet",
    "grasshopper asia": "Financial Technology (FinTech)",
    "huawei": "Telecommunications",
    "jane street": "Financial Technology (FinTech)",
    "jump trading": "Financial Technology (FinTech)",
    "mastercard": "Financial Technology (FinTech)",
    "meta": "Internet",
    "micron": "Semiconductors & Integrated Circuits",
    "ncs group": "Software & IT Services",
    "point72": "Financial Technology (FinTech)",
    "shopback": "E-commerce",
    "shopee": "E-commerce",
    "sierra": "Artificial Intelligence",
    "squarepoint capital": "Financial Technology (FinTech)",
    "straitsx": "Financial Technology (FinTech)",
    "stripe": "Financial Technology (FinTech)",
    "tencent": "Internet",
    "tiktok bytedance": "Internet",
    "tower research capital": "Financial Technology (FinTech)",
    "visa": "Financial Technology (FinTech)",
    "viridien": "Cloud Computing & Big Data",
    "virtu financial": "Financial Technology (FinTech)",
    "visier": "Enterprise Software & SaaS",
    "worldquant": "Financial Technology (FinTech)",
}


def normalize_company_name(company: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", company.casefold()))


def classify_company_industry(company: str) -> str:
    normalized_company = normalize_company_name(company)
    if normalized_company in COMPANY_INDUSTRIES:
        return COMPANY_INDUSTRIES[normalized_company]

    for company_marker, industry in COMPANY_INDUSTRIES.items():
        if company_marker in normalized_company:
            return industry

    return DEFAULT_INDUSTRY


def validate_industry_table() -> None:
    invalid = set(COMPANY_INDUSTRIES.values()) - set(TARGET_INDUSTRIES)
    if invalid:
        raise ValueError(f"Unknown industries in company mapping: {sorted(invalid)}")


validate_industry_table()

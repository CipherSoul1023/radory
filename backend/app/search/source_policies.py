from typing import Literal

from pydantic import BaseModel, ConfigDict


class DiscoverySourcePolicy(BaseModel):
    model_config = ConfigDict(frozen=True)

    preferred_domains: tuple[str, ...]
    include_domains_mode: Literal["prefer", "restrict"]


DISCOVERY_SOURCE_POLICIES: dict[str, DiscoverySourcePolicy] = {
    "market_entry": DiscoverySourcePolicy(
        preferred_domains=(
            "itweb.co.za",
            "bizcommunity.com",
            "africabusinesscommunities.com",
            "businesswire.com",
            "prnewswire.com",
            "globenewswire.com",
        ),
        include_domains_mode="prefer",
    ),
    "local_headcount_growth": DiscoverySourcePolicy(
        preferred_domains=(
            "itweb.co.za",
            "bpesa.org.za",
            "prnewswire.com",
            "businesstech.co.za",
        ),
        include_domains_mode="prefer",
    ),
    "business_expansion": DiscoverySourcePolicy(
        preferred_domains=(
            "engineeringnews.co.za",
            "itweb.co.za",
            "bizcommunity.com",
            "techcentral.co.za",
            "bpesa.org.za",
            "wesgro.co.za",
        ),
        include_domains_mode="prefer",
    ),
    "rto_change": DiscoverySourcePolicy(
        preferred_domains=(
            "mybroadband.co.za",
            "businesstech.co.za",
        ),
        include_domains_mode="prefer",
    ),
    "office_opening": DiscoverySourcePolicy(
        preferred_domains=(
            "itweb.co.za",
            "engineeringnews.co.za",
            "propertywheel.co.za",
            "africabusinesscommunities.com",
            "businesswire.com",
            "prnewswire.com",
            "globenewswire.com",
            "attacq.co.za",
            "growthpoint.co.za",
        ),
        include_domains_mode="prefer",
    ),
    "office_relocation": DiscoverySourcePolicy(
        preferred_domains=(
            "propertywheel.co.za",
            "engineeringnews.co.za",
            "techcentral.co.za",
            "itweb.co.za",
            "attacq.co.za",
            "growthpoint.co.za",
            "etenders.gov.za",
        ),
        include_domains_mode="prefer",
    ),
    "leadership_buildout": DiscoverySourcePolicy(
        preferred_domains=(
            "itweb.co.za",
            "bizcommunity.com",
            "techcentral.co.za",
            "itnewsafrica.com",
            "businesswire.com",
        ),
        include_domains_mode="prefer",
    ),
    "workplace_hiring": DiscoverySourcePolicy(
        preferred_domains=(
            "linkedin.com",
            "za.indeed.com",
            "pnet.co.za",
            "careers24.com",
        ),
        include_domains_mode="prefer",
    ),
    "funding_expansion": DiscoverySourcePolicy(
        preferred_domains=(
            "disruptafrica.com",
            "itweb.co.za",
            "techcabal.com",
        ),
        include_domains_mode="prefer",
    ),
    "ma_consolidation": DiscoverySourcePolicy(
        preferred_domains=(
            "techcentral.co.za",
            "itweb.co.za",
            "compcom.co.za",
            "senspdf.jse.co.za",
            "moneyweb.co.za",
            "comptrib.co.za",
        ),
        include_domains_mode="prefer",
    ),
    "downsizing_layoffs": DiscoverySourcePolicy(
        preferred_domains=(
            "itweb.co.za",
            "moneyweb.co.za",
            "businessday.co.za",
            "engineeringnews.co.za",
            "reuters.com",
        ),
        include_domains_mode="prefer",
    ),
    "sublease_disposal": DiscoverySourcePolicy(
        preferred_domains=(
            "propertywheel.co.za",
            "moneyweb.co.za",
            "linkedin.com",
            "itweb.co.za",
        ),
        include_domains_mode="prefer",
    ),
    "business_rescue_closure": DiscoverySourcePolicy(
        preferred_domains=(
            "moneyweb.co.za",
            "engineeringnews.co.za",
            "senspdf.jse.co.za",
            "businessday.co.za",
        ),
        include_domains_mode="prefer",
    ),
}

from pydantic import BaseModel, ConfigDict


class DiscoveryQueryTemplateSet(BaseModel):
    model_config = ConfigDict(frozen=True)

    templates: tuple[str, str, str, str]


DISCOVERY_QUERY_TEMPLATES: dict[str, DiscoveryQueryTemplateSet] = {
    "market_entry": DiscoveryQueryTemplateSet(
        templates=(
            "{country} launches operations",
            "opens first office in {country}",
            "{country} establishes new subsidiary",
            "launches in {country} appoints country manager",
        ),
    ),
    "local_headcount_growth": DiscoveryQueryTemplateSet(
        templates=(
            "{market} double its workforce",
            "{market} expansion create new jobs",
            "{market} recruitment drive hundreds",
            "{market} new local team hiring expansion",
        ),
    ),
    "business_expansion": DiscoveryQueryTemplateSet(
        templates=(
            "{market} expands operations",
            "{market} opens new branch",
            "{market} expands delivery centre",
            "{market} expands production capacity",
        ),
    ),
    "rto_change": DiscoveryQueryTemplateSet(
        templates=(
            "{country} orders staff return to office",
            "{country} ending work from home",
            "{country} stricter remote working policy office days",
            "{country} senior staff required office all workdays",
        ),
    ),
    "office_opening": DiscoveryQueryTemplateSet(
        templates=(
            "opens new office in {market}",
            "{submarket} {market} new headquarters opening",
            "{market} opens regional hub office",
            "{market} opens new delivery centre",
        ),
    ),
    "office_relocation": DiscoveryQueryTemplateSet(
        templates=(
            "{market} planned move office relocation",
            "{submarket} {market} moving to larger premises",
            "{market} consolidates offices new headquarters",
            "{market} tender new office accommodation relocation",
        ),
    ),
    "leadership_buildout": DiscoveryQueryTemplateSet(
        templates=(
            "{country} appoints country manager expansion",
            "{country} expands leadership team",
            "{country} appoints first country manager",
            "{market} appoints regional director new office",
        ),
    ),
    "workplace_hiring": DiscoveryQueryTemplateSet(
        templates=(
            "{market} facilities manager vacancy",
            "{submarket} {market} office manager vacancy",
            "{market} workplace experience manager facilities vacancy",
            "{market} corporate real estate manager vacancy",
        ),
    ),
    "funding_expansion": DiscoveryQueryTemplateSet(
        templates=(
            "{country} funding grow its team",
            "raises funding to expand into {country}",
            "{country} raises funding expand operations",
            "{country} funding to build new facility",
        ),
    ),
    "ma_consolidation": DiscoveryQueryTemplateSet(
        templates=(
            "{country} announces acquisition",
            "{country} approves merger",
            "{country} companies announce merger",
            "{country} acquisition expands local operations",
        ),
    ),
    "downsizing_layoffs": DiscoveryQueryTemplateSet(
        templates=(
            "{country} announces retrenchments",
            "{country} announces job cuts Section 189 consultation",
            "{country} offers voluntary severance",
            "{country} restructuring headcount reduced",
        ),
    ),
    "sublease_disposal": DiscoveryQueryTemplateSet(
        templates=(
            "{market} sells headquarters building",
            "{submarket} {market} office sublease",
            "{market} surplus office buildings auction",
            "{market} reduced office footprint",
        ),
    ),
    "business_rescue_closure": DiscoveryQueryTemplateSet(
        templates=(
            "{country} enters business rescue",
            "{country} cease operations",
            "{country} company liquidation announced",
            "{market} announces closure facility restructuring",
        ),
    ),
}

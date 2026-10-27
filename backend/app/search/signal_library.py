from .signal_types import DiscoveryCapability, SignalCategory, SignalDefinition  # noqa: I001


SIGNAL_LIBRARY = {
    "market_entry": SignalDefinition(
        key="market_entry",
        name="Market Entry",
        category=SignalCategory.GROWTH,
        discovery_capability=DiscoveryCapability.DIRECT,
        description=("A company enters or establishes operations in a new geographic market."),
    ),
    "local_headcount_growth": SignalDefinition(
        key="local_headcount_growth",
        name="Local Headcount Growth",
        category=SignalCategory.GROWTH,
        discovery_capability=DiscoveryCapability.DIRECT,
        description="Material location-specific employee or hiring growth.",
    ),
    "business_expansion": SignalDefinition(
        key="business_expansion",
        name="Business / Geographic Expansion",
        category=SignalCategory.GROWTH,
        discovery_capability=DiscoveryCapability.DIRECT,
        description=(
            "A company expands operations, teams, or geographic presence in the target market."
        ),
    ),
    "rto_change": SignalDefinition(
        key="rto_change",
        name="RTO / Workplace Policy Change",
        category=SignalCategory.WORKPLACE,
        discovery_capability=DiscoveryCapability.DIRECT,
        description=("A company materially increases required physical office attendance."),
    ),
    "office_opening": SignalDefinition(
        key="office_opening",
        name="Office Opening / New HQ",
        category=SignalCategory.PROPERTY,
        discovery_capability=DiscoveryCapability.DIRECT,
        description=("A company establishes a new office, headquarters, or physical workplace."),
    ),
    "office_relocation": SignalDefinition(
        key="office_relocation",
        name="Office Relocation",
        category=SignalCategory.PROPERTY,
        discovery_capability=DiscoveryCapability.DIRECT,
        description=("A company moves or plans to move its workplace to another location."),
    ),
    "leadership_buildout": SignalDefinition(
        key="leadership_buildout",
        name="Leadership Buildout",
        category=SignalCategory.GROWTH,
        discovery_capability=DiscoveryCapability.CONDITIONAL,
        description=(
            "A company appoints or hires local leadership such as a Country Manager, "
            "Head of South Africa, or Managing Director."
        ),
    ),
    "workplace_hiring": SignalDefinition(
        key="workplace_hiring",
        name="Workplace / Facilities / CRE Hiring",
        category=SignalCategory.WORKPLACE,
        discovery_capability=DiscoveryCapability.CONDITIONAL,
        description=(
            "A company hires workplace, facilities, office management, or corporate "
            "real-estate roles."
        ),
    ),
    "funding_expansion": SignalDefinition(
        key="funding_expansion",
        name="Funding + Expansion",
        category=SignalCategory.GROWTH,
        discovery_capability=DiscoveryCapability.CONDITIONAL,
        description=(
            "A funding event explicitly connected to hiring, market entry, or operating expansion."
        ),
    ),
    "ma_consolidation": SignalDefinition(
        key="ma_consolidation",
        name="M&A / Consolidation",
        category=SignalCategory.CORPORATE_CHANGE,
        discovery_capability=DiscoveryCapability.CONDITIONAL,
        description=(
            "A merger or acquisition may cause expansion, consolidation, relocation, "
            "or another footprint change."
        ),
    ),
    "downsizing_layoffs": SignalDefinition(
        key="downsizing_layoffs",
        name="Downsizing / Layoffs",
        category=SignalCategory.CORPORATE_CHANGE,
        discovery_capability=DiscoveryCapability.CONDITIONAL,
        description=(
            "Significant workforce reduction that may cause rightsizing, relocation, "
            "consolidation, or space disposal."
        ),
    ),
    "sublease_disposal": SignalDefinition(
        key="sublease_disposal",
        name="Sublease / Office Disposal",
        category=SignalCategory.PROPERTY,
        discovery_capability=DiscoveryCapability.CONDITIONAL,
        description=("A company releases, markets, subleases, or disposes of existing workspace."),
    ),
    "business_rescue_closure": SignalDefinition(
        key="business_rescue_closure",
        name="Business Rescue / Closure",
        category=SignalCategory.CORPORATE_CHANGE,
        discovery_capability=DiscoveryCapability.CONDITIONAL,
        description=(
            "Business distress, closure, or restructuring that may create property churn "
            "or released space."
        ),
    ),
    "fitout_activity": SignalDefinition(
        key="fitout_activity",
        name="Fit-out / Design Activity",
        category=SignalCategory.PROPERTY,
        discovery_capability=DiscoveryCapability.NONE,
        description=(
            "A workspace designer, architect, or fit-out contractor becomes involved in "
            "a physical workplace project."
        ),
    ),
    "named_tenant": SignalDefinition(
        key="named_tenant",
        name="Named Tenant in Development",
        category=SignalCategory.PROPERTY,
        discovery_capability=DiscoveryCapability.NONE,
        description=(
            "A company is publicly identified as the tenant of a specific development or building."
        ),
    ),
    "signed_lease": SignalDefinition(
        key="signed_lease",
        name="Signed Lease Announcement",
        category=SignalCategory.PROPERTY,
        discovery_capability=DiscoveryCapability.NONE,
        description=("A lease or tenancy agreement has already been publicly confirmed."),
    ),
    "completed_move": SignalDefinition(
        key="completed_move",
        name="Completed Relocation / Office Opening",
        category=SignalCategory.PROPERTY,
        discovery_capability=DiscoveryCapability.NONE,
        description=("A company has completed a relocation or opened its new workplace."),
    ),
}

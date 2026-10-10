from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.data.south_african_geography import PREPARED_SUBMARKETS

PROPERTY_SECTORS = {"office", "industrial_logistics", "retail", "other"}
HORIZONS = {
    "up_to_6_months",
    "up_to_12_months",
    "up_to_18_months",
    "up_to_24_months",
    "as_early_as_possible",
}
OPPORTUNITY_TYPES = {
    "expansion",
    "relocation",
    "lease_renewal",
    "new_market_entry",
    "consolidation",
    "contraction_space_disposal",
    "sublease",
}
INDUSTRIES = {
    "technology",
    "financial_services",
    "professional_services",
    "healthcare",
    "manufacturing",
    "logistics",
    "retail_businesses",
    "telecommunications",
    "media",
    "energy",
    "legal_services",
    "government_public_sector",
    "other",
    "any_industry",
}
PRIORITY_FACTORS = {
    "location_fit",
    "industry_fit",
    "property_sector_fit",
    "deal_size_fit",
    "opportunity_type_fit",
    "timing",
    "evidence_strength",
}


class BrokerageSetupRequest(BaseModel):
    brokerage_name: str = Field(min_length=2, max_length=256)
    property_sectors: list[str] = Field(min_length=1, max_length=4)
    custom_property_sectors: list[str] = Field(default_factory=list, max_length=20)
    country: Literal["South Africa"] = "South Africa"
    primary_market: str = Field(min_length=2, max_length=120)
    submarkets: list[str] = Field(default_factory=list, max_length=50)
    custom_submarkets: list[str] = Field(
        default_factory=list,
        max_length=50,
        description=(
            "Deprecated compatibility field. Custom submarkets are no longer accepted; "
            "submit an empty list."
        ),
        json_schema_extra={"deprecated": True},
    )
    min_transaction_size_sqm: int = Field(gt=0, le=10_000_000)
    ideal_transaction_size_min_sqm: int = Field(gt=0, le=10_000_000)
    ideal_transaction_size_max_sqm: int = Field(gt=0, le=10_000_000)
    max_transaction_size_sqm: int = Field(gt=0, le=10_000_000)
    industries: list[str] = Field(min_length=1, max_length=14)
    custom_industries: list[str] = Field(default_factory=list, max_length=30)
    prospecting_horizon: str
    opportunity_types: list[str] = Field(min_length=1, max_length=7)
    priority_factors: list[str] = Field(min_length=1, max_length=3)

    @field_validator("brokerage_name", "primary_market", "prospecting_horizon", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "property_sectors",
        "custom_property_sectors",
        "submarkets",
        "custom_submarkets",
        "industries",
        "custom_industries",
        "opportunity_types",
        "priority_factors",
    )
    @classmethod
    def normalize_choices(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        normalized = [value.casefold() for value in cleaned]
        if len(normalized) != len(set(normalized)):
            raise ValueError("Selections must not contain duplicates")
        return cleaned

    @model_validator(mode="after")
    def validate_profile(self) -> "BrokerageSetupRequest":
        if not set(self.property_sectors) <= PROPERTY_SECTORS:
            raise ValueError("Unsupported property sector")
        if "other" in self.property_sectors and not self.custom_property_sectors:
            raise ValueError("Add at least one custom property sector when Other is selected")
        if "other" not in self.property_sectors and self.custom_property_sectors:
            raise ValueError("Custom property sectors require the Other selection")
        if self.prospecting_horizon not in HORIZONS:
            raise ValueError("Unsupported prospecting horizon")
        if not set(self.opportunity_types) <= OPPORTUNITY_TYPES:
            raise ValueError("Unsupported opportunity type")
        if not set(self.industries) <= INDUSTRIES:
            raise ValueError("Unsupported tenant industry")
        if "any_industry" in self.industries and len(self.industries) > 1:
            raise ValueError("Any industry cannot be combined with another industry")
        if "any_industry" in self.industries and self.custom_industries:
            raise ValueError("Any industry cannot be combined with custom industries")
        if "other" in self.industries and not self.custom_industries:
            raise ValueError("Add at least one custom tenant industry when Other is selected")
        if "other" not in self.industries and self.custom_industries:
            raise ValueError("Custom tenant industries require the Other selection")
        if not (
            self.min_transaction_size_sqm
            <= self.ideal_transaction_size_min_sqm
            <= self.ideal_transaction_size_max_sqm
            <= self.max_transaction_size_sqm
        ):
            raise ValueError(
                "Transaction sizes must increase from minimum through the ideal range to maximum"
            )
        if not set(self.priority_factors) <= PRIORITY_FACTORS:
            raise ValueError("Unsupported priority factor")
        if not set(self.submarkets) <= PREPARED_SUBMARKETS:
            raise ValueError("Unsupported submarket; select a prepared submarket")
        if self.custom_submarkets:
            raise ValueError("custom_submarkets is deprecated and must remain empty")
        return self


class SetupStatusResponse(BaseModel):
    status: Literal["needs_setup", "provisioning", "ready"]
    organization_id: str | None = None
    workspace_id: str | None = None


class WorkspaceSetupResponse(BaseModel):
    workspace_id: str
    organization_id: str
    organization_name: str
    status: Literal["ready"] = "ready"


class BrokerageProfileResponse(BrokerageSetupRequest):
    workspace_id: str
    organization_id: str

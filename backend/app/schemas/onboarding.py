from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

PROPERTY_SECTORS = {"Office", "Industrial / Logistics", "Retail", "Other"}
HORIZONS = {"0–6 months", "6–12 months", "12–18 months", "18–24 months", "24+ months"}
OPPORTUNITY_TYPES = {
    "Expansion",
    "Relocation",
    "Renewal",
    "New market entry",
    "Consolidation",
    "Contraction / disposal",
    "Sublease",
}
INDUSTRIES = {
    "Technology",
    "Financial services",
    "Professional services",
    "Healthcare",
    "Manufacturing",
    "Logistics",
    "Consumer goods",
    "Education",
    "Any industry",
}


class BrokerageSetupRequest(BaseModel):
    brokerage_name: str = Field(min_length=2, max_length=256)
    property_sectors: list[str] = Field(min_length=1, max_length=4)
    country: str = Field(min_length=2, max_length=100)
    primary_metro: str = Field(min_length=2, max_length=120)
    submarkets: list[str] = Field(min_length=1, max_length=50)
    minimum_sqm: int = Field(ge=0, le=10_000_000)
    ideal_minimum_sqm: int = Field(ge=0, le=10_000_000)
    ideal_maximum_sqm: int = Field(ge=0, le=10_000_000)
    maximum_sqm: int = Field(ge=0, le=10_000_000)
    industries: list[str] = Field(min_length=1, max_length=30)
    prospecting_horizon: str
    opportunity_types: list[str] = Field(min_length=1, max_length=7)
    priorities: list[str] = Field(min_length=1, max_length=3)

    @field_validator(
        "brokerage_name", "country", "primary_metro", "prospecting_horizon", mode="before"
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator(
        "property_sectors", "submarkets", "industries", "opportunity_types", "priorities"
    )
    @classmethod
    def normalize_choices(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("Choose at least one option")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Selections must not contain duplicates")
        return cleaned

    @model_validator(mode="after")
    def validate_profile(self) -> "BrokerageSetupRequest":
        if not set(self.property_sectors) <= PROPERTY_SECTORS:
            raise ValueError("Unsupported property sector")
        if self.prospecting_horizon not in HORIZONS:
            raise ValueError("Unsupported prospecting horizon")
        if not set(self.opportunity_types) <= OPPORTUNITY_TYPES:
            raise ValueError("Unsupported opportunity type")
        if not set(self.industries) <= INDUSTRIES:
            raise ValueError("Unsupported tenant industry")
        if "Any industry" in self.industries and len(self.industries) > 1:
            raise ValueError("Any industry cannot be combined with another industry")
        if not (
            self.minimum_sqm <= self.ideal_minimum_sqm <= self.ideal_maximum_sqm <= self.maximum_sqm
        ):
            raise ValueError("Transaction sizes must increase from minimum to maximum")
        available_priorities = {
            *(f"opportunity:{value}" for value in self.opportunity_types),
            *(f"submarket:{value}" for value in self.submarkets),
            *(f"industry:{value}" for value in self.industries if value != "Any industry"),
            "deal:Ideal-size deals",
            f"timing:{self.prospecting_horizon}",
        }
        if not set(self.priorities) <= available_priorities:
            raise ValueError("Priorities must be generated from the brokerage profile")
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

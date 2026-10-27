from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .query_templates import DISCOVERY_QUERY_TEMPLATES
from .source_policies import DISCOVERY_SOURCE_POLICIES


class BrokerSearchContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    country: str = Field(min_length=1)
    market: str = Field(min_length=1)
    submarkets: tuple[str, ...] = ()

    @field_validator("country", "market", mode="before")
    @classmethod
    def strip_geography(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("submarkets", mode="before")
    @classmethod
    def strip_submarkets(cls, value: object) -> object:
        if not isinstance(value, (list, tuple)):
            return value
        stripped = tuple(item.strip() if isinstance(item, str) else item for item in value)
        if any(not item for item in stripped):
            raise ValueError("Submarkets must not contain empty values")
        return stripped

    @property
    def resolved_submarket(self) -> str | None:
        return self.submarkets[0] if self.submarkets else None


class SearchPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: UUID
    workspace_id: UUID
    signal_key: str
    query_rank: int
    query_text: str
    preferred_domains: tuple[str, ...]
    include_domains_mode: Literal["prefer", "restrict"]


def build_discovery_search_plans(
    *,
    job_id: UUID,
    workspace_id: UUID,
    profile: BrokerSearchContext,
) -> list[SearchPlan]:
    plans: list[SearchPlan] = []

    for signal_key, template_set in DISCOVERY_QUERY_TEMPLATES.items():
        source_policy = DISCOVERY_SOURCE_POLICIES[signal_key]

        for query_rank, template in enumerate(template_set.templates[:2], start=1):
            plans.append(
                SearchPlan(
                    job_id=job_id,
                    workspace_id=workspace_id,
                    signal_key=signal_key,
                    query_rank=query_rank,
                    query_text=" ".join(
                        template.format(
                            country=profile.country,
                            market=profile.market,
                            submarket=profile.resolved_submarket or "",
                        ).split()
                    ),
                    preferred_domains=source_policy.preferred_domains,
                    include_domains_mode=source_policy.include_domains_mode,
                )
            )

    return plans

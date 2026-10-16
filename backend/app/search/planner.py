from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .query_templates import DISCOVERY_QUERY_TEMPLATES
from .source_policies import DISCOVERY_SOURCE_POLICIES


class BrokerSearchContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    country: str = Field(min_length=1)
    market: str = Field(min_length=1)
    submarket: str = Field(min_length=1)

    @field_validator("country", "market", "submarket", mode="before")
    @classmethod
    def strip_geography(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class SearchPlan(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: str
    broker_id: str
    signal_key: str
    query_rank: int
    query_text: str
    preferred_domains: tuple[str, ...]
    include_domains_mode: Literal["prefer", "restrict"]


def build_discovery_search_plans(
    *,
    job_id: str,
    broker_id: str,
    profile: BrokerSearchContext,
) -> list[SearchPlan]:
    plans: list[SearchPlan] = []

    for signal_key, template_set in DISCOVERY_QUERY_TEMPLATES.items():
        source_policy = DISCOVERY_SOURCE_POLICIES[signal_key]

        for query_rank, template in enumerate(template_set.templates[:2], start=1):
            plans.append(
                SearchPlan(
                    job_id=job_id,
                    broker_id=broker_id,
                    signal_key=signal_key,
                    query_rank=query_rank,
                    query_text=template.format(
                        country=profile.country,
                        market=profile.market,
                        submarket=profile.submarket,
                    ),
                    preferred_domains=source_policy.preferred_domains,
                    include_domains_mode=source_policy.include_domains_mode,
                )
            )

    return plans

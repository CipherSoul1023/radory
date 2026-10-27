from enum import StrEnum

from pydantic import BaseModel


class SignalCategory(StrEnum):
    GROWTH = "GROWTH"
    WORKPLACE = "WORKPLACE"
    PROPERTY = "PROPERTY"
    CORPORATE_CHANGE = "CORPORATE_CHANGE"


class DiscoveryCapability(StrEnum):
    DIRECT = "DIRECT"
    CONDITIONAL = "CONDITIONAL"
    NONE = "NONE"


class SignalDefinition(BaseModel):
    key: str
    name: str
    category: SignalCategory
    discovery_capability: DiscoveryCapability
    description: str

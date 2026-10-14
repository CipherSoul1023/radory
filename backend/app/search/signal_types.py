from enum import Enum

from pydantic import BaseModel


class SignalCategory(str, Enum):
    GROWTH = "GROWTH"
    WORKPLACE = "WORKPLACE"
    PROPERTY = "PROPERTY"
    CORPORATE_CHANGE = "CORPORATE_CHANGE"


class DiscoveryCapability(str, Enum):
    DIRECT = "DIRECT"
    CONDITIONAL = "CONDITIONAL"
    NONE = "NONE"


class SignalDefinition(BaseModel):
    key: str
    name: str
    category: SignalCategory
    discovery_capability: DiscoveryCapability
    description: str

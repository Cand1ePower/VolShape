from dataclasses import dataclass, field
from enum import Enum


class Capability(str, Enum):
    NUTRITION_TEXT = "nutrition_text"
    NUTRITION_PHOTO = "nutrition_photo"
    MOVEMENT_VIDEO = "movement_video"


class PricingModel(str, Enum):
    LOCAL_FREE = "local_free"
    PAY_AS_YOU_GO = "pay_as_you_go"
    STARTUP_FREE = "startup_free"
    FREE_TIER = "free_tier"
    TRIAL_ONLY = "trial_only"
    MONTHLY_SUBSCRIPTION = "monthly_subscription"
    MONTHLY_CREDITS = "monthly_credits"


class StageKind(str, Enum):
    PARSE = "parse"
    DETECT = "detect"
    CANONICALIZE = "canonicalize"
    POSE_EXTRACT = "pose_extract"
    FORM_SCORE = "form_score"
    FALLBACK = "fallback"


@dataclass(frozen=True)
class ProviderDescriptor:
    name: str
    pricing_model: PricingModel
    capabilities: tuple[Capability, ...]
    notes: str = ""


@dataclass(frozen=True)
class StagePlan:
    stage: StageKind
    providers: tuple[ProviderDescriptor, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class CapabilityPlan:
    capability: Capability
    stages: tuple[StagePlan, ...] = ()
    summary: str = ""
    design_notes: tuple[str, ...] = field(default_factory=tuple)

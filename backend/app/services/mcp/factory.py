from enum import Enum

from app.services.mcp.catalog import PROVIDERS
from app.services.mcp.types import Capability, CapabilityPlan, StageKind, StagePlan


class CostProfile(str, Enum):
    CREDIT_FIRST = "credit_first"
    DEMO_TRIAL_FIRST = "demo_trial_first"
    SUBSCRIPTION_FIRST = "subscription_first"


class CapabilityPlanFactory:
    @staticmethod
    def build(capability: Capability, cost_profile: CostProfile = CostProfile.CREDIT_FIRST) -> CapabilityPlan:
        if cost_profile == CostProfile.DEMO_TRIAL_FIRST:
            return CapabilityPlanFactory._build_demo_trial_plan(capability)
        if cost_profile == CostProfile.SUBSCRIPTION_FIRST:
            return CapabilityPlanFactory._build_subscription_plan(capability)
        return CapabilityPlanFactory._build_credit_first_plan(capability)

    @staticmethod
    def _build_credit_first_plan(capability: Capability) -> CapabilityPlan:
        if capability == Capability.NUTRITION_TEXT:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.PARSE,
                        providers=(PROVIDERS["newapi_text_parser"],),
                        notes="Use the existing LLM gateway to parse natural-language meals into candidate foods and quantities.",
                    ),
                    StagePlan(
                        stage=StageKind.CANONICALIZE,
                        providers=(PROVIDERS["fatsecret"], PROVIDERS["edamam"]),
                        notes="Normalize candidate foods into structured nutrition records.",
                    ),
                ),
                summary="LLM parsing plus free/startup nutrition lookup keeps costs close to pay-as-you-go.",
                design_notes=(
                    "Do not expose FatSecret and Edamam directly to the chat model.",
                    "Keep the stable tool name as nutrition_text.analyze.",
                ),
            )

        if capability == Capability.NUTRITION_PHOTO:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.DETECT,
                        providers=(PROVIDERS["newapi_vision"], PROVIDERS["logmeal"], PROVIDERS["ymove"]),
                        notes="Use multimodal LLM vision first, then fall back to photo-food SaaS only when needed.",
                    ),
                    StagePlan(
                        stage=StageKind.CANONICALIZE,
                        providers=(PROVIDERS["fatsecret"],),
                        notes="Map detected foods to a structured nutrition database before advice generation.",
                    ),
                ),
                summary="The cheapest viable path is multimodal LLM detection plus structured nutrition canonicalization.",
                design_notes=(
                    "Always ask the user to confirm portion size before saving nutrition totals.",
                    "Keep the stable tool name as nutrition_photo.analyze.",
                ),
            )

        if capability == Capability.MOVEMENT_VIDEO:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.POSE_EXTRACT,
                        providers=(PROVIDERS["mediapipe_local"],),
                        notes="Extract landmarks locally to avoid recurring SaaS cost.",
                    ),
                    StagePlan(
                        stage=StageKind.FORM_SCORE,
                        providers=(PROVIDERS["quickpose"], PROVIDERS["ymove"]),
                        notes="Fallback to external analysis only when the local path is insufficient.",
                    ),
                ),
                summary="Local pose extraction plus LLM coaching gives the best leverage for a low-frequency interview app.",
                design_notes=(
                    "Keep the stable tool name as movement_video.analyze.",
                    "LLM should only turn structured defects into feedback, not infer pose geometry from scratch when landmarks are available.",
                ),
            )

        raise ValueError(f"Unsupported capability: {capability}")

    @staticmethod
    def _build_demo_trial_plan(capability: Capability) -> CapabilityPlan:
        if capability == Capability.NUTRITION_TEXT:
            return CapabilityPlanFactory._build_credit_first_plan(capability)

        if capability == Capability.NUTRITION_PHOTO:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.DETECT,
                        providers=(PROVIDERS["logmeal"], PROVIDERS["ymove"], PROVIDERS["newapi_vision"]),
                        notes="Optimize for quick demo success while trial credits are still available.",
                    ),
                    StagePlan(
                        stage=StageKind.CANONICALIZE,
                        providers=(PROVIDERS["fatsecret"],),
                        notes="Canonicalize nutrition after visual detection.",
                    ),
                ),
                summary="Trial-first mode prioritizes faster food-photo demos over long-term cost efficiency.",
            )

        if capability == Capability.MOVEMENT_VIDEO:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.POSE_EXTRACT,
                        providers=(PROVIDERS["ymove"], PROVIDERS["quickpose"], PROVIDERS["mediapipe_local"]),
                        notes="Prefer packaged posture analysis during demo periods, keeping local extraction as a fallback.",
                    ),
                ),
                summary="Trial-first mode prioritizes getting a polished movement demo online quickly.",
            )

        raise ValueError(f"Unsupported capability: {capability}")

    @staticmethod
    def _build_subscription_plan(capability: Capability) -> CapabilityPlan:
        if capability == Capability.NUTRITION_TEXT:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.PARSE,
                        providers=(PROVIDERS["newapi_text_parser"],),
                        notes="Keep parsing in-house even when subscriptions are enabled.",
                    ),
                    StagePlan(
                        stage=StageKind.CANONICALIZE,
                        providers=(PROVIDERS["fatsecret"], PROVIDERS["edamam"], PROVIDERS["passio"]),
                        notes="Prefer subscribed nutrition providers for throughput and consistency.",
                    ),
                ),
                summary="Subscription-first mode expands structured nutrition coverage.",
            )

        if capability == Capability.NUTRITION_PHOTO:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.DETECT,
                        providers=(PROVIDERS["ymove"], PROVIDERS["passio"], PROVIDERS["logmeal"], PROVIDERS["newapi_vision"]),
                        notes="Use dedicated food-photo vendors before falling back to generic multimodal vision.",
                    ),
                    StagePlan(
                        stage=StageKind.CANONICALIZE,
                        providers=(PROVIDERS["fatsecret"], PROVIDERS["passio"]),
                        notes="Normalize nutrition through a structured database layer.",
                    ),
                ),
                summary="Subscription-first mode prioritizes dedicated food-photo accuracy over spend minimization.",
            )

        if capability == Capability.MOVEMENT_VIDEO:
            return CapabilityPlan(
                capability=capability,
                stages=(
                    StagePlan(
                        stage=StageKind.POSE_EXTRACT,
                        providers=(PROVIDERS["ymove"], PROVIDERS["quickpose"], PROVIDERS["mediapipe_local"]),
                        notes="Prefer dedicated movement providers, but keep local pose extraction available.",
                    ),
                ),
                summary="Subscription-first mode prioritizes packaged form-analysis velocity.",
            )

        raise ValueError(f"Unsupported capability: {capability}")

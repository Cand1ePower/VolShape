import pytest

from app.services.mcp.factory import CapabilityPlanFactory, CostProfile
from app.services.mcp.types import Capability, StageKind


pytestmark = pytest.mark.anyio


async def test_credit_first_nutrition_photo_prefers_payg_then_canonicalization():
    plan = CapabilityPlanFactory.build(Capability.NUTRITION_PHOTO, CostProfile.CREDIT_FIRST)

    assert plan.capability == Capability.NUTRITION_PHOTO
    assert plan.stages[0].stage == StageKind.DETECT
    assert [provider.name for provider in plan.stages[0].providers] == [
        "newapi_vision",
        "logmeal",
        "ymove",
    ]
    assert [provider.name for provider in plan.stages[1].providers] == ["fatsecret"]


async def test_credit_first_movement_video_prefers_local_pose_extraction():
    plan = CapabilityPlanFactory.build(Capability.MOVEMENT_VIDEO, CostProfile.CREDIT_FIRST)

    assert plan.capability == Capability.MOVEMENT_VIDEO
    assert plan.stages[0].stage == StageKind.POSE_EXTRACT
    assert [provider.name for provider in plan.stages[0].providers] == ["mediapipe_local"]
    assert [provider.name for provider in plan.stages[1].providers] == ["quickpose", "ymove"]


async def test_demo_trial_profile_reorders_photo_vendors_for_fast_demo():
    plan = CapabilityPlanFactory.build(Capability.NUTRITION_PHOTO, CostProfile.DEMO_TRIAL_FIRST)

    assert [provider.name for provider in plan.stages[0].providers] == [
        "logmeal",
        "ymove",
        "newapi_vision",
    ]


async def test_subscription_profile_allows_monthly_first_text_lookup():
    plan = CapabilityPlanFactory.build(Capability.NUTRITION_TEXT, CostProfile.SUBSCRIPTION_FIRST)

    assert plan.capability == Capability.NUTRITION_TEXT
    assert plan.stages[1].stage == StageKind.CANONICALIZE
    assert [provider.name for provider in plan.stages[1].providers] == [
        "fatsecret",
        "edamam",
        "passio",
    ]

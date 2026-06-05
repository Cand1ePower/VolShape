from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


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

    async def execute(
        self,
        initial_payload: Dict[str, Any],
        *,
        user_id: Optional[str] = None,
        db: Optional["AsyncSession"] = None,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        按 Stage 顺序依次执行所有 Provider Adapter。
        每个 Stage 只使用第一个注册了 Adapter 的 Provider（其余为备选）。
        每个 Stage 的输出会合并进下一个 Stage 的输入 payload。
        """
        from app.services.mcp.adapters import get_adapter

        ctx = {"user_id": user_id, "db": db, "session_id": session_id}
        payload = dict(initial_payload)

        for stage_plan in self.stages:
            stage_result = None
            last_exc = None

            for provider in stage_plan.providers:
                try:
                    adapter = get_adapter(provider.name)
                    stage_result = await adapter.execute(payload, **ctx)
                    if stage_result.get("success"):
                        # 将本 Stage 的 data 合并进下一阶段的 payload
                        if isinstance(stage_result.get("data"), dict):
                            payload.update(stage_result["data"])
                        else:
                            payload[stage_plan.stage.value] = stage_result["data"]
                        break
                except ValueError:
                    # 该 Provider 没有注册 Adapter（只是目录里的候选），跳过
                    continue
                except Exception as exc:
                    last_exc = exc
                    print(f"[MCP] Stage {stage_plan.stage} provider {provider.name} failed: {exc}")

            if stage_result is None and last_exc:
                raise RuntimeError(
                    f"[MCP] All providers for stage {stage_plan.stage} failed. Last error: {last_exc}"
                )

        return payload


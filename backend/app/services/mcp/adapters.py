"""
adapters.py — MCP Provider 适配器层
每个 Adapter 对应一个实际的外部能力提供方，实现统一的 execute() 接口。
CapabilityPlanFactory 生成的 Plan 将在这里被真正执行。
"""
from __future__ import annotations

import base64
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class BaseAdapter(ABC):
    """所有 MCP Provider 适配器的基类。"""

    name: str = "base"

    @abstractmethod
    async def execute(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """
        执行该 Provider 的能力。

        Args:
            payload: 输入数据（内容因 Stage 而异，如 image_bytes / food_items / video_bytes）
            **kwargs: 可选上下文 (user_id, db, session_id ...)

        Returns:
            标准化结果字典，至少包含 "success": bool 和 "data": Any
        """


# ---------------------------------------------------------------------------
# Nutrition — DETECT stage (Vision LLM)
# ---------------------------------------------------------------------------
class VisionAdapter(BaseAdapter):
    """
    调用 NewAPI 多模态 LLM 识别图片中的食物信息。
    对应 catalog 中的 newapi_vision provider。
    """

    name = "newapi_vision"

    async def execute(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from app.services.llm_client import llm_call_messages_structured

        image_bytes: bytes = payload["image_bytes"]
        user_prompt: str = payload.get("user_prompt", "请识别图片中的食物和估计份量。")
        user_id: Optional[str] = kwargs.get("user_id")
        db: Optional[AsyncSession] = kwargs.get("db")
        session_id: Optional[str] = kwargs.get("session_id")

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": user_prompt},
                ],
            }
        ]

        from app.services.media_analysis import FOOD_IMAGE_ANALYSIS_SYSTEM

        result = await llm_call_messages_structured(
            system_prompt=FOOD_IMAGE_ANALYSIS_SYSTEM,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
            user_id=user_id,
            db=db,
            session_id=session_id,
        )
        return {"success": True, "data": result}


# ---------------------------------------------------------------------------
# Nutrition — CANONICALIZE stage (FatSecret)
# ---------------------------------------------------------------------------
class FatSecretAdapter(BaseAdapter):
    """
    调用 FatSecret API 将 LLM 识别到的食物名称规范化为结构化营养数据。
    对应 catalog 中的 fatsecret provider。
    """

    name = "fatsecret"

    async def execute(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        from app.services.fatsecret import FatSecretService

        food_items: List[Dict] = payload.get("food_items", [])
        enriched = []
        for item in food_items:
            name = item.get("name", "")
            try:
                fs_result = await FatSecretService.search_food(name)
                if fs_result:
                    item = {**item, **fs_result}
            except Exception as exc:
                print(f"[FatSecretAdapter] lookup failed for '{name}': {exc}")
            enriched.append(item)
        return {"success": True, "data": enriched}


# ---------------------------------------------------------------------------
# Movement — POSE_EXTRACT stage (MediaPipe local)
# ---------------------------------------------------------------------------
class MediaPipeAdapter(BaseAdapter):
    """
    使用本地 MediaPipe 从视频中提取姿态关键点，零边际成本。
    对应 catalog 中的 mediapipe_local provider。
    """

    name = "mediapipe_local"

    async def execute(self, payload: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        import asyncio

        from app.services.media_analysis import _analyze_pose_frames

        video_bytes: bytes = payload["video_bytes"]

        loop = asyncio.get_event_loop()
        pose_result = await loop.run_in_executor(None, _analyze_pose_frames, video_bytes)
        return {"success": True, "data": pose_result}


# ---------------------------------------------------------------------------
# Registry: provider name → Adapter class
# ---------------------------------------------------------------------------
ADAPTER_REGISTRY: Dict[str, type[BaseAdapter]] = {
    "newapi_vision": VisionAdapter,
    "fatsecret": FatSecretAdapter,
    "mediapipe_local": MediaPipeAdapter,
}


def get_adapter(provider_name: str) -> BaseAdapter:
    """根据 Provider 名称返回对应 Adapter 实例。"""
    cls = ADAPTER_REGISTRY.get(provider_name)
    if cls is None:
        raise ValueError(f"[MCP] No adapter registered for provider: '{provider_name}'")
    return cls()

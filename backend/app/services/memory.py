import json
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import UserProfile, UserMetrics, Events
from app.core.config import settings

CORE_PROFILE_KEYS = {"height_cm", "gender", "birth_date", "goal", "training_years", "injuries", "medical_conditions"}
METRICS_KEYS = {"weight", "body_fat", "muscle_mass", "bench_press", "squat", "deadlift"}


async def _llm_extract_memory(user_input: str, user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
    """
    调用 LLM 从用户自然语言中提取结构化健身数据。
    使用 MEMORY_EXTRACTION_SYSTEM 提示词，返回标准化的 extracted 列表。
    """
    from app.services.llm_client import llm_call_structured
    from app.prompts import MEMORY_EXTRACTION_SYSTEM
    result = await llm_call_structured(
        system_prompt=MEMORY_EXTRACTION_SYSTEM,
        user_prompt=f"用户输入: {user_input}",
        temperature=0.0,
        max_tokens=512,
    )
    return result.get("extracted", [])


# 不值得提取的纯问候/闲聊关键词（避免对每条消息都调用 LLM）
_SKIP_EXTRACTION_KEYWORDS = {
    "hi", "hello", "你好", "嗨", "哈哈", "哈哈哈", "好的", "好", "ok", "okay",
    "谢谢", "感谢", "谢", "对", "是的", "明白", "了解", "知道了", "好的好的",
    "没事", "没关系", "不客气", "随便", "都行", "无所谓",
}


def _should_skip_extraction(text: str) -> bool:
    """
    轻量前置过滤：跳过极短消息或纯问候，避免每条闲聊都触发额外的 LLM 调用。
    策略是「宁可多送」而不是「严格过滤」，以避免漏掉有价值的数据。
    """
    stripped = text.strip()
    if len(stripped) < 4:
        return True
    if stripped.lower() in _SKIP_EXTRACTION_KEYWORDS:
        return True
    return False


class MemoryService:

    @staticmethod
    async def extract_and_sync_memory(user_input: str, user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
        extracted_items = []
        # ──────────────────────────────────────────────────────────
        # 轻量前置过滤：跳过纯问候/空消息，避免每条消息都触发 LLM 调用
        # ──────────────────────────────────────────────────────────
        if _should_skip_extraction(user_input):
            return []

        # ──────────────────────────────────────────────────────────
        # 直接调用 LLM 从用户自然语言中提取所有结构化健身数据
        # （使用 MEMORY_EXTRACTION_SYSTEM 提示词，比正则更灵活精准）
        # ──────────────────────────────────────────────────────────
        try:
            extracted_items = await _llm_extract_memory(user_input, user_id, db)
        except Exception as e:
            print(f"[Memory Extraction Error] LLM 提取失败，跳过本轮存储: {e}")
            return []

        # Sync extracted items to DB
        changes = []
        for item in extracted_items:
            key = item["key"]
            val = item["value"]

            profile = await db.get(UserProfile, user_id)
            if not profile:
                profile = UserProfile(user_id=user_id)
                db.add(profile)
                await db.flush()

            if item["type"] == "profile":
                old_val = getattr(profile, key, None)
                if old_val != val:
                    setattr(profile, key, val)
                    changes.append({"key": key, "old": old_val, "new": val, "layer": 1})

            elif item["type"] in ("metric", "exercise_pr"):
                stmt = select(UserMetrics).where(
                    UserMetrics.user_id == user_id,
                    UserMetrics.metric_type == key,
                ).order_by(desc(UserMetrics.recorded_at)).limit(1)
                result = await db.execute(stmt)
                latest_metric = result.scalars().first()

                if not latest_metric or float(latest_metric.value) != float(val):
                    new_metric = UserMetrics(
                        user_id=user_id,
                        metric_type=key,
                        value=val,
                        unit=item.get("unit", ""),
                        source="agent_extracted",
                    )
                    db.add(new_metric)
                    changes.append({
                        "key": key,
                        "old": float(latest_metric.value) if latest_metric else None,
                        "new": val,
                        "layer": 2,
                    })

            elif item["type"] == "note":
                note_event = Events(
                    user_id=user_id,
                    event_type=key,
                    payload={"value": val, "timestamp": datetime.datetime.utcnow().isoformat()},
                    event_date=datetime.date.today(),
                )
                db.add(note_event)
                changes.append({"key": key, "value": val, "layer": 3})

            elif item["type"] == "injury":
                current_injuries = profile.injuries or []
                action = item.get("action", "add")

                if action == "add" and val not in current_injuries:
                    profile.injuries = list(current_injuries) + [val]
                    changes.append({"key": "injuries", "old": current_injuries, "new": profile.injuries, "layer": 1})
                    injury_event = Events(
                        user_id=user_id, event_type="injury",
                        payload={"action": "add_injury", "injury": val},
                        event_date=datetime.date.today(),
                    )
                    db.add(injury_event)

                elif action == "remove" and val in current_injuries:
                    profile.injuries = [i for i in current_injuries if i != val]
                    changes.append({"key": "injuries", "old": current_injuries, "new": profile.injuries, "layer": 1})
                    injury_event = Events(
                        user_id=user_id, event_type="injury",
                        payload={"action": "remove_injury", "injury": val},
                        event_date=datetime.date.today(),
                    )
                    db.add(injury_event)

        if changes:
            await db.commit()
        return changes

    @staticmethod
    async def retrieve_aggregated_profile(user_id: str, db: AsyncSession) -> Dict[str, Any]:
        profile = await db.get(UserProfile, user_id)
        if not profile:
            return {
                "user_id": user_id,
                "height_cm": None, "gender": None, "goal": None,
                "training_years": None, "injuries": [], "medical_conditions": [],
                "metrics": {},
            }

        stmt = select(UserMetrics).where(UserMetrics.user_id == user_id).order_by(UserMetrics.metric_type, desc(UserMetrics.recorded_at))
        result = await db.execute(stmt)
        all_metrics = result.scalars().all()

        latest_metrics = {}
        for m in all_metrics:
            if m.metric_type not in latest_metrics:
                latest_metrics[m.metric_type] = {
                    "value": float(m.value),
                    "unit": m.unit,
                    "recorded_at": m.recorded_at.isoformat(),
                }

        return {
            "user_id": user_id,
            "height_cm": float(profile.height_cm) if profile.height_cm else None,
            "gender": profile.gender,
            "goal": profile.goal,
            "training_years": profile.training_years,
            "injuries": profile.injuries or [],
            "medical_conditions": profile.medical_conditions or [],
            "metrics": latest_metrics,
        }

    @staticmethod
    async def prune_garbage_episodic_memory(user_id: str, db: AsyncSession) -> List[int]:
        """
        Agent 记忆自我净化与垃圾回收 (Garbage Collection)。
        从数据库加载该用户的 Layer 3 近期事件流水，调用大模型识别无价值噪音并执行物理删除 (DELETE)。
        """
        from app.database.models import Events
        from app.services.llm_client import llm_call_structured
        from app.prompts import EPISODIC_MEMORY_GC_SYSTEM
        from sqlalchemy import select, delete

        # 1. 查询该用户最近的 30 条事件流水记录
        stmt = select(Events).where(Events.user_id == user_id).order_by(desc(Events.recorded_at)).limit(30)
        result = await db.execute(stmt)
        events = result.scalars().all()

        if not events:
            return []

        # 2. 序列化事件列表为大模型输入
        serialized_events = []
        for ev in events:
            serialized_events.append({
                "id": ev.id,
                "type": ev.event_type,
                "date": str(ev.event_date),
                "payload": ev.payload
            })

        # 3. 调用大模型对近期记忆做检查，识别无长期参考健身价值的数据
        user_prompt = f"当前待审查的 Layer 3 时序事件日志:\n{json.dumps(serialized_events, ensure_ascii=False)}"

        try:
            resp = await llm_call_structured(
                system_prompt=EPISODIC_MEMORY_GC_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=1024
            )
            prune_ids = resp.get("prune_event_ids", [])

            # 过滤以确保大模型返回的 ID 确实在这些事件里，防止大模型捏造/越界删除
            valid_ids = [ev.id for ev in events]
            ids_to_delete = [pid for pid in prune_ids if pid in valid_ids]

            if ids_to_delete:
                # 4. 执行物理删除 (DELETE)
                del_stmt = delete(Events).where(Events.id.in_(ids_to_delete))
                await db.execute(del_stmt)
                await db.commit()
                print(f"[Memory GC] Successfully compacted & pruned {len(ids_to_delete)} garbage events for user {user_id}. Deleted IDs: {ids_to_delete}")
                return ids_to_delete

        except Exception as e:
            print(f"[Memory GC Error] Failed to run episodic memory garbage collection: {e}")

        return []


import datetime
import json
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now_iso
from app.database.models import Events, UserMetrics, UserProfile

CORE_PROFILE_KEYS = {
    "height_cm",
    "gender",
    "birth_date",
    "goal",
    "training_years",
    "injuries",
    "medical_conditions",
}

MEMORY_EXTRACTION_SYSTEM_FLEX = """
You are VolShape's long-term memory extractor.

Goal:
- Read one user message.
- Extract stable profile facts, quantitative metrics, health/training states, injuries, and noteworthy events.
- Prefer structured facts that are useful for future coaching.
- Keys are NOT fixed. Create concise snake_case keys when needed.
- If the message only contains trivial small talk or date/time chatter, return an empty list.

Return strict JSON with this shape:
{
  "extracted": [
    {
      "type": "profile_core | metric | state | injury | event",
      "key": "snake_case_key",
      "value": "string | number | boolean | list",
      "unit": "optional string",
      "action": "optional add/remove for injury",
      "confidence": 0.0,
      "effective_at": "optional ISO timestamp or date",
      "reason": "optional short explanation"
    }
  ]
}

Guidelines:
- Use profile_core only for stable identity/profile fields such as height_cm, gender, birth_date, goal, training_years, injuries, medical_conditions.
- Use metric for quantitative values, including custom ones like resting_heart_rate, sleep_hours, waist_cm, body_temperature_c.
- Use state for latest non-numeric statuses such as current_illness, recovery_status, fatigue_status, tfcc_status, sleep_quality, stress_level.
- Use injury when the user reports a new injury/pain problem or says an old injury recovered. Put the injury/problem in value and action in add/remove.
- Use event for notable episodic facts that should appear in recent events even if they are not stable.
- If the user says they are sick, ill, feverish, injured, in pain, or unusually fatigued, that should usually yield at least one state or injury item.
- Avoid inventing facts not grounded in the message.
""".strip()

_SKIP_EXTRACTION_KEYWORDS = {
    "hi",
    "hello",
    "你好",
    "嗨",
    "哈哈",
    "好的",
    "好",
    "ok",
    "okay",
    "谢谢",
    "感谢",
    "谢了",
    "对",
    "是的",
    "明白",
    "了解",
    "知道了",
    "没事",
    "没关系",
    "不客气",
    "随便",
    "都行",
    "无所谓",
}

_GENERIC_CHAT_PATTERNS = {
    "今天几号",
    "今天不是",
    "几点",
    "星期几",
    "天气",
    "在吗",
    "收到",
}

_STATE_EVENT_TYPES = {"state", "event"}


async def _llm_extract_memory(user_input: str, user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
    from app.services.llm_client import llm_call_structured

    result = await llm_call_structured(
        system_prompt=MEMORY_EXTRACTION_SYSTEM_FLEX,
        user_prompt=f"User message: {user_input}",
        temperature=0.0,
        max_tokens=700,
        user_id=user_id,
        db=db,
        trace_enabled=False,
    )
    extracted = result.get("extracted", [])
    return extracted if isinstance(extracted, list) else []


def _should_skip_extraction(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) < 2:
        return True
    if stripped.lower() in _SKIP_EXTRACTION_KEYWORDS:
        return True
    return False


def should_capture_long_term_memory(text: str) -> bool:
    stripped = text.strip()
    if _should_skip_extraction(stripped):
        return False
    if any(pattern in stripped for pattern in _GENERIC_CHAT_PATTERNS):
        return False
    return True


def should_persist_to_mem0(item: Dict[str, Any]) -> bool:
    item_type = str(item.get("type") or "").strip().lower()
    key = str(item.get("key") or "").strip().lower()
    value = item.get("value")

    if item_type == "profile_core":
        return True

    if item_type == "injury":
        return True

    if item_type == "state":
        return key in {
            "current_illness",
            "recovery_status",
            "fatigue_status",
            "tfcc_status",
            "sleep_quality",
            "stress_level",
            "injury_status",
            "pain_status",
            "training_preference",
            "schedule_constraint",
        }

    if item_type == "event":
        if isinstance(value, str):
            lowered = value.lower()
            if any(token in lowered for token in ("doms", "酸痛", "疼", "生病", "发烧", "受伤", "出差", "停训")):
                return True
        return key in {
            "injury_event",
            "illness_event",
            "schedule_change",
            "recovery_issue",
        }

    return False


def _to_snake_case(value: str) -> str:
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", str(value).strip())
    text = re.sub(r"_+", "_", text).strip("_").lower()
    return text or "unknown_key"


def _coerce_numeric(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def _coerce_profile_value(key: str, value: Any) -> Any:
    if key == "height_cm":
        numeric = _coerce_numeric(value)
        return numeric if numeric is not None else value
    if key == "training_years":
        numeric = _coerce_numeric(value)
        return int(numeric) if numeric is not None else value
    if key == "birth_date" and isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            return value
    if key in {"injuries", "medical_conditions"}:
        if isinstance(value, list):
            return value
        return [value] if value not in (None, "") else []
    return value


def _normalize_extracted_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    raw_key = item.get("key") or item.get("field") or item.get("name")
    value = item.get("value")
    if raw_key in (None, "") or value is None:
        return None

    key = _to_snake_case(str(raw_key))
    item_type = str(item.get("type") or "").strip().lower()

    if item_type == "profile":
        item_type = "profile_core" if key in CORE_PROFILE_KEYS else "state"
    elif item_type == "note":
        item_type = "state"
    elif item_type == "exercise_pr":
        item_type = "metric"
    elif not item_type:
        item_type = "profile_core" if key in CORE_PROFILE_KEYS else "state"

    return {
        "type": item_type,
        "key": key,
        "value": value,
        "unit": item.get("unit", ""),
        "action": item.get("action"),
        "confidence": item.get("confidence"),
        "effective_at": item.get("effective_at"),
        "reason": item.get("reason"),
    }


def _build_dynamic_entry(item: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "value": item["value"],
        "type": item["type"],
        "updated_at": utc_now_iso(),
        "source": "agent_extracted",
    }
    if item.get("unit"):
        payload["unit"] = item["unit"]
    if item.get("confidence") is not None:
        payload["confidence"] = item["confidence"]
    if item.get("effective_at"):
        payload["effective_at"] = item["effective_at"]
    if item.get("reason"):
        payload["reason"] = item["reason"]
    return payload


def _set_dynamic_attribute(profile: UserProfile, key: str, item: Dict[str, Any]) -> bool:
    current = dict(profile.dynamic_attributes or {})
    next_value = _build_dynamic_entry(item)
    if current.get(key) == next_value:
        return False
    current[key] = next_value
    profile.dynamic_attributes = current
    return True


def _build_event_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "key": item["key"],
        "value": item["value"],
        "type": item["type"],
        "timestamp": utc_now_iso(),
    }
    if item.get("unit"):
        payload["unit"] = item["unit"]
    if item.get("confidence") is not None:
        payload["confidence"] = item["confidence"]
    if item.get("effective_at"):
        payload["effective_at"] = item["effective_at"]
    if item.get("reason"):
        payload["reason"] = item["reason"]
    return payload


def _changes_to_mem0_summary(changes: List[Dict[str, Any]]) -> str:
    persistable_changes = [change for change in changes if should_persist_to_mem0(change)]
    if not persistable_changes:
        return ""
    lines = ["User memory updates:"]
    for change in persistable_changes:
        key = change.get("key")
        value = change.get("new", change.get("value"))
        layer = change.get("layer")
        change_type = change.get("type")
        if change_type == "injury":
            action = change.get("action", "add")
            lines.append(f"- layer{layer}: injury {action} = {change.get('value')}")
        else:
            lines.append(f"- layer{layer}: {key} = {value}")
    return "\n".join(lines)


class MemoryService:
    @staticmethod
    async def extract_and_sync_memory(user_input: str, user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
        if not should_capture_long_term_memory(user_input):
            return []

        try:
            raw_items = await _llm_extract_memory(user_input, user_id, db)
        except Exception as exc:
            print(f"[Memory Extraction Error] {exc}")
            return []

        normalized_items = [item for item in (_normalize_extracted_item(raw) for raw in raw_items) if item]
        if not normalized_items:
            return []

        profile = await db.get(UserProfile, user_id)
        if not profile:
            profile = UserProfile(user_id=user_id)
            db.add(profile)
            await db.flush()

        changes: List[Dict[str, Any]] = []

        for item in normalized_items:
            key = item["key"]
            value = item["value"]
            item_type = item["type"]

            if item_type == "profile_core" and key in CORE_PROFILE_KEYS:
                coerced_value = _coerce_profile_value(key, value)
                old_value = getattr(profile, key, None)
                if old_value != coerced_value:
                    setattr(profile, key, coerced_value)
                    changes.append(
                        {
                            "type": item_type,
                            "key": key,
                            "value": value,
                            "old": old_value,
                            "new": coerced_value,
                            "layer": 1,
                        }
                    )
                continue

            if item_type == "injury":
                current_injuries = list(profile.injuries or [])
                action = str(item.get("action") or "add").lower()
                injury_name = str(value)

                if action == "remove" and injury_name in current_injuries:
                    profile.injuries = [inj for inj in current_injuries if inj != injury_name]
                    changes.append(
                        {
                            "type": item_type,
                            "key": "injuries",
                            "value": injury_name,
                            "action": action,
                            "old": current_injuries,
                            "new": profile.injuries,
                            "layer": 1,
                        }
                    )
                elif action != "remove" and injury_name not in current_injuries:
                    profile.injuries = current_injuries + [injury_name]
                    changes.append(
                        {
                            "type": item_type,
                            "key": "injuries",
                            "value": injury_name,
                            "action": action,
                            "old": current_injuries,
                            "new": profile.injuries,
                            "layer": 1,
                        }
                    )

                db.add(
                    Events(
                        user_id=user_id,
                        event_type="injury",
                        payload={
                            "key": key,
                            "injury": injury_name,
                            "action": action,
                            "timestamp": utc_now_iso(),
                        },
                        event_date=datetime.date.today(),
                    )
                )
                continue

            if item_type == "metric":
                numeric_value = _coerce_numeric(value)
                if numeric_value is None:
                    item_type = "state"
                    item["type"] = "state"
                else:
                    stmt = (
                        select(UserMetrics)
                        .where(UserMetrics.user_id == user_id, UserMetrics.metric_type == key)
                        .order_by(desc(UserMetrics.recorded_at))
                        .limit(1)
                    )
                    result = await db.execute(stmt)
                    latest_metric = result.scalars().first()
                    latest_value = float(latest_metric.value) if latest_metric else None
                    if latest_metric is None or latest_value != numeric_value:
                        db.add(
                            UserMetrics(
                                user_id=user_id,
                                metric_type=key,
                                value=numeric_value,
                                unit=str(item.get("unit") or ""),
                                source="agent_extracted",
                            )
                        )
                        changes.append(
                            {
                                "type": item_type,
                                "key": key,
                                "value": numeric_value,
                                "old": latest_value,
                                "new": numeric_value,
                                "layer": 2,
                            }
                        )
                    continue

            if item_type in _STATE_EVENT_TYPES or key not in CORE_PROFILE_KEYS:
                updated = _set_dynamic_attribute(profile, key, item)
                db.add(
                    Events(
                        user_id=user_id,
                        event_type=key if item_type == "state" else "event",
                        payload=_build_event_payload(item),
                        event_date=datetime.date.today(),
                    )
                )
                if updated:
                    changes.append(
                        {
                            "type": item_type,
                            "key": key,
                            "value": value,
                            "new": value,
                            "layer": 2,
                        }
                    )

        if changes:
            await db.commit()
            try:
                from app.services.mem0_client import add_memory_async

                summary = _changes_to_mem0_summary(changes)
                if summary:
                    await add_memory_async([{"role": "system", "content": summary}], user_id)
            except Exception as exc:
                print(f"[mem0 Structured Memory Error] {exc}")

        return changes

    @staticmethod
    async def retrieve_aggregated_profile(user_id: str, db: AsyncSession) -> Dict[str, Any]:
        profile = await db.get(UserProfile, user_id)
        if not profile:
            return {
                "user_id": user_id,
                "height_cm": None,
                "gender": None,
                "goal": None,
                "training_years": None,
                "injuries": [],
                "medical_conditions": [],
                "dynamic_attributes": {},
                "metrics": {},
            }

        stmt = select(UserMetrics).where(UserMetrics.user_id == user_id).order_by(
            UserMetrics.metric_type,
            desc(UserMetrics.recorded_at),
        )
        result = await db.execute(stmt)
        all_metrics = result.scalars().all()

        latest_metrics: Dict[str, Dict[str, Any]] = {}
        for metric in all_metrics:
            if metric.metric_type not in latest_metrics:
                latest_metrics[metric.metric_type] = {
                    "value": float(metric.value),
                    "unit": metric.unit,
                    "recorded_at": metric.recorded_at.isoformat(),
                }

        return {
            "user_id": user_id,
            "height_cm": float(profile.height_cm) if profile.height_cm is not None else None,
            "gender": profile.gender,
            "goal": profile.goal,
            "training_years": profile.training_years,
            "injuries": profile.injuries or [],
            "medical_conditions": profile.medical_conditions or [],
            "dynamic_attributes": profile.dynamic_attributes or {},
            "metrics": latest_metrics,
        }

    @staticmethod
    async def prune_garbage_episodic_memory(user_id: str, db: AsyncSession) -> List[int]:
        from app.prompts import EPISODIC_MEMORY_GC_SYSTEM
        from app.services.llm_client import llm_call_structured

        stmt = select(Events).where(Events.user_id == user_id).order_by(desc(Events.recorded_at)).limit(30)
        result = await db.execute(stmt)
        events = result.scalars().all()

        if not events:
            return []

        serialized_events = [
            {"id": event.id, "type": event.event_type, "date": str(event.event_date), "payload": event.payload}
            for event in events
        ]
        user_prompt = f"Current Layer 3 recent events:\n{json.dumps(serialized_events, ensure_ascii=False)}"

        try:
            resp = await llm_call_structured(
                system_prompt=EPISODIC_MEMORY_GC_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=1024,
                user_id=user_id,
                db=db,
                trace_enabled=False,
            )
            prune_ids = resp.get("prune_event_ids", [])
            valid_ids = [event.id for event in events]
            ids_to_delete = [item_id for item_id in prune_ids if item_id in valid_ids]

            if ids_to_delete:
                await db.execute(delete(Events).where(Events.id.in_(ids_to_delete)))
                await db.commit()
                print(f"[Memory GC] Deleted {len(ids_to_delete)} events for user {user_id}: {ids_to_delete}")
                return ids_to_delete
        except Exception as exc:
            print(f"[Memory GC Error] {exc}")

        return []

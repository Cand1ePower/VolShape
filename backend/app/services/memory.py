import json
import re
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import UserProfile, UserMetrics, Events
from app.core.config import settings

CORE_PROFILE_KEYS = {"height_cm", "gender", "birth_date", "goal", "training_years", "injuries", "medical_conditions"}
METRICS_KEYS = {"weight", "body_fat", "muscle_mass", "bench_press", "squat", "deadlift"}


def _should_try_llm_extraction(text: str) -> bool:
    has_number = bool(re.search(r'\d+', text))
    has_profile_kw = any(k in text for k in ["kg", "公斤", "斤", "cm", "厘米", "%", "岁", "体重", "体脂", "身高"])
    return has_number or has_profile_kw


async def _llm_extract_memory(user_input: str, user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
    from app.services.llm_client import llm_call_structured
    from app.prompts import MEMORY_EXTRACTION_SYSTEM
    result = await llm_call_structured(
        system_prompt=MEMORY_EXTRACTION_SYSTEM,
        user_prompt=f"用户输入: {user_input}",
        temperature=0.0,
        max_tokens=512,
    )
    return result.get("extracted", [])


class MemoryService:

    @staticmethod
    async def extract_and_sync_memory(user_input: str, user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
        extracted_items = []
        user_input_lower = user_input.lower()

        # Parse weight: "我体重64kg" or "体重大约 64.5 公斤"
        weight_match = re.search(r'(?:体重|weight)(?:是|大约)?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤|公斤重)?', user_input_lower)
        if weight_match:
            extracted_items.append({"key": "weight", "value": float(weight_match.group(1)), "type": "metric", "unit": "kg"})

        # Parse body fat: "体脂18%" or "体脂不是20%，是18%"
        body_fat_match = re.search(r'(?:体脂|body fat)(?:不是\d+%)?(?:是|大约)?\s*(\d+(?:\.\d+)?)\s*%', user_input_lower)
        if body_fat_match:
            extracted_items.append({"key": "body_fat", "value": float(body_fat_match.group(1)), "type": "metric", "unit": "%"})

        # Parse height
        height_match = re.search(r'(?:身高|height)(?:是|大约)?\s*(\d+(?:\.\d+)?)\s*(?:cm|厘米)?', user_input_lower)
        if height_match:
            extracted_items.append({"key": "height_cm", "value": float(height_match.group(1)), "type": "profile"})

        # Parse goal
        if "减脂" in user_input_lower or "cut" in user_input_lower:
            extracted_items.append({"key": "goal", "value": "cut", "type": "profile"})
        elif "增肌" in user_input_lower or "bulk" in user_input_lower:
            extracted_items.append({"key": "goal", "value": "bulk", "type": "profile"})

        # Parse exercise PRs (regex fast pass)
        pull_up_match = re.search(r'(?:引体向上?|pull[-\s]?ups?)\s*(?:可以|能|最多)?\s*(?:做|拉)?\s*(\d+)\s*(?:个|次|reps?)?', user_input_lower)
        if pull_up_match:
            extracted_items.append({"key": "pull_up", "value": int(pull_up_match.group(1)), "type": "exercise_pr", "unit": "reps"})
        push_up_match = re.search(r'(?:俯卧撑|push[-\s]?ups?)\s*(?:可以|能|最多)?\s*(?:做)?\s*(\d+)\s*(?:个|次|reps?)?', user_input_lower)
        if push_up_match:
            extracted_items.append({"key": "push_up", "value": int(push_up_match.group(1)), "type": "exercise_pr", "unit": "reps"})
        bench_match = re.search(r'(?:卧推|bench[-\s]?press)\s*(?:可以|能|最多)?\s*(?:推)?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤)?', user_input_lower)
        if bench_match:
            extracted_items.append({"key": "bench_press", "value": float(bench_match.group(1)), "type": "exercise_pr", "unit": "kg"})
        squat_match = re.search(r'(?:深蹲|squat)\s*(?:可以|能|最多)?\s*(?:蹲)?\s*(\d+(?:\.\d+)?)\s*(?:kg|公斤)?', user_input_lower)
        if squat_match:
            extracted_items.append({"key": "squat", "value": float(squat_match.group(1)), "type": "exercise_pr", "unit": "kg"})

        # Parse sleep
        sleep_hour_match = re.search(r'(?:睡|眠)(?:了|觉)?\s*(\d+(?:\.\d+)?)\s*(?:小时|个?钟|h)', user_input_lower)
        if sleep_hour_match:
            extracted_items.append({"key": "sleep_hours", "value": float(sleep_hour_match.group(1)), "type": "note"})
        if any(k in user_input_lower for k in ["没睡好", "失眠", "睡不好", "睡得很差", "熬夜", "通宵"]):
            extracted_items.append({"key": "sleep_quality", "value": "poor", "type": "note"})
        elif any(k in user_input_lower for k in ["睡得好", "睡得很香", "睡眠不错"]):
            extracted_items.append({"key": "sleep_quality", "value": "good", "type": "note"})

        # Parse energy/soreness
        if any(k in user_input_lower for k in ["状态很好", "精力充沛", "元气满满", "活力"]):
            extracted_items.append({"key": "energy_level", "value": "high", "type": "note"})
        elif any(k in user_input_lower for k in ["很累", "疲惫", "没精神", "状态不好", "没劲"]):
            extracted_items.append({"key": "energy_level", "value": "low", "type": "note"})
        if "酸" in user_input_lower or "酸痛" in user_input_lower:
            body_parts = {"胸": "chest", "背": "back", "腿": "legs", "肩": "shoulders", "手臂": "arms", "腹": "abs"}
            for cn, en in body_parts.items():
                if cn in user_input_lower:
                    extracted_items.append({"key": "soreness", "value": en, "type": "note"})
                    break
            else:
                extracted_items.append({"key": "soreness", "value": "general", "type": "note"})

        # Parse diet notes
        if any(k in user_input_lower for k in ["没吃", "空腹", "还没吃", "没吃东西"]):
            extracted_items.append({"key": "diet_note", "value": "skipped_meal", "type": "note"})
        if any(k in user_input_lower for k in ["吃撑", "吃多", "暴食", "吃太多"]):
            extracted_items.append({"key": "diet_note", "value": "overeaten", "type": "note"})
        if any(k in user_input_lower for k in ["肌酸", "creatine"]):
            extracted_items.append({"key": "supplement", "value": "creatine", "type": "note"})
        if any(k in user_input_lower for k in ["蛋白粉", "乳清", "whey"]):
            extracted_items.append({"key": "supplement", "value": "whey_protein", "type": "note"})

        # Parse injury recovery
        is_recovery = any(k in user_input_lower for k in ["好了", "康复", "痊愈", "恢复", "没有", "消除", "痊愈了", "康复了", "消退"])

        if "左肩" in user_input_lower or "肩袖" in user_input_lower:
            extracted_items.append({
                "key": "injuries", "value": "左肩袖劳损", "type": "injury",
                "action": "remove" if is_recovery else "add",
            })
        elif "腰" in user_input_lower or "腰肌" in user_input_lower:
            extracted_items.append({
                "key": "injuries", "value": "轻度腰肌劳损", "type": "injury",
                "action": "remove" if is_recovery else "add",
            })

        # Event logging for non-query inputs
        is_query = any(k in user_input_lower for k in ["计划", "安排", "定制", "设计", "怎么", "如何", "帮我", "想要", "求", "我想练"])

        if not is_query and not extracted_items and any(kw in user_input_lower for kw in ["练", "吃", "卧推", "哑铃", "米饭", "鸡胸肉"]):
            event_type = "training" if any(k in user_input_lower for k in ["练", "卧推", "哑铃"]) else "diet"
            event = Events(
                user_id=user_id,
                event_type=event_type,
                payload={"raw_input": user_input, "timestamp": datetime.datetime.utcnow().isoformat()},
                event_date=datetime.date.today(),
            )
            db.add(event)
            await db.flush()
            return [{"key": "event", "value": event_type, "type": "event"}]

        # LLM fallback for complex inputs
        if not extracted_items and _should_try_llm_extraction(user_input_lower):
            try:
                llm_items = await _llm_extract_memory(user_input, user_id, db)
                extracted_items.extend(llm_items)
            except Exception:
                pass

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

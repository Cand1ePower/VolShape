"""
user_insights.py — 用户洞察模块
负责: /mem0 语义记忆查询、/profile 聚合画像（含营养摘要）
从 chat.py 拆分而来
"""
import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.database.models import DietRecord, Events, WeeklySummary
from app.database.session import get_db
from app.services.memory import MemoryService

router = APIRouter()


@router.get("/mem0")
async def get_mem0_memory(user_id: str = Depends(get_current_user_id)):
    """返回该用户在 Mem0 中的全部语义记忆条目。"""
    from app.services.mem0_client import get_all_memory_async

    memories = await get_all_memory_async(user_id)
    return {"memories": memories}


@router.get("/profile")
async def get_user_aggregated_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """
    返回用户完整的聚合画像，包含：
    - 结构化画像 (L1/L2/L3)
    - 近期训练/饮食事件
    - 周度总结
    - 营养摘要（今日 / 近7天 / 最近一餐）
    """
    profile = await MemoryService.retrieve_aggregated_profile(user_id, db)

    # ---------- 近期事件 ----------
    event_stmt = select(Events).where(Events.user_id == user_id).order_by(desc(Events.event_date)).limit(30)
    event_result = await db.execute(event_stmt)
    events = event_result.scalars().all()
    recent_events = [
        {"type": event.event_type, "date": str(event.event_date), "payload": event.payload}
        for event in events
    ]

    # ---------- 周度总结 ----------
    summary_stmt = (
        select(WeeklySummary)
        .where(WeeklySummary.user_id == user_id)
        .order_by(desc(WeeklySummary.week_start))
        .limit(4)
    )
    summary_result = await db.execute(summary_stmt)
    summaries = summary_result.scalars().all()
    weekly_summaries = [
        {"week_start": str(s.week_start), "text": s.summary_text, "snapshot": s.metrics_snapshot}
        for s in summaries
    ]

    # ---------- 营养摘要 ----------
    recent_records_stmt = (
        select(DietRecord)
        .where(DietRecord.user_id == user_id)
        .order_by(desc(DietRecord.recorded_at))
        .limit(10)
    )
    recent_records_result = await db.execute(recent_records_stmt)
    recent_records = recent_records_result.scalars().all()

    today = datetime.date.today()
    seven_days_ago = today - datetime.timedelta(days=6)

    today_summary = {"calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "meals_count": 0}
    week_summary  = {"calories": 0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "meals_count": 0}

    serialized_records = []
    for record in recent_records:
        record_date = record.recorded_at.date() if record.recorded_at else today
        if record_date == today:
            today_summary["calories"]    += int(record.total_calories or 0)
            today_summary["protein"]     += float(record.total_protein or 0.0)
            today_summary["carbs"]       += float(record.total_carbs or 0.0)
            today_summary["fat"]         += float(record.total_fat or 0.0)
            today_summary["meals_count"] += 1

        if record_date >= seven_days_ago:
            week_summary["calories"]    += int(record.total_calories or 0)
            week_summary["protein"]     += float(record.total_protein or 0.0)
            week_summary["carbs"]       += float(record.total_carbs or 0.0)
            week_summary["fat"]         += float(record.total_fat or 0.0)
            week_summary["meals_count"] += 1

        serialized_records.append(
            {
                "id": record.id,
                "meal_type": record.meal_type,
                "food_items": record.food_items or [],
                "total_calories": int(record.total_calories or 0),
                "total_protein":  float(record.total_protein or 0.0),
                "total_carbs":    float(record.total_carbs or 0.0),
                "total_fat":      float(record.total_fat or 0.0),
                "recorded_at":    record.recorded_at.isoformat() if record.recorded_at else None,
            }
        )

    days_span = 7
    nutrition_summary = {
        "today": {
            **today_summary,
            "protein": round(today_summary["protein"], 1),
            "carbs":   round(today_summary["carbs"], 1),
            "fat":     round(today_summary["fat"], 1),
        },
        "last7days": {
            **week_summary,
            "protein":     round(week_summary["protein"], 1),
            "carbs":       round(week_summary["carbs"], 1),
            "fat":         round(week_summary["fat"], 1),
            "avg_calories": round(week_summary["calories"] / days_span, 1) if week_summary["calories"] else 0.0,
            "avg_protein":  round(week_summary["protein"]  / days_span, 1) if week_summary["protein"]  else 0.0,
        },
        "latest_record":  serialized_records[0] if serialized_records else None,
        "recent_records": serialized_records[:4],
    }

    return {
        "profile":          profile,
        "recent_events":    recent_events,
        "weekly_summaries": weekly_summaries,
        "nutrition_summary": nutrition_summary,
    }

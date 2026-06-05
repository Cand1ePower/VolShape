import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Events


def _session_load(payload: dict) -> float:
    duration = float(payload.get("duration_minutes", 45) or 45)
    rpe = float(payload.get("rpe", 7) or 7)
    return duration * rpe


async def calculate_acwr(
    user_id: str,
    new_session_duration: int,
    new_session_rpe: int,
    db: AsyncSession,
) -> dict:
    """
    Calculate ACWR (Acute:Chronic Workload Ratio) for the proposed session.

    We deliberately avoid inventing a chronic baseline when historical data is
    too sparse. In that case we return `risk="insufficient_history"` so the
    evaluator can be explicit about the uncertainty instead of presenting a
    misleading score.
    """

    today = datetime.date.today()
    acute_start = today - datetime.timedelta(days=7)
    chronic_start = today - datetime.timedelta(days=28)

    stmt = select(Events).where(
        Events.user_id == user_id,
        Events.event_type == "training",
        Events.event_date >= chronic_start,
        Events.event_date <= today,
    )
    result = await db.execute(stmt)
    training_events = result.scalars().all()

    acute_load_sum = float(new_session_duration) * float(new_session_rpe)
    chronic_load_sum = 0.0

    distinct_dates = set()
    for event in training_events:
        payload = event.payload or {}
        load = _session_load(payload)
        chronic_load_sum += load
        distinct_dates.add(event.event_date)

        if event.event_date >= acute_start:
            acute_load_sum += load

    history_days = 0
    if distinct_dates:
        history_days = (today - min(distinct_dates)).days + 1

    has_enough_history = len(training_events) >= 4 and history_days >= 14 and chronic_load_sum > 0
    if not has_enough_history:
        return {
            "acwr": None,
            "risk": "insufficient_history",
            "acute_load": round(acute_load_sum, 2),
            "chronic_load": round(chronic_load_sum, 2),
            "weekly_chronic_avg": None,
            "history_days": history_days,
            "training_sessions_28d": len(training_events),
        }

    weekly_chronic_avg = chronic_load_sum / 4.0
    acwr = round(acute_load_sum / weekly_chronic_avg, 2) if weekly_chronic_avg > 0 else None

    if acwr is None:
        risk = "insufficient_history"
    elif acwr > 1.5:
        risk = "high"
    elif acwr > 1.3:
        risk = "moderate"
    else:
        risk = "safe"

    return {
        "acwr": acwr,
        "risk": risk,
        "acute_load": round(acute_load_sum, 2),
        "chronic_load": round(chronic_load_sum, 2),
        "weekly_chronic_avg": round(weekly_chronic_avg, 2),
        "history_days": history_days,
        "training_sessions_28d": len(training_events),
    }

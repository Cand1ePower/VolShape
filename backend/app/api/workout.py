import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id
from app.database.models import Events, TrainingPlan
from app.database.session import get_db

router = APIRouter()


class ApplyRequest(BaseModel):
    plan_id: str
    plan_json: dict


class SaveProgressRequest(BaseModel):
    plan_id: str
    completion_data: dict


class CompleteRequest(BaseModel):
    plan_id: str
    completion_data: dict


def summarize_completion(plan_json: dict, completion: dict) -> dict:
    exercises = plan_json.get("exercises", []) if isinstance(plan_json, dict) else []
    total_sets = int(completion.get("total_sets") or 0) if isinstance(completion, dict) else 0
    if total_sets <= 0:
        total_sets = sum(int(ex.get("sets") or 0) for ex in exercises if isinstance(ex, dict))

    completed_sets = 0
    completed_keys = []
    if isinstance(completion, dict):
        if isinstance(completion.get("completed_keys"), list):
            completed_keys = [str(k) for k in completion.get("completed_keys", [])]
            completed_sets = int(completion.get("completed_sets") or len(completed_keys))
        else:
            for value in completion.values():
                if isinstance(value, dict):
                    completed_sets += sum(1 for done in value.values() if done)

    return {
        "total_sets": total_sets,
        "completed_sets": completed_sets,
        "completed_keys": completed_keys,
        "completion_rate": round(completed_sets / total_sets, 2) if total_sets > 0 else 0,
    }


def _plan_payload(plan: TrainingPlan) -> dict:
    return {
        "id": plan.id,
        "plan_json": plan.plan_json,
        "status": plan.status,
        "target_date": str(plan.target_date),
        "completion_data": plan.completion_data,
        "completion_summary": summarize_completion(plan.plan_json or {}, plan.completion_data or {}),
    }


@router.get("/active")
async def get_active_workout(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(TrainingPlan)
        .where(TrainingPlan.user_id == user_id, TrainingPlan.status == "training")
        .order_by(desc(TrainingPlan.created_at))
        .limit(1)
    )
    res = await db.execute(stmt)
    plan = res.scalars().first()
    return {"plan": _plan_payload(plan) if plan else None}


@router.get("/all_status")
async def get_all_workout_status(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    stmt = select(TrainingPlan).where(TrainingPlan.user_id == user_id).order_by(desc(TrainingPlan.created_at)).limit(50)
    res = await db.execute(stmt)
    plans = res.scalars().all()
    return {"status_map": {p.id: p.status for p in plans}}


@router.get("/history")
async def get_workout_history(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(TrainingPlan)
        .where(TrainingPlan.user_id == user_id, TrainingPlan.status == "completed")
        .order_by(desc(TrainingPlan.created_at))
        .limit(20)
    )
    res = await db.execute(stmt)
    return {"history": [_plan_payload(p) for p in res.scalars().all()]}


@router.post("/apply")
async def apply_workout(req: ApplyRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    plan = await db.get(TrainingPlan, req.plan_id)

    res = await db.execute(select(TrainingPlan).where(TrainingPlan.user_id == user_id, TrainingPlan.status == "training"))
    for active_plan in res.scalars().all():
        active_plan.status = "active"

    if not plan:
        plan = TrainingPlan(
            id=req.plan_id,
            user_id=user_id,
            plan_json=req.plan_json,
            target_date=datetime.date.today(),
            status="training",
            completion_data={},
        )
        db.add(plan)
    elif plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="未找到该训练计划")
    else:
        plan.status = "training"

    await db.commit()
    return {"status": "training", "plan_id": plan.id}


@router.post("/save_progress")
async def save_progress(req: SaveProgressRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    plan = await db.get(TrainingPlan, req.plan_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="未找到该训练计划")

    plan.completion_data = req.completion_data
    plan.status = "training"
    await db.commit()
    return {"status": "training", "plan_id": plan.id, "completion": summarize_completion(plan.plan_json or {}, plan.completion_data or {})}


@router.post("/complete")
async def complete_workout(req: CompleteRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    plan = await db.get(TrainingPlan, req.plan_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="未找到该训练计划")

    plan.status = "completed"
    plan.completion_data = req.completion_data

    plan_json = plan.plan_json or {}
    exercises = plan_json.get("exercises", [])
    completion_summary = summarize_completion(plan_json, req.completion_data or {})
    db.add(
        Events(
            user_id=user_id,
            event_type="training",
            payload={
                "plan_id": plan.id,
                "duration_minutes": plan_json.get("duration_minutes", 45),
                "rpe": plan_json.get("estimated_rpe", 7),
                "exercises_count": len(exercises),
                "total_sets": completion_summary["total_sets"],
                "completed_sets": completion_summary["completed_sets"],
                "completed_keys": completion_summary["completed_keys"],
                "completion_rate": completion_summary["completion_rate"],
            },
            event_date=datetime.date.today(),
        )
    )

    await db.commit()
    return {"status": "completed", "plan_id": plan.id, "completion": completion_summary}


@router.post("/abandon")
async def abandon_workout(req: SaveProgressRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    plan = await db.get(TrainingPlan, req.plan_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="未找到该训练计划")

    plan.status = "abandoned"
    await db.commit()
    return {"status": "abandoned", "plan_id": plan.id}


@router.get("/abandoned_history")
async def get_abandoned_workout_history(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    stmt = (
        select(TrainingPlan)
        .where(TrainingPlan.user_id == user_id, TrainingPlan.status == "abandoned")
        .order_by(desc(TrainingPlan.created_at))
        .limit(20)
    )
    res = await db.execute(stmt)
    return {"history": [_plan_payload(p) for p in res.scalars().all()]}

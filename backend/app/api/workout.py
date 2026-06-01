import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from app.core.auth import get_current_user_id
from app.database.session import get_db
from app.database.models import TrainingPlan, Events

router = APIRouter()


class ApplyRequest(BaseModel):
    plan_id: str
    plan_json: dict # 🌟 接收前端卡片完整计划数据，在应用时才延迟落库


class SaveProgressRequest(BaseModel):
    plan_id: str
    completion_data: dict


class CompleteRequest(BaseModel):
    plan_id: str
    completion_data: dict


@router.get("/active")
async def get_active_workout(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """
    拉取该用户当前处于训练中 ("training") 的计划。
    用于在前端强刷网页或重新进入时，还原高保真的训练现场。
    """
    stmt = select(TrainingPlan).where(
        TrainingPlan.user_id == user_id,
        TrainingPlan.status == "training"
    ).order_by(desc(TrainingPlan.created_at)).limit(1)
    
    res = await db.execute(stmt)
    plan = res.scalars().first()
    if not plan:
        return {"plan": None}
        
    return {
        "plan": {
            "id": plan.id,
            "plan_json": plan.plan_json,
            "status": plan.status,
            "target_date": str(plan.target_date),
            "completion_data": plan.completion_data
        }
    }


@router.get("/all_status")
async def get_all_workout_status(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """
    获取用户所有计划的状态映射。
    用于聊天卡片在渲染时批量判断是显示“应用计划”、“应用中”还是“已完成”。
    """
    stmt = select(TrainingPlan).where(
        TrainingPlan.user_id == user_id
    ).order_by(desc(TrainingPlan.created_at)).limit(50)
    
    res = await db.execute(stmt)
    plans = res.scalars().all()
    status_map = {p.id: p.status for p in plans}
    return {"status_map": status_map}


@router.get("/history")
async def get_workout_history(user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """
    获取用户的历史已完成训练计划。
    """
    stmt = select(TrainingPlan).where(
        TrainingPlan.user_id == user_id,
        TrainingPlan.status == "completed"
    ).order_by(desc(TrainingPlan.created_at)).limit(20)
    
    res = await db.execute(stmt)
    plans = res.scalars().all()
    
    history = []
    for p in plans:
        history.append({
            "id": p.id,
            "plan_json": p.plan_json,
            "status": p.status,
            "target_date": str(p.target_date),
            "completion_data": p.completion_data
        })
        
    return {"history": history}


@router.post("/apply")
async def apply_workout(req: ApplyRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """
    用户在聊天界面点击“应用”计划。
    在此处【真正将训练计划保存创建并写入 training_plans 物理表中】，默认状态为 "training" (未完成进行中状态)。
    并将此用户的其他正处于 "training" 的计划复位成 "active"（重置为待应用），保证单一活跃计划。
    """
    # 1. 物理检查该 plan_id 在数据库中是否已存在（万一重复应用）
    plan = await db.get(TrainingPlan, req.plan_id)
    
    # 2. 复位其他活跃状态的计划为 active
    stmt = select(TrainingPlan).where(
        TrainingPlan.user_id == user_id,
        TrainingPlan.status == "training"
    )
    res = await db.execute(stmt)
    other_plans = res.scalars().all()
    for p in other_plans:
        p.status = "active"
        
    if not plan:
        # 3. 在此处真正往 training_plans 数据库表写入新纪录！默认 status = "training" (未完成)
        plan = TrainingPlan(
            id=req.plan_id,
            user_id=user_id,
            plan_json=req.plan_json,
            target_date=datetime.date.today(),
            status="training",
            completion_data={}
        )
        db.add(plan)
    else:
        # 如果已经存在，直接更新为 training
        plan.status = "training"
        
    await db.commit()
    return {"status": "training", "plan_id": plan.id}


@router.post("/save_progress")
async def save_progress(req: SaveProgressRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """
    组打卡实时进度暂存。
    用于在用户每完成一组勾选时，静默把进度同步落库，但【物理维持 status='training' 不变】。
    完美保证刷新页面打勾不丢，且计划绝不会提前归档消失！
    """
    plan = await db.get(TrainingPlan, req.plan_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="未找到该训练计划")
        
    # 同步打卡明细进度，强制保证 status 为 training 进行中
    plan.completion_data = req.completion_data
    plan.status = "training"
    await db.commit()
    
    return {"status": "training", "plan_id": plan.id}


@router.post("/complete")
async def complete_workout(req: CompleteRequest, user_id: str = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """
    训练彻底完成打卡。将 status 物理变更为 "completed" 归档。
    🌟 彻底剥离、删除向 Layer 3 Events 写入打卡事件流的余波冗余逻辑，保持 Events 事件表的绝对纯净，彻底实现干净解耦的专表专用！
    """
    plan = await db.get(TrainingPlan, req.plan_id)
    if not plan or plan.user_id != user_id:
        raise HTTPException(status_code=404, detail="未找到该训练计划")
        
    # 修改状态为已完成 (已归档)
    plan.status = "completed"
    plan.completion_data = req.completion_data
    
    await db.commit()
    return {"status": "completed", "plan_id": plan.id}

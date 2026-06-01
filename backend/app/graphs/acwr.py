import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Events

async def calculate_acwr(
    user_id: str,
    new_session_duration: int,
    new_session_rpe: int,
    db: AsyncSession
) -> dict:
    """
    急性与慢性负荷比值 (Acute-to-Chronic Workload Ratio, ACWR) 损伤预防计算模型。
    急性负荷 (Acute Load): 过去 7 天内所有训练的（负荷 = RPE * 运动时长）总和。
    慢性负荷 (Chronic Load): 过去 28 天内所有训练（4周）的日均/周均负荷总和。
    安全区间: 0.8 - 1.3
    高风险警戒区间: > 1.5 (运动医学证实该区间损伤风险成倍增高，Evaluator 智能体必须进行阻断/重写计划)
    """
    today = datetime.date.today()
    acute_start = today - datetime.timedelta(days=7)
    chronic_start = today - datetime.timedelta(days=28)

    # 1. 查询过去 28 天内的所有训练明细事件
    stmt = select(Events).where(
        Events.user_id == user_id,
        Events.event_type == "training",
        Events.event_date >= chronic_start,
        Events.event_date <= today
    )
    result = await db.execute(stmt)
    training_events = result.scalars().all()

    # 2. 统计负荷 (Load = duration * rpe)
    # 模拟默认无训练时提供基础小基数负荷以防止除以零
    acute_load_sum = new_session_duration * new_session_rpe
    chronic_load_sum = 100.0  # 基础慢性底数 load

    for event in training_events:
        payload = event.payload or {}
        duration = payload.get("duration_minutes", 45)
        rpe = payload.get("rpe", 7)
        load = duration * rpe
        
        if event.event_date >= acute_start:
            acute_load_sum += load
        
        chronic_load_sum += load

    # 3. 计算比值：急性负荷 / (慢性负荷 / 4周)
    # 将 28 天平均到 4 周进行计算
    weekly_chronic_avg = chronic_load_sum / 4.0
    acwr = round(acute_load_sum / weekly_chronic_avg, 2) if weekly_chronic_avg > 0 else 1.0

    # 4. 判定伤病风险
    if acwr > 1.5:
        risk = "high"  # 极高损伤危险，必须拒绝计划
    elif acwr > 1.3:
        risk = "moderate"  # 中度负荷增加，应当警告
    else:
        risk = "safe"  # 绿灯安全，ACWR 在 0.8-1.3 最适甜美点
        
    return {
        "acwr": acwr,
        "risk": risk,
        "acute_load": acute_load_sum,
        "chronic_load": chronic_load_sum
    }

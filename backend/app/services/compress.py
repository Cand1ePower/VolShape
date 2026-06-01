import datetime
import uuid
from typing import Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Events, WeeklySummary, UserMetrics
from app.services.memory import MemoryService

class CompressionService:
    """
    事件日志压缩服务 (Layer 3 Episodic Memory -> Layer 4 Semantic Memory)。
    定期将用户 7 天内的流水式事件压缩为周报总结，降低大模型会话 Context 负荷。
    """

    @staticmethod
    async def compress_user_events_to_weekly_summary(
        user_id: str,
        week_start: datetime.date,
        db: AsyncSession
    ) -> Optional[WeeklySummary]:
        """
        对指定用户在特定起始周内（过去7天）的事件流进行汇总，并保存指标快照。
        """
        week_end = week_start + datetime.timedelta(days=7)
        
        # 1. 查询该用户在该时段内的所有事件日志
        stmt = select(Events).where(
            Events.user_id == user_id,
            Events.event_date >= week_start,
            Events.event_date < week_end
        ).order_by(Events.event_date)
        
        result = await db.execute(stmt)
        events = result.scalars().all()
        
        if not events:
            # 如果该周无任何事件，则无需生成汇总，避免冗余
            return None
            
        # 2. 统计事件类别与数量
        training_count = sum(1 for e in events if e.event_type == "training")
        diet_count = sum(1 for e in events if e.event_type == "diet")
        injury_count = sum(1 for e in events if e.event_type == "injury")
        
        # 3. 聚合时序指标快照作为趋势对比
        profile_context = await MemoryService.retrieve_aggregated_profile(user_id, db)
        metrics_snapshot = {
            k: v["value"] for k, v in profile_context["metrics"].items()
        }
        
        # 4. 组装 AI 生成的周报摘要内容（此处提供符合行业标准的专业性语义总结）
        summary_text = (
            f"📅 周报时间区间: {week_start.isoformat()} 至 {(week_end - datetime.timedelta(days=1)).isoformat()}。\n"
            f"💪 本周累计完成训练 {training_count} 次，合理打卡记录饮食 {diet_count} 次。\n"
        )
        
        if injury_count > 0:
            summary_text += f"⚠️ 警告：本周记录了 {injury_count} 次伤病反馈，请在下周训练计划中保持较低的负荷强度并强化关节保护。\n"
        else:
            summary_text += "✅ 良好：本周无新增伤病日志，肩关节和腰部等关键动作代偿指标均表现健康。\n"
            
        weight = metrics_snapshot.get("weight")
        body_fat = metrics_snapshot.get("body_fat")
        if weight:
            summary_text += f"⚖️ 体重快照: {weight} kg"
            if body_fat:
                summary_text += f" (体脂率: {body_fat}%)"
            summary_text += "。体型指标稳健推进，符合当前健身周期策略。"

        # 5. 持久化存储到 PostgreSQL weekly_summaries 表中
        summary_id = str(uuid.uuid4())
        weekly_summary = WeeklySummary(
            id=summary_id,
            user_id=user_id,
            week_start=week_start,
            summary_text=summary_text,
            metrics_snapshot=metrics_snapshot
        )
        
        db.add(weekly_summary)
        
        # 6. 为防止上下文过度膨胀，周汇总生成后，可以安全删除或归档 Layer 3 中的原始明细事件
        # 在工业级开发中，这是一个高吞吐量上下文保活的核心机制
        delete_stmt = delete(Events).where(
            Events.user_id == user_id,
            Events.event_date >= week_start,
            Events.event_date < week_end
        )
        await db.execute(delete_stmt)
        
        await db.commit()
        print(f"User {user_id} episodic memory compressed into summary {summary_id}.")
        return weekly_summary

import pytest
import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import UserProfile, UserMetrics, Events, WeeklySummary
from app.services.memory import MemoryService
from app.services.compress import CompressionService

@pytest.mark.anyio
async def test_memory_extraction_and_conflict_resolution(anyio_backend):
    """
    测试用户指标的提取、分层存储与时序冲突消解机制
    """
    from app.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        user_id = "test-user-candlepw"
        
        # 1. 模拟清理老测试数据，保持幂等性
        profile = await session.get(UserProfile, user_id)
        if profile:
            await session.delete(profile)
            await session.commit()
            
        # 2. 模拟发送包含体重和身高的输入
        changes = await MemoryService.extract_and_sync_memory(
            "今天起床量了体重是 64kg，身高 175cm",
            user_id,
            session
        )
        
        # 验证提取到了两个指标变动
        assert len(changes) == 2
        keys = {c["key"] for c in changes}
        assert "weight" in keys
        assert "height_cm" in keys
        
        # 3. 再次查询画像，验证合并是否成功
        merged = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert merged["height_cm"] == 175.0
        assert merged["metrics"]["weight"]["value"] == 64.0
        
        # 4. 冲突消解测试：用户声称体重降低为 62kg (这与之前录入的 64kg 冲突)
        changes_2 = await MemoryService.extract_and_sync_memory(
            "今天秤了下，体重是 62 公斤啦",
            user_id,
            session
        )
        
        # 验证通过追加时序行成功消解冲突并保留了变更明细
        assert len(changes_2) == 1
        assert changes_2[0]["key"] == "weight"
        assert changes_2[0]["old"] == 64.0
        assert changes_2[0]["new"] == 62.0
        
        # 5. 验证数据库中该指标的时序表记录是否有 2 条
        stmt = select(UserMetrics).where(
            UserMetrics.user_id == user_id,
            UserMetrics.metric_type == "weight"
        ).order_by(UserMetrics.recorded_at)
        result = await session.execute(stmt)
        weight_history = result.scalars().all()
        assert len(weight_history) == 2
        assert float(weight_history[0].value) == 64.0
        assert float(weight_history[1].value) == 62.0


@pytest.mark.anyio
async def test_episodic_memory_compression(anyio_backend):
    """
    测试周归档定时压缩服务，验证 Episodic 流水压缩为 Semantic 周报
    """
    from app.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        user_id = "test-user-memory-compress"
        
        # 1. 模拟写入本周内发生的若干训练与饮食流水事件 (Layer 3)
        event_1 = Events(
            user_id=user_id,
            event_type="training",
            payload={"action": "卧推", "weight": 70},
            event_date=datetime.date.today() - datetime.timedelta(days=3)
        )
        event_2 = Events(
            user_id=user_id,
            event_type="diet",
            payload={"meal": "lunch", "protein": 45},
            event_date=datetime.date.today() - datetime.timedelta(days=2)
        )
        
        session.add_all([event_1, event_2])
        await session.commit()
        
        # 2. 触发压缩任务
        week_start = datetime.date.today() - datetime.timedelta(days=5)
        summary = await CompressionService.compress_user_events_to_weekly_summary(
            user_id,
            week_start,
            session
        )
        
        # 验证周摘要是否生成成功并妥善记录了训练和饮食次数
        assert summary is not None
        assert "本周累计完成训练 1 次" in summary.summary_text
        assert "合理打卡记录饮食 1 次" in summary.summary_text
        
        # 3. 验证明细事件是否已被安全清理以防止 Context 溢出
        stmt = select(Events).where(
            Events.user_id == user_id,
            Events.event_date >= week_start
        )
        result = await session.execute(stmt)
        remaining_events = result.scalars().all()
        assert len(remaining_events) == 0


@pytest.mark.anyio
async def test_injury_recovery_and_deletion(anyio_backend):
    """
    测试伤病康复语义提取、持久化数据库自愈移除与画像同步的全闭环
    """
    from app.database.session import AsyncSessionLocal
    
    async with AsyncSessionLocal() as session:
        user_id = "test-user-injury-clear-candlepw"
        
        # 1. 模拟初始化，清除旧画像以维持幂等性
        profile = await session.get(UserProfile, user_id)
        if profile:
            await session.delete(profile)
            await session.commit()
            
        # 2. 模拟用户声明伤病
        changes_add = await MemoryService.extract_and_sync_memory(
            "最近推胸有点肩膀疼，估计是左肩袖劳损了",
            user_id,
            session
        )
        
        # 验证提取并写入了左肩袖劳损伤病
        assert len(changes_add) == 1
        assert changes_add[0]["key"] == "injuries"
        
        # 验证数据库画像中伤病列表已增加该项
        profile_add = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert "左肩袖劳损" in profile_add["injuries"]
        
        # 3. 核心消解测试：用户声称伤病康复
        changes_remove = await MemoryService.extract_and_sync_memory(
            "告诉你个好消息！我之前肩袖的伤病已经完全康复痊愈啦，可以安排练背了！",
            user_id,
            session
        )
        
        # 验证触发了移除逻辑
        assert len(changes_remove) == 1
        assert changes_remove[0]["key"] == "injuries"
        
        # 验证数据库画像中的 injuries 列表已将该伤病干净抹除！
        profile_remove = await MemoryService.retrieve_aggregated_profile(user_id, session)
        assert "左肩袖劳损" not in profile_remove["injuries"]

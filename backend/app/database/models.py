import datetime
from typing import List, Optional
from sqlalchemy import String, Date, DateTime, Numeric, Integer, ForeignKey, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class UserProfile(Base):
    """
    核心画像表 (Layer 1 - 缓慢变化数据)
    """
    __tablename__ = "user_profile"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    height_cm: Mapped[Optional[float]] = mapped_column(Numeric(5, 2))
    gender: Mapped[Optional[str]] = mapped_column(String(10))
    birth_date: Mapped[Optional[datetime.date]] = mapped_column(Date)
    # goal: bulk, cut, maintain, strength, endurance
    goal: Mapped[Optional[str]] = mapped_column(String(20))
    training_years: Mapped[Optional[int]] = mapped_column(Integer)
    # 伤病和医疗史使用 JSON list 存储，保证对不同数据库的兼容性
    injuries: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    medical_conditions: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    # 关联关系
    metrics: Mapped[List["UserMetrics"]] = relationship("UserMetrics", back_populates="user", cascade="all, delete-orphan")
    events: Mapped[List["Events"]] = relationship("Events", back_populates="user", cascade="all, delete-orphan")
    training_plans: Mapped[List["TrainingPlan"]] = relationship("TrainingPlan", back_populates="user", cascade="all, delete-orphan")
    diet_records: Mapped[List["DietRecord"]] = relationship("DietRecord", back_populates="user", cascade="all, delete-orphan")
    weekly_summaries: Mapped[List["WeeklySummary"]] = relationship("WeeklySummary", back_populates="user", cascade="all, delete-orphan")


class UserMetrics(Base):
    """
    动态指标时序表 (Layer 2 - 频繁变化数据，用于折线图)
    """
    __tablename__ = "user_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user_profile.user_id"), nullable=False)
    # metric_type: weight, body_fat, muscle_mass, bench_press, squat, deadlift 等
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)  # "kg", "%", "reps" 等
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow
    )
    source: Mapped[str] = mapped_column(String(50), default="user_input")  # "user_input", "agent_extracted", "wearable"

    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="metrics")


class Events(Base):
    """
    事件日志表 (Layer 3 - 7天事件流水)
    """
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user_profile.user_id"), nullable=False)
    # event_type: training, diet, sleep, supplement, injury, note
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # payload: 存储该事件的 JSON 结构化数据
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    event_date: Mapped[datetime.date] = mapped_column(Date, default=datetime.date.today)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow
    )

    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="events")


class TrainingPlan(Base):
    """
    训练计划表
    """
    __tablename__ = "training_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user_profile.user_id"), nullable=False)
    plan_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)  # 动作/组数/重量等的完整结构
    target_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active, completed, archived
    completion_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)  # 打勾完成的数据
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow
    )

    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="training_plans")


class DietRecord(Base):
    """
    饮食记录表
    """
    __tablename__ = "diet_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user_profile.user_id"), nullable=False)
    meal_type: Mapped[str] = mapped_column(String(20), nullable=False)  # breakfast, lunch, dinner, snack
    food_items: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # 食物卡片详情列表
    total_calories: Mapped[int] = mapped_column(Integer, nullable=False)
    total_protein: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)
    total_carbs: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)
    total_fat: Mapped[float] = mapped_column(Numeric(6, 2), default=0.0)
    image_url: Mapped[Optional[str]] = mapped_column(String(500))
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow
    )

    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="diet_records")


class ConversationMessage(Base):
    """对话历史表"""
    __tablename__ = "conversation_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user_profile.user_id"), nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False, default="default")
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=datetime.datetime.utcnow)

    user: Mapped["UserProfile"] = relationship("UserProfile")


class WeeklySummary(Base):
    """
    周报摘要表 (Layer 3 -> 4 记忆压缩缓存)
    """
    __tablename__ = "weekly_summaries"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # UUID string
    user_id: Mapped[str] = mapped_column(String, ForeignKey("user_profile.user_id"), nullable=False)
    week_start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    summary_text: Mapped[str] = mapped_column(String, nullable=False)
    metrics_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.datetime.utcnow
    )

    user: Mapped["UserProfile"] = relationship("UserProfile", back_populates="weekly_summaries")

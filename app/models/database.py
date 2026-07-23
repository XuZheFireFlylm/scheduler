"""数据库连接与模型基类"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Float, Integer, JSON, ForeignKey, Enum, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.ext.asyncio import AsyncAttrs, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_size=10)
AsyncSession = async_sessionmaker(engine, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


# ─── 枚举 ───────────────────────────────────────────────────────────────────
import enum


class TaskStatus(str, enum.Enum):
    PENDING = "pending"          # 等待领取
    ASSIGNED = "assigned"        # 已分配给节点
    DOWNLOADING = "downloading"  # 节点正在下载数据
    TRAINING = "training"        # 训练中
    UPLOADING = "uploading"      # 上传权重
    COMPLETED = "completed"      # 完成
    FAILED = "failed"            # 失败
    CANCELLED = "cancelled"      # 取消


class NodeStatus(str, enum.Enum):
    ONLINE = "online"
    BUSY = "busy"      # 正在训练
    OFFLINE = "offline"


# ─── 模型 ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    nodes: Mapped[list["Node"]] = relationship("Node", back_populates="owner")
    submissions: Mapped[list["TaskSubmission"]] = relationship("TaskSubmission", back_populates="node")


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    node_key: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=NodeStatus.OFFLINE.value)

    # 硬件信息
    gpu_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gpu_vram_gb: Mapped[float | None] = mapped_column(Float, nullable=True)
    gpu_count: Mapped[int] = mapped_column(Integer, default=1)
    cpu_cores: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ram_gb: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 能力标记
    capabilities: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    max_batch_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supports_bf16: Mapped[bool] = mapped_column(Boolean, default=False)

    # 统计
    total_tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_compute_score: Mapped[float] = mapped_column(Float, default=0.0)  # 累计贡献分

    # 心跳
    last_heartbeat: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="nodes")
    submissions: Mapped[list["TaskSubmission"]] = relationship("TaskSubmission", back_populates="node")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "qlora_finetune"
    version: Mapped[str] = mapped_column(String(20), nullable=False)       # e.g. "v0.5"

    # 任务配置（JSON）
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # 训练数据集在S3的路径
    train_data_s3_prefix: Mapped[str] = mapped_column(String(500), nullable=False)
    # 基础模型标识（Hub ID 或 S3 路径）
    base_model: Mapped[str] = mapped_column(String(255), nullable=False)

    # 状态
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value)
    assigned_count: Mapped[int] = mapped_column(Integer, default=0)  # 已分配次数
    completed_count: Mapped[int] = mapped_column(Integer, default=0)  # 成功完成次数

    # 优先级
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1~10，1最高

    # 创建/过期时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    submissions: Mapped[list["TaskSubmission"]] = relationship("TaskSubmission", back_populates="task")


class TaskSubmission(Base):
    """节点完成任务后的提交记录"""
    __tablename__ = "task_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id"), nullable=False)
    node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("nodes.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.ASSIGNED.value)

    # 训练指标
    final_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    steps_completed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    epoch_completed: Mapped[float | None] = mapped_column(Float, nullable=True)

    # 计算量（用于结算贡献分）
    compute_score: Mapped[float] = mapped_column(Float, default=0.0)

    # 权重文件在S3的路径
    lora_weights_s3_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # 日志摘要（最后20行）
    log_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 错误信息
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    task: Mapped["Task"] = relationship("Task", back_populates="submissions")
    node: Mapped["Node"] = relationship("Node", back_populates="submissions")


async def init_db():
    """初始化所有表"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db():
    """FastAPI 依赖注入"""
    async with AsyncSession() as session:
        yield session

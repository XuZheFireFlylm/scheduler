"""Node Pydantic schemas."""
import uuid
from datetime import datetime
from pydantic import BaseModel, Field


# ── Hardware info (submitted by client) ───────────────────────────────────────
class CPUInfo(BaseModel):
    model: str
    cores: int | None = None
    threads: int | None = None


class GPUInfo(BaseModel):
    model: str
    vram_gb: float | None = None
    cuda_version: str | None = None


class HardwareInfo(BaseModel):
    cpu: CPUInfo
    gpu: GPUInfo | None = None
    memory_gb: int | None = None
    disk_gb: int | None = None
    os: str | None = None
    client_version: str | None = None


# ── Register ──────────────────────────────────────────────────────────────────
class NodeRegister(BaseModel):
    node_name: str = Field(..., min_length=1, max_length=64)
    hardware_info: HardwareInfo
    max_task_level: int = Field(default=1, ge=1, le=3)


# ── Heartbeat ─────────────────────────────────────────────────────────────────
class NodeHeartbeat(BaseModel):
    node_id: uuid.UUID


# ── Response ──────────────────────────────────────────────────────────────────
class NodeRead(BaseModel):
    id: uuid.UUID
    node_name: str
    status: str
    reputation_score: int
    max_task_level: int
    last_heartbeat: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class HeartbeatResponse(BaseModel):
    status: str                      # online / busy / offline
    running_task_id: uuid.UUID | None = None
    time_until_expiry: int | None = None  # seconds until task TTL expires


class NodesList(BaseModel):
    nodes: list[NodeRead]

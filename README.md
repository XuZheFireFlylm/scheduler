# Firefly Scheduler · 萤火虫调度中心

> 萤火虫大模型 v0.1 阶段：调度闭环完整 API 服务
>
> 技术栈：FastAPI + PostgreSQL + Redis + MinIO（S3兼容）

## 快速启动

```bash
cd docker
docker compose up -d
```

服务启动后访问：
- API 文档：http://localhost:8000/docs
- MinIO Console：http://localhost:9001

## 核心 API

| 接口 | 方法 | 说明 |
|------|------|------|
| `/auth/register` | POST | 用户注册 |
| `/auth/token` | POST | 登录获取 JWT |
| `/nodes/register` | POST | 注册节点 |
| `/nodes/{id}/heartbeat` | POST | 节点心跳 |
| `/tasks/` | GET | 列出任务 |
| `/tasks/claim` | POST | 节点领取任务 |
| `/submissions/report` | POST | 上报训练结果 |
| `/submissions/leaderboard` | GET | 贡献排行榜 |

## 开发

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

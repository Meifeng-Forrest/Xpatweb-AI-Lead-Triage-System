# 后端基础设施（FastAPI + Docker + PostgreSQL + Celery）

## 功能概述

线索分级系统的后端底座：容器化部署、数据持久化、异步可靠队列、统一脱敏调用日志，以及线索全生命周期的 CRUD 与流水线触发 API。是所有上层业务（提取/评分/起草/审核）的运行容器。

## 已实现（自 TODO 归档）

- **归档日期**：2026-06-05
- **原 TODO 位置**：§1.2 FastAPI+Docker 骨架（✅）、§1.3 PostgreSQL 持久化（已完成部分）、§1.4 调用日志规范（后端部分）
- **验证**：2026-06-04 ~ 06-05 多轮验证记录；后端容器单测累计 30/30 ✅；`docker compose up` app/worker/postgres/redis 正常运行 ✅；`/healthz` 200 ✅；真实写库与按 `lead_id` 读回 ✅

### 实现摘要

- **容器编排**：`docker-compose.yml` 编排 app(FastAPI)、worker(Celery)、postgres、redis；`.env` 注入密钥（仓库不留 `.env.example`）；app/worker 以非 root 用户运行。
- **数据持久化**：启动时创建连接池并建表 `leads`（覆盖 PRD 提取字段、评分字段、草稿字段、各阶段 provider/model/temperature 元数据、`extracted_fields`/`draft_fields` JSONB 快照）与 `audit_events`。
- **审计事件**：每个关键写操作在同一事务追加审计（`lead.received.manual` / `lead.extracted_fields.persisted` / `lead.qualification.persisted` / `lead.score.persisted` / `lead.drafts.persisted` / `lead.status_changed`）；`actor` 字段记录操作者（当前为 `system`/`frontend`/`pipeline`，待登录后升级为真实用户，见 TODO §2.9）。
- **Celery 可靠队列**：手动入站与单条重跑统一投递 `app.tasks.run_lead_pipeline`；单并发、晚确认、worker 丢失重投；仅网络/超时、HTTP 429/5xx、数据库错误最多重试 3 次，永久 4xx 直接失败；审计记录 queued/started/succeeded/failed 与 retry_count；任务重试复用已持久化评分避免重复计费。
- **插座接口**：`services/ports.py` 预留 `Notifier`（ConsoleNotifier 假实现）与 `CrmSink`（NoopCrmSink），客户确认 Slack/Push/CRM 后只换实现。
- **脱敏调用日志**：所有 LLM/队列调用记录入口、参数摘要、成功/失败、错误原因；只输出邮箱域名/来源箱/字段是否存在/耗时，禁止输出 Key/Token/邮件原文/PII。

### 已实现验收

- `docker compose up -d` 后 app/worker/postgres/redis 全部运行，`GET /healthz` 返回 200（已通过）
- 线索写库后可按 `lead_id` 读回独立字段 + JSON 快照（已通过）
- 列表/状态/审计接口返回真实 PostgreSQL 数据（已通过）
- 手动入站自动投递 Celery 流水线并可查询 `task_id` 状态；永久错误不重试（已通过）
- 审计事件按事务写入，metadata 不含敏感原文（已通过）

### 已实现 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/healthz` | 健康检查（含 db/redis/llm/graph 配置态） |
| POST | `/api/v1/leads/manual` | 手动线索接收落库 |
| POST | `/api/v1/leads/manual-confirmed` | 两步确认式落库（见 manual-entry.md） |
| GET | `/api/v1/leads?limit=` | 线索列表（倒序） |
| GET | `/api/v1/leads/{id}` | 单条线索 |
| GET | `/api/v1/leads/{id}/audit-events` | 审计时间线 |
| PATCH | `/api/v1/leads/{id}/status` | 状态更新 + 审计 |
| PUT | `/api/v1/leads/{id}/extracted-fields` | 提取字段写回 |
| POST/PUT | `/api/v1/leads/{id}/score` | 评分（调 LLM / 离线写入） |
| POST/PUT | `/api/v1/leads/{id}/drafts` | 起草（调 LLM / 离线写入） |
| POST | `/api/v1/leads/{id}/pipeline` | 单条重跑流水线 |
| GET | `/api/v1/leads/pipeline-tasks/{task_id}` | 任务状态查询 |

### 相关代码文件

- `docker-compose.yml`、`backend/Dockerfile`、`backend/requirements.txt`
- `backend/app/main.py`（启动建表 + 路由注册）、`backend/app/config.py`、`backend/app/logging.py`
- `backend/app/database.py`（连接池）、`backend/app/celery_app.py`、`backend/app/tasks.py`
- `backend/app/repositories/leads.py`（LeadRepository + 建表 SQL + 审计写入）
- `backend/app/api/leads.py`、`backend/app/api/health.py`
- `backend/app/services/ports.py`（Notifier / CrmSink 插座）
- 测试：`backend/tests/test_celery_tasks.py`、`test_pipeline_enqueue.py`、`test_lead_pipeline.py`

## 关联未完成（仍在 TODO）

- 状态枚举收敛到 PRD 完整生命周期；Graph 邮件轮询 / 表单 webhook 接入同一流水线（TODO §2.1）
- 登录/用户身份后将审计 `actor` 升级为真实复核人（TODO §2.9）
- CRM 同步真实实现（TODO §2.8 / Phase 2）

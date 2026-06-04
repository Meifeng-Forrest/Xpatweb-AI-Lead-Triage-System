# AI Lead Triage System

Xpatweb AI 线索分级处理系统。本仓库当前包含：

- React + Vite 前端原型：审核队列、线索详情、手动录入、分析页
- FastAPI 后端骨架：健康检查、手动线索接收入口
- Docker Compose 编排：`app` / `postgres` / `redis`

## 本地运行前端

```bash
npm install
npm run dev
```

前端默认运行在 `http://localhost:3000`。

前端调用后端的默认地址是 `http://localhost:8000`。如需改地址，可在 `.env` 中设置：

```bash
VITE_API_BASE_URL=http://localhost:8000
```

## 本地运行后端与基础服务

根目录 `.env` 需要存在，并包含 `DATABASE_URL`、`REDIS_URL`、Kimi/Gemini LLM 相关变量、Microsoft Graph 相关变量。密钥文件已被 `.gitignore` 忽略，不能提交入库。

```bash
docker compose up --build
```

后端默认运行在 `http://localhost:8000`。

可检查：

```bash
curl http://localhost:8000/healthz
```

手动创建一条测试线索：

```bash
curl -X POST http://localhost:8000/api/v1/leads/manual \
  -H "Content-Type: application/json" \
  -d '{
    "sender_name": "Test Lead",
    "email_address": "test@example.com",
    "source_box": "XP",
    "visa_category": "Retired Person Visa",
    "raw_message": "I would like help with a retirement visa."
  }'
```

返回的 `lead_id` 可用于读取落库记录：

```bash
curl http://localhost:8000/api/v1/leads/{lead_id}
```

读取最近线索列表：

```bash
curl "http://localhost:8000/api/v1/leads?limit=100"
```

更新线索状态，并写入审计记录：

```bash
curl -X PATCH http://localhost:8000/api/v1/leads/{lead_id}/status \
  -H "Content-Type: application/json" \
  -d '{"status":"in_review","actor":"frontend"}'
```

结构化提取邮件字段（后端调用 Gemini Flash，`temperature=0`）：

```bash
curl -X POST http://localhost:8000/api/v1/extraction/email \
  -H "Content-Type: application/json" \
  -d '{
    "source_box": "XP",
    "email_subject": "Retirement visa inquiry",
    "email_from": "Alex Smith <alex.smith@example.com>",
    "email_body": "Hello, I am from Canada and want help with a Retired Person Visa."
  }'
```

将结构化提取结果写回某条线索：

```bash
curl -X PUT http://localhost:8000/api/v1/leads/{lead_id}/extracted-fields \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gemini",
    "model": "gemini-3.5-flash",
    "temperature": 0,
    "actor": "system",
    "extracted": {
      "sender_name": "Alex Smith",
      "email_address": "alex.smith@example.com",
      "contact_number": null,
      "email_domain": "other_personal",
      "lead_type": "Individual",
      "visa_category": "Retired Person Visa",
      "current_visa": null,
      "pr_route": "other",
      "nationality": "Canada",
      "is_first_world": true,
      "job_title": null,
      "net_worth_indicator": "pension income",
      "has_job_offer": null,
      "qualifying_work_visa_years": null,
      "annual_salary_zar": null,
      "pbs_total_score_below_100": null,
      "relationship_duration": null,
      "marriage_type": null,
      "rejection_date": null,
      "urgency_flag": false,
      "multi_visa_flag": false,
      "email_coherence": "high",
      "additional_info": "The lead asks about retiring in South Africa."
    }
  }'
```

调用后端 Gemini 评分并写回线索：

```bash
curl -X POST http://localhost:8000/api/v1/leads/{lead_id}/score
```

在离线/调试时直接写入评分结果：

```bash
curl -X PUT http://localhost:8000/api/v1/leads/{lead_id}/score \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gemini",
    "model": "gemini-3.5-flash",
    "temperature": 0,
    "actor": "verification",
    "result": {
      "lead_score": "GD",
      "score_confidence": "high",
      "score_rationale": "Retired Person Visa enquiry with coherent message and clear value signals.",
      "escalation_flag": false,
      "soft_dnq_warning": null
    }
  }'
```

调用后端 Gemini 起草并写回线索：

```bash
curl -X POST http://localhost:8000/api/v1/leads/{lead_id}/drafts
```

运行完整自动流水线（提取 → DNQ 硬规则 → 评分 → 起草）：

```bash
curl -X POST http://localhost:8000/api/v1/leads/{lead_id}/pipeline
```

接口会把任务投递到 Redis/Celery，并返回 `task_id`。查询执行状态：

```bash
curl http://localhost:8000/api/v1/leads/pipeline-tasks/{task_id}
```

命中 DNQ 时，评分阶段不会调用 Gemini，而是由 `dnq-hard-rules-v1` 确定性写入 `BD` 与 `dnq_reason`，随后继续生成供人工审核的拒绝草稿。手动录入成功后也会投递同一 Celery 流水线。网络超时、连接错误、HTTP 429/5xx 与数据库错误会指数退避重试最多 3 次；HTTP 4xx 等永久错误直接失败，生命周期写入审计事件。

在离线/调试时直接写入草稿：

```bash
curl -X PUT http://localhost:8000/api/v1/leads/{lead_id}/drafts \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "gemini",
    "model": "gemini-3.5-flash",
    "temperature": 0.2,
    "actor": "verification",
    "result": {
      "email_draft": "Dear Alex, thank you for your enquiry...",
      "whatsapp_draft": "Hi Alex, thank you for your enquiry...",
      "phone_script": "Hi Alex, this is Xpatweb following up...",
      "internal_whatsapp_post": "Box: XP lead. Quality: GD. Action: call and book consultation."
    }
  }'
```

## 当前实现边界

后端目前已具备基础持久化：手动线索会写入 PostgreSQL 的 `leads` 表，并生成 `audit_events` 审计记录；状态更新、结构化提取字段、DNQ/risk flags、评分结果和沟通草稿也会落库并写入审计。手动录入会自动投递“提取 → DNQ → 评分 → 起草”Celery 流水线，也可通过单一 API 手动重跑和查询任务状态。前端启动时会先读取 `GET /api/v1/leads`，若后端不可用才保留 mock 数据提示。Microsoft Graph 邮件轮询、真实通知、模板/费用库和 CRM 同步仍在 `TODO.md` 中继续推进。

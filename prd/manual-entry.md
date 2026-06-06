# Manual Entry 两步引导式闭环

## 功能概述

顾问从侧边栏任意页面打开 Manual Entry：Step 1 只粘贴自然语言询盘文本，后端 LLM 提取结构化字段；Step 2 自动回填核心字段供确认/修改并选择品牌；确认后字段与原文同事务落库，自动进入详情页并轮询后台流水线结果。人工确认的字段优先，后台流水线禁止再次提取覆盖。

## 已实现（自 TODO 归档）

- **归档日期**：2026-06-05
- **原 TODO 位置**：§2.1 手动录入（✅ 2026-06-04）、§2.2 两步法拆分（✅ 2026-06-05）
- **验证**：`npm run lint` ✅；`npm run build` ✅；后端容器单测 17/17 ✅（含确认式落库、skip_extraction）；浏览器确认任意页面打开 Step 1 弹窗 ✅；真实提取 + 确认落库 + 评分 + 草稿 HTTP 200 持久化 ✅

### 实现摘要

- **前端两步弹窗**：Step 1 粘贴自然语言；Step 2 回填姓名/邮箱/电话/签证 + 选品牌，可展开编辑全部评分字段；确认后进入详情并每 2 秒轮询任务与线索结果。
- **后端两段式**：`POST /api/v1/extraction/manual`（LLM 提取）→ `POST /api/v1/leads/manual-confirmed`（确认字段与原文同事务落库 + 写审计 `lead.received.manual`、`lead.extracted_fields.confirmed`）。
- **不覆盖人工修改**：Celery 以 `skip_extraction=true` 从 DNQ 阶段开始，禁止后台再次提取覆盖确认字段；任务重试复用已持久化评分避免重复计费。
- **脱敏日志**：前后端调用日志只记邮箱域名、来源箱、签证类别、输入长度、耗时，不输出邮件原文/Key/Token。

### 已实现验收

- 从任意页面打开 Manual Entry → Step 1 粘贴 → 提取回填 Step 2（已通过）
- 确认字段落库并展示后端返回的 `lead_id`/`created_at`（已通过）
- 确认后自动触发流水线并轮询出评分/草稿（已通过）
- 后台流水线不覆盖人工确认字段（已通过，skip_extraction 单测）

### 相关代码文件

- 前端：`src/App.tsx`（两步弹窗）、`src/services/leadApi.ts`
- 后端：`backend/app/api/extraction.py`（`/manual`）、`backend/app/api/leads.py`（`/manual-confirmed`）
- 后端：`backend/app/repositories/leads.py`（`create_confirmed_manual_lead`）、`backend/app/tasks.py`（`skip_extraction`）

## 关联未完成（仍在 TODO）

- 提取偶发 `ReadTimeout` 的服务端有限重试 / 备用提取路由（TODO §2.2）
- 邮件 Graph 轮询 / 表单 webhook 接入同一入站流水线（TODO §2.1）

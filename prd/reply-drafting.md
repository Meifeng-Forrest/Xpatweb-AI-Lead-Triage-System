# 回复起草：模板库 + 费用硬编码

## 功能概述

按签证类型/评分确定性选取回复模板生成第一版草稿。费用金额**绝不由 LLM 生成**（防捏造），从模板硬编码取值；命中模板时跳过 LLM 起草。DNQ 线索走分原因拒绝模板，强调进入人工拒绝审核路径、不自动外发。

## 已实现（自 TODO 归档）

- **归档日期**：2026-06-05
- **原 TODO 位置**：§2.4 回复起草 —— Top 10 模板库（[x]）、费用硬编码（[x]）、品牌署名、DNQ 拒绝模板 + 替代建议
- **验证**：`tests/test_visa_templates.py` 等，容器内 `test_visa_templates + test_lead_pipeline + test_celery_tasks + test_qualification_rules` 20/20 ✅；`npm run build` ✅；前端 Est. Revenue 改读后端模板费用 ✅

### 实现摘要

- **Top 10 正向模板**（`TMPL_POSITIVE_*`，覆盖 Bucket A/B/C 高频签证）：Retired Person、PR Financially Independent、Critical Skills Work、Remote Work、Intra-Company Transfer、General Work、Visitor 11(6) Spousal、Appeal、Study、Relative's。
- **费用硬编码**：每个模板带 `professional_fee_zar` / `admin_fee_zar`，`fee_source=doc/业务规格.md §3.3`，写入 `DraftResult`/`draft_fields`/审计 metadata；未命中模板时前端显示 `Pending template match`，不再用假值 `R44,760`/`R12,500`。
- **模板优先起草**：命中模板时 triage adapter 跳过 LLM 起草，`draft_provider=template`、`draft_model=<template_id>`、`temperature=0`。
- **品牌署名按 source_box**：Xpatweb / Retire In South Africa / Visa Litigation Services / Sable Migration Visa（SMV 正式品牌名待客户确认）。
- **分级差异化**：GD 生成咨询预约邮件 + WhatsApp + 电话话术；MF/MD/BD 生成完整服务报价骨架；命中模板时还生成内部 Box–Quality–Action 草稿。
- **6 条 DNQ 拒绝模板**（`TMPL_DNQ_01`~`06`）：分原因拒绝 + 替代签证建议，草稿强调进入 Marisa/QA 拒绝审核路径，**不报价、不生成电话话术、不自动外发**；软风险 RISK-01/02 不套拒绝模板。

### 已实现验收

- 10 类签证按类型命中正确模板并填充费用（已通过）
- 费用值来自模板而非 LLM，审计记录 `fee_source`（已通过）
- DNQ 命中走对应拒绝模板 + 替代建议，不报价（已通过）
- 品牌署名随 source_box 变化（已通过）

### 相关代码文件

- `backend/app/services/visa_templates.py`（正向 + DNQ 模板、费用、品牌署名）
- `backend/app/services/triage_contract.py`（`DraftResult` 合同、模板优先逻辑）
- 测试：`backend/tests/test_visa_templates.py`

## 关联未完成（仍在 TODO）

- 研究驱动 V2 草稿，与 V1 并排（TODO §2.4 / §2.7）
- WhatsApp 发帖点赞 + 四眼审核门控（TODO §2.4 / §2.6）
- 剩余签证模板补齐至 20+（TODO §10 Phase 2）

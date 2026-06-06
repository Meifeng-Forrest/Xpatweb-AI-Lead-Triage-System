# PRD 已实现模块文档索引

> 本目录存放**已稳定完成且已验证**的功能模块文档（实现摘要 + 已实现验收 + 相关代码路径）。
> 与 `TODO.md`（未完成的待办队列）互补：完成并验证的功能块从 TODO 卸货到此，TODO 仅留一行索引。
> 业务规则权威以 `doc/业务规格.md` 为准，产品定义见 `doc/prd.md`。

## 模块列表

- [后端基础设施](backend-infrastructure.md) — FastAPI + Docker Compose + PostgreSQL + Celery 可靠队列 + 审计事件 + 线索 CRUD/流水线 API（归档 2026-06-05）
- [线索评分：DNQ 硬规则 + 软风险标记](lead-scoring.md) — 6 条确定性 DNQ 规则 + 2 条 risk_flags + DNQ 命中确定性 BD 评分（归档 2026-06-05）
- [回复起草：模板库 + 费用硬编码](reply-drafting.md) — Top 10 正向签证模板 + 6 条 DNQ 拒绝模板 + 费用防捏造 + 品牌署名（归档 2026-06-05）
- [LLM 业务合同与供应商解耦](llm-contract-layer.md) — 中立 extraction/triage 合同 + 工厂 + 按协议命名 adapter（归档 2026-06-05）
- [Manual Entry 两步引导式闭环](manual-entry.md) — 自然语言粘贴 → 提取 → 确认/修改 → 落库 → 流水线（归档 2026-06-05）
- [用户 / 角色 / 权限与管理员用户管理](user-management.md) — JWT 登录 + 多角色权限 + 四眼审核 actor + 管理员用户管理界面（归档 2026-06-05）

## 卸货规范

见 `.claude/rules/todo-prd-archive.md`。仅归档已 `[x]` 且已验证的块；`prd/` 描述必须与当前代码一致。

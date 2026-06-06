# 线索评分：DNQ 硬规则 + 软风险标记

## 功能概述

在调用 LLM 评分之前，用确定性 Python 规则前置判定：命中 DNQ（Do Not Qualify）硬规则的线索零 token 直接判 `BD` 并进入拒绝审核路径；高风险但不应自动拒绝的情形只打 `risk_flags` 交人工。职责边界：LLM 负责读懂语言并提取事实，Python 只按**已确认事实**执行明确规则，缺失/冲突/证据不足时不得自动 DNQ。

## 已实现（自 TODO 归档）

- **归档日期**：2026-06-05
- **原 TODO 位置**：§2.3 线索评分引擎 —— DNQ 6 条硬规则（✅ 2026-06-04）、软规则 risk_flags（✅ 2026-06-04）、DNQ 命中确定性 BD 评分
- **验证**：`tests/test_qualification_rules.py` + `test_lead_pipeline.py`，容器内单测 20/20 ✅；真实数据库 fixture 返回 `provider=rules`、`BD / DNQ-01`，审计含 `lead.qualification.persisted`、`lead.score.persisted` ✅

### 实现摘要

- **6 条 DNQ 硬规则**（`DNQ-01`~`DNQ-06`，依据 `doc/业务规格.md §4.1`）：
  - DNQ-01 关键技能工作签证需正式 job offer
  - DNQ-02 永居需当前有效南非签证
  - DNQ-03 工作签证路径永居需满 4 个合格年限
  - DNQ-04 亲属/配偶路径需正式登记婚姻
  - DNQ-05 上诉超出 10 个工作日窗口
  - DNQ-06 访客签证 11(1) 不适用于免签国籍
- **2 条软风险标记**（`RISK-01`/`RISK-02`，依据 §4.2）：PBS 薪资、Visitor 11(6) 关系等高风险**只标记不拒绝**，强制人工判定。
- **确定性 BD 评分**：命中 DNQ → `lead_score=BD`、写 `dnq_reason`、`status=dnq`、跳过 LLM 评分，但继续生成拒绝审核草稿（见 reply-drafting.md）；`score_provider=rules`、`score_model=dnq-hard-rules-v1`。
- **防误杀**：字段 `null/unknown`、相互矛盾或证据不足时不得自动 DNQ；规则带 `as_of` 日期参数处理时间窗口类规则。

### 已实现验收

- 命中样本正确判 DNQ 并给出对应 `dnq_reason`（已通过，fixture）
- 非 DNQ 与 unknown 样本不被误杀（已通过，防误杀 fixture）
- 软风险只设 `risk_flags`、不改变 DNQ 结果（已通过）
- DNQ 命中时流水线跳过 LLM 评分、确定性写 BD（已通过）

### 相关代码文件

- `backend/app/services/qualification_rules.py`（`DNQ_REASONS`、`qualify_lead()`、`QualificationResult`）
- `backend/app/services/lead_pipeline.py`（`deterministic_dnq_score()` + DNQ 前置门控）
- 测试：`backend/tests/test_qualification_rules.py`、`backend/tests/test_lead_pipeline.py`

## 关联未完成（仍在 TODO）

- 未命中 DNQ 的真实 LLM 评分回包（TODO §2.3）
- 置信度标记驱动流程门控（低置信度转人工，TODO §2.3）
- 回归测试集验证 ≥85% 一致率（上线 gate，TODO §2.3 / `业务规格.md §13.4`）

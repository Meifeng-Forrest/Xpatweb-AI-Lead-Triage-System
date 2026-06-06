# LLM 业务合同与供应商解耦

## 功能概述

把「提取 / 评分 / 起草」三类业务能力的 schema、prompt 和统一接口，从具体供应商（Gemini/Shengsuanyun/Kimi）的实现中抽离。API 与 pipeline 只调用中立合同接口，换模型/换供应商不需改业务主流程；供应商名仅作为配置值与审计记录存在，不再出现在业务文件名/类名里。

## 已实现（自 TODO 归档）

- **归档日期**：2026-06-05
- **原 TODO 位置**：§1.1 LLM 服务层迁移 —— 业务合同与供应商 adapter 分离 + adapter 按协议命名
- **验证**：容器依赖环境内 `python -m unittest discover /app/tests` 30/30 ✅；`npm run lint` ✅；静态检查确认 `backend/app`/`src` 无旧供应商命名 service/类名/import 残留 ✅；`docker compose build/up app worker` + `/healthz` ✅

### 实现摘要

- **中立合同**：`extraction_contract`（提取字段 schema + manual/email prompt + temperature）、`triage_contract`（评分 `LeadScoreResult` + 起草 `DraftResult` 合同 + 模板优先逻辑）。
- **统一工厂**：`llm_factory` 暴露 `get_extraction_service()` / `get_triage_service()` 等，按配置返回实现，向调用方暴露 `provider/model/temperature` 只读属性。
- **按协议命名 adapter**：`openai_compatible_adapters.py`（OpenAI 兼容 JSON，如 Shengsuanyun/Kimi）、`native_json_adapters.py`（Gemini 原生 JSON）；底层 HTTP 客户端 `openai_compatible.py`。
- **默认主链路不变**：Shengsuanyun 提取 + Kimi 评分/非模板起草 + 确定性模板优先起草；数据库与审计继续记录真实 provider/model/temperature。
- **通用口径**：`/api/v1/extraction/*`、`/score`、`/drafts` 的错误文案与日志改为通用 LLM 口径；前端提示不再展示供应商名；`ManualConfirmedLeadCreate.extraction_provider` 默认 `llm`。
- 旧供应商命名文件（`gemini_extraction.py`/`gemini_triage.py`/`kimi_triage.py`/`shengsuanyun_extraction.py`/`gemini_http.py`、前端 `geminiService.ts`）已删除。

### 已实现验收

- API/pipeline 仅依赖中立合同接口，不直接 import 供应商 schema/prompt（已通过，静态检查）
- 换模型只改配置/工厂返回，不动业务主流程（已通过，30/30 单测）
- 审计仍记录真实 provider/model/temperature（已通过）

### 相关代码文件

- `backend/app/services/extraction_contract.py`、`triage_contract.py`、`llm_factory.py`
- `backend/app/services/openai_compatible_adapters.py`、`native_json_adapters.py`、`openai_compatible.py`
- 测试：`backend/tests/test_llm_contracts.py`、`test_native_json_adapters.py`、`test_openai_compatible_adapters.py`、`test_leads_api_llm.py`

## 关联未完成（仍在 TODO）

- 前端 `researchService.ts` 的 `generateResearchBrief` 迁移到后端异步 Web Search / LLM adapter（TODO §1.1 / §10）
- 更换有效 Key 后真实 LLM 提取→评分→起草全链路复测（TODO §2.2 / §2.3）

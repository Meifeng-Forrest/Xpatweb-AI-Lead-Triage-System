# TODO — AI 线索分级处理系统

> 基准文档：`doc/prd.md`（PRD v1.0）、`doc/业务规格.md`（业务规则以此为准）
> 生成方式：对照 PRD §4 核心功能 + §7 Phase 划分，与当前 `src/` 实际代码做差距分析
> 创建日期：2026-06-01

---

## 0. 当前实现快照（事实基线）

当前仓库是一个 **AI Studio 生成的纯前端原型**，技术栈 React 19 + Vite 6 + Tailwind 4 + motion。

**已经能跑的部分（前端 UI 层）：**

- 单页应用骨架（`src/App.tsx` 899 行，全部 UI 集中在此）
- 侧边栏导航：Dashboard / Review Queue / Analytics + Manual Entry 入口
- 仪表盘：统计卡片（总数/待处理/60秒致电队列/已处理）+ 线索表格
- 线索详情页：信息 Tab、Research Brief Tab、草稿区（V1/V2 切换）、60 秒致电卡片、工作流按钮、审计时间线
- 评分徽章（GD/MF/MD/BD + 置信度）、状态徽章
- 手动录入表单（姓名/邮箱/签证类型/品牌）→ 触发 AI triage
- 审核队列列表页、分析页（图表为随机/硬编码数据）
- `researchService.ts`：保留旧前端同步 `generateResearchBrief`（仍待迁移到后端异步 Web Search / LLM adapter）
- 3 条写死的 mock 数据（`src/mockData.ts`）、内存态管理（`useState`）

**关键事实：当前已有 FastAPI + Celery Worker + PostgreSQL + Redis 的 Docker Compose 后端；Manual Entry 已实现“自然语言粘贴 → LLM 提取 adapter → 用户确认/修改 → DNQ → LLM 评分/模板或 LLM 起草 → 详情轮询”的两步闭环。默认 adapter 仍为 Shengsuanyun 提取、Kimi 评分/非模板起草；前端启动时会优先加载后端真实线索；轻量 JWT 鉴权与管理员用户管理已接通；真实邮箱/表单接入、Sheets 写入、真实通知尚未接通。**

---

## 已完成模块（详见 prd/）

> 已稳定完成且验证通过的功能块已卸货到 `prd/`，TODO 仅保留索引与未完成项。

- 后端基础设施（FastAPI/Docker/PostgreSQL/Celery/审计/CRUD API）→ `prd/backend-infrastructure.md`（2026-06-05）
- 线索评分 DNQ 硬规则 + 软风险标记 → `prd/lead-scoring.md`（2026-06-05）
- 回复模板库 + 费用硬编码 + DNQ 拒绝模板 → `prd/reply-drafting.md`（2026-06-05）
- LLM 业务合同与供应商解耦 → `prd/llm-contract-layer.md`（2026-06-05）
- Manual Entry 两步引导式闭环 → `prd/manual-entry.md`（2026-06-05）
- 用户 / 角色 / 权限与管理员用户管理 → `prd/user-management.md`（2026-06-06，已按 5 角色 + 路由并入 Users 表更新）

---

## 1. 关键架构差距（动手前必须先定方向）⚠️

> 📌 **技术栈已定稿**：详见 `doc/技术方案与部署规划.md`。
> Docker 容器化（app=FastAPI + Celery / postgres / redis）部署至客户服务器；
> LLM 用 Gemini（结构化字段提取、评分、起草均在后端服务层执行；提取 temperature=0）；
> 邮件接入用 Microsoft Graph（Client Credentials Flow，App Registration 已建好）。

- **1.1 LLM 服务层迁移：前端 → 后端分步模型调用** 🔴（进行中）
  - **已归档**：业务合同与供应商解耦（`extraction_contract`/`triage_contract`/`llm_factory` + 按协议命名 adapter）→ `prd/llm-contract-layer.md`（2026-06-05）。默认主链路：Shengsuanyun 提取 + Kimi 评分/非模板起草 + 模板优先。
  - 前端 `researchService.ts` 的 `generateResearchBrief` 迁移到后端异步 Web Search / LLM adapter（见 §10）
  - 更换有效 Key 后真实 LLM 提取→评分→起草全链路复测（依赖 §2.3）
- **1.2 FastAPI 后端 + Docker Compose 骨架** ✅（2026-06-04）
  - **已归档** → `prd/backend-infrastructure.md`（含容器编排、健康检查、插座接口、Celery worker）
- **1.3 PostgreSQL 数据持久化**（自建，不用 Supabase）（进行中）
  - **已归档**：`leads`/`audit_events` 表、Repository、CRUD/状态/审计/流水线 API、Celery 可靠队列 → `prd/backend-infrastructure.md`
  - 状态枚举收敛到 PRD 完整生命周期（Received→Scored→Drafted→In Review→Sent/DNQ）
  - 把 Graph 邮件 / 表单入站接入同一流水线（见 §2.1）
  - OneSheet 字段对照 `业务规格.md §8`（Sheets 同步 = Phase 2 可选导出）
- **1.4 调用日志规范落地**（CLAUDE.md 强制要求）
  - **已归档**：后端 LLM/队列调用脱敏日志（入口/参数摘要/成功失败/错误原因，禁输出 Key/Token/PII）→ `prd/backend-infrastructure.md`
  - 前端 research 路径迁移到后端后补齐脱敏调用日志（依赖 §1.1）
- **1.5 密钥安全基线**：补建 `.gitignore`、`.env`（含 MS Graph + kimi 密钥）；确认 `.env` 已被 git 忽略 ✅（2026-06-02）
  - 删除 `.env.example`（部署到客户服务器，仓库不留模板）✅（2026-06-02）
  - `doc/技术方案与部署规划.md` 隐去 App Registration 真实值（App/Tenant/Secret ID + Client Secret 仅存 `.env`）✅（2026-06-02）
  - `.gitignore` 追加忽略 `.claude/`、`CLAUDE.md`、`API文档/`（内部协作配置与资料不入库）✅（2026-06-02）
  - ⚠️ 安全提醒：Client Secret 已在协作过程中明文出现，建议到 Azure 重新生成新密钥作废旧值后更新 `.env`（待用户决定）

---

## 1.6 推进策略：待确认项下如何继续 MVP（2026-06-02 决策）

> **结论：可以继续，推进约 80%。** 待确认项几乎全部卡在「最后一公里对外接线」，而非核心逻辑。
> **核心技巧：接口隔离 + 假实现** —— 把不确定的外部依赖（邮箱地址、通知 channel、CRM 类型）做成「插座」（统一接口 + 日志假实现），核心逻辑照常全建，客户答复后只换实现、零返工。

**🟢 现在全做（零客户依赖，MVP 心脏）：**

- §1.2 FastAPI+Docker 骨架 → §1.1 Gemini 后端服务层 → §1.3 数据库状态机
- §2.2 两步提取、§2.3 **DNQ 硬规则 + 评分引擎 + 回归测试集**、§2.4 模板库+费用硬编码
- §2.6 审核队列真实化+审计、§2.7 异步调研(Web Search)、§1.4 调用日志

**🟡 做接口 + 假实现，留好「插座」（客户答复后换真实现即可）：**

- 邮件接入：Graph 调用代码照写，先连**自有测试邮箱**验通路；客户给 4 地址 → 填 `.env` 即生效
- 60秒通知：定义 `Notifier` 接口 + 控制台/日志假实现；将来换 Slack/Push 只改一处
- CRM 去向：数据先落自建 PostgreSQL；Sheets/HubSpot 做可插拔适配器（Phase 2 接）
- 表单 webhook：先按通用 JSON POST 建端点，字段映射留适配层

**🛑 暂缓（等客户答复，避免返工）：**

- 阈值/模板/路由的**配置管理界面** —— 取决于客户是否要「自助可编辑」（待确认 A）；先放数据库/配置文件，**先不做 UI**
- 任何客户专属值**禁止**写死进业务代码（邮箱/channel/CRM 类型全走 `.env` 或适配器）
- 真·端到端线上联调（真邮件进→真通知出→真 CRM 写）—— 代码就位，客户给账号/地址/公网入口后**收尾**

**停工线：** 推到「装好插座的可演示系统」——核心逻辑 + 假实现能用测试数据走通端到端，可给客户做 demo（呼应 PRD §7「第 3 周看到能用的东西」，并反向逼客户回答悬而未决项）。

---

## 2. MVP 功能拆解（按 PRD §4 + Phase 0/1）

### 2.1 数据接入层（PRD §4.1）— 几乎全缺

- 多品牌收件箱：每条线索打 `source_box` 标签（XP/RISA/VLS/SMV）
  - 现状：`constants.ts` 有品牌常量、`Lead.inboxBrand` 字段；但**无真实收件箱区分逻辑**
- 邮件接入：**Microsoft Graph + OAuth2 Client Credentials Flow**（方案见 `doc/技术方案与部署规划.md §2`）
  - App Registration 已建（`Mail.Read` Application 级已授权），四个 Outlook 收件箱轮询打 `source_box` 标签
  - ⚠️ 阻塞：四个品牌收件箱**具体邮箱地址未提供**，需向客户索取后填入 `.env` 的 `MAILBOX_`*
- [x] 网页表单 webhook：接收 POST，自动填充 lead_id/日期/来源/邮箱/电话
  - 2026-06-05：新增 `POST /api/v1/leads/webhook/form`，支持通用 JSON 表单字段映射（姓名/邮箱/电话/签证类型/message/UTM/活动代码），落库后写 `lead.received.form_webhook` 审计并投递现有 Celery triage pipeline；可选 `FORM_WEBHOOK_SECRET` + `X-Webhook-Secret` 保护入口。
- 手动录入：[x] **已归档** → `prd/manual-entry.md`（两步引导式闭环：粘贴→提取→确认→落库→轮询；前端启动优先加载后端真实列表）
- 原文保留与详情页对照：[x] 2026-06-05，`leads.raw_message` 已随 Lead API 返回为前端 `rawMessage`；详情页 `Leads Information` 底部新增默认收起的 Original Message 折叠块，支持字符数、展开滚动查看与复制。
- 线索来源标记：自动识别 UTM/活动代码，保留 `lead_source`（XP349/RSA024 等）
  - 2026-06-05：表单 webhook 已从 `lead_source` / `campaign_code` / `utm_campaign` / `utm_source` / 常见 `fields` 别名自动写入 `lead_source`。
  - 待做：Graph 邮件入站、前端手动录入的来源代码仍需各自补自动识别。
- WhatsApp 接入 — **Phase 2，不在本轮**

### 2.2 AI 解析与提取（PRD §4.2）

- **已归档**：完整提取字段集 schema + `/api/v1/extraction/email`/`/manual` + 提取字段写回 + `extraction_contract` 统一合同 → `prd/llm-contract-layer.md`
- **已归档**：两步法拆分（提取→确认→DNQ→评分→模板或 LLM 起草，确认字段不被覆盖）→ `prd/manual-entry.md`
- 更换有效 Key / 网络可达后跑通真实 LLM 提取回包
- 把 Graph 邮件轮询接到该提取服务（依赖 §2.1 邮件接入）
  - 2026-06-05：表单 webhook 已接入同一入站流水线并触发后续提取/评分/起草；Graph 邮件仍待客户提供四个品牌邮箱地址后接入。

### 2.3 线索评分引擎（PRD §4.3）🔴

- **已归档**：DNQ 6 条硬规则 + 软规则 risk_flags + DNQ 命中确定性 BD 评分（含评分/写回 API）→ `prd/lead-scoring.md`
- 评分矩阵：未命中 DNQ → 真实 LLM 评分 → GD/MF/MD/BD（依赖有效 Key 复测）
- [x] 置信度标记驱动流程门控：低置信度**标记待人工确认**
  - 2026-06-05：`score_confidence=low` 写回评分时状态进入 `in_review`；后续写入草稿不会覆盖该人工审核状态；容器内真实 API 冒烟通过。
- [ ] **回归测试集验证 ≥85% 一致率**（`业务规格.md §13.4`，上线前必跑的 gate）
  - [x] 2026-06-05：新增确定性回归 fixture（DNQ-01~06、RISK-01/02、unknown 不自动 DNQ、明显优质样例）与 `test_lead_regression_cases.py`；当前 Python 硬规则一致率 100%。
  - [ ] 真实 LLM 评分矩阵一致率：仍依赖有效 Key / 网络可达后跑通，不在本轮强行打勾。

### 2.4 回复起草（PRD §4.4）

- **已归档**：Top 10 正向模板 + 6 条 DNQ 拒绝模板 + 费用硬编码（防捏造）+ 品牌署名 + 分级差异化草稿 + 内部 Box–Quality–Action 草稿 → `prd/reply-drafting.md`
- 研究驱动 V2 草稿，与 V1 并排（依赖 §2.7）
- MVP 系统内管理员审核门控（WhatsApp 点赞移 Phase 2，见 §10）
- SMV 正式品牌署名待客户确认后更新映射

### 2.5 路由与分配（PRD §4.5）— MVP 管理员审核路由已接，真实通知待接 🔴

- 60 秒致电提醒：真实 Push / Slack DM 触发（PRD §8.9 最核心约束）
  - 进度：2026-06-05，pipeline 起草完成后会把需审核线索路由到 `admin` 并调用 `Notifier` 插座；当前仍是 `ConsoleNotifier`，**未接真实 Push / Slack DM**。
- 升级路由：escalationFlag → 真实通知 Jerry，绕过标准队列
  - MVP 口径：先统一通知 `admin` 做系统内审核；`escalation_handler` 专属通知保留为后续路由细化。
- DNQ/Bad → Marisa 拒绝确认路径
  - 进度：2026-06-05，前端质量确认按钮已接 `/reject-confirm`，`quality_lead`/`admin` 可确认拒绝；MVP 通知先统一到 `admin`，真实通知仍是 ConsoleNotifier。
- 签证核查 → 标记 Willem Pretorius（prompt 里提了，无真实路由）
  - 进度：2026-06-05，后端路由已支持按签证核查文本标记查 `visa_verifier`；仍需把上游评分/提取结果稳定写入明确 marker。
- Melissa 每日工作概览
- 不同时区 GD：先 WhatsApp 语音再致电的标记逻辑
- 📌 **路由接收人不写死人名** → 见 §2.9 用户/角色/权限设计方案（按角色查在职用户 + 接 Notifier 插座）

### 2.6 四眼审核队列（PRD §4.6）— MVP 改为系统内管理员审核 🔴

- 审核动作真实化：批准 / 编辑后批准 / 拒绝（退回修改）
  - ✅ 2026-06-05：`Approve & Send` 接 `/approve`；`Edit Drafts` 接 `/edit-draft`；`Reject / Return Draft` 接 `/reject`；BD/DNQ 质量确认接 `/reject-confirm`。
- 第二人复核门控：外发邮件须经第二人检查（当前无"人"的概念，无登录）
  - ✅ 2026-06-05：后端 `approve` 已强制 `批准人 ≠ 最近一次提交/编辑草稿的人`；同人批准返回 409。
  - ✅ 2026-06-05（口径调整）：MVP 最终外发批准权限收紧为 `admin`；`lead_agent`/`team_lead` 可编辑或退回，但不能最终 Approve & Send。
- **完整审计记录**：谁在何时批准（持久化）
  - 2026-06-04：后端新增 `GET /api/v1/leads/{lead_id}/audit-events`，可读取持久化 `audit_events`
  - 2026-06-04：前端详情页 `ACTIVITY AUDIT` 已替换为真实审计时间线；接口失败时显示降级提示
  - ✅ 2026-06-05：审核动作 actor 改用 `current_user.user_id`，不再信任前端传 actor；验收覆盖 `lead.drafts.edited` / `lead.review.rejected` / `lead.reject.confirmed` / `lead.approved`。
- MVP 人工门控：管理员收到通知并在系统内审核通过
  - ✅ 2026-06-05：`routing.py` 将起草完成后的待审核线索路由到 `admin`；`approve` 需要 `lead.approve`，当前仅 `admin` 具备。
  - Phase 2：WhatsApp 发帖获赞门控后移，待客户确认仍要用 WhatsApp 作为内部审批渠道后再接。
- 📌 **审核动作真实化依赖登录/用户身份** → 见 §2.9 用户/角色/权限设计方案（四眼第二人校验 + 真实 actor 审计）

### 2.7 客户背景调研（PRD §4.7）— 后端异步骨架已接，真实 Web Search 待接

- **异步执行**：评分后后台触发，绝不阻塞 60 秒致电（PRD §8.13）
  - [x] 2026-06-05：新增 `research_briefs` 表、`POST /api/v1/leads/{lead_id}/research`、`GET /api/v1/leads/{lead_id}/research` 与 Celery `run_lead_research`；前端 Research 按钮改为后端排队 + 状态轮询，不再直接调用浏览器端 Gemini。
- 真实调研来源：Phase 1 仅 Web Search（LinkedIn 移 Phase 2）
  - 进度：2026-06-05，已移除前端 `@google/genai` 调研依赖；未配置 `WEB_SEARCH_PROVIDER`/`WEB_SEARCH_API_KEY` 时后端明确返回 `failed/WebSearchNotConfigured`，不会编造背景。
  - [ ] 待接真实 Web Search provider（Tavily / SerpAPI / Google CSE 等任选其一），并把来源 URL 写入 `source_refs` 后再交给 LLM 总结。
- 输出 1 Research Brief：已有 5 段结构 ✅（personalProfile/employer/immigration/news/consultantTips）
- 输出 2 Consultant Briefing Note（最多 3 条）— 字段未独立建模
- 输出 3 研究驱动草稿 V2，与 V1 并排（PRD §8.14）
  - 现状：UI 有 V1/V2 切换钮，但**两个 tab 显示同一份草稿**，V2 是空壳
- 外发邮件不提及做过调研（PRD §8.15）— 需写入 prompt 约束
- 调研进行中 loading 态显示在致电提醒旁（PRD §8.13）
  - 2026-06-05：详情页 Research tab 已显示后端排队/轮询 loading；真正自动评分后触发仍待接入 pipeline。

### 2.8 CRM 记录（PRD §4.8）— 未实现

- 线索入站自动建记录，写入所有提取字段
- 状态机：Received → Scored → Drafted → In Review → Sent / DNQ
  - 现状：`LeadStatus` 枚举存在，但状态流转无持久化、无完整生命周期
- OneSheet 双向同步（`业务规格.md §8`）
- `enquiry_lead_quality`(AI) 与 `current_quality`(人工) 双字段（PRD §8.12）— 未建模

---

### 2.9 用户 / 角色 / 权限 + 管理员用户管理

- [x] **已归档** → 见 `prd/user-management.md`（2026-06-06）
  - 已实现：JWT 登录、`AUTH_ENABLED` 灰度、`users`/`user_roles`、5 角色权限常量、审核动作权限、四眼校验、路由并入 `Users` 表编辑弹窗、真实 actor 审计、管理员 `Users` 页面（新增用户/单角色分配/启停/重置密码/按用户配置路由 category）、`user_audit_events`。
  - 最新角色：`superadmin` / `approver` / `agent` / `quality_lead` / `reviewer`；一人一角色，`admin` 历史角色启动时幂等迁移为 `superadmin`。
  - 验证：容器后端单测 62/62 ✅；目标角色/路由测试 23/23 ✅；`npm run lint` ✅；`npm run build` ✅；`GET /api/v1/users/roles`、`GET /api/v1/users`、`GET /api/v1/routing/rules`、按用户设置签证路由冒烟 ✅。
- [ ] 权限矩阵自助编辑
  - 延后：MVP 继续把 `ROLE_PERMISSIONS` 放后端代码常量，降低误配风险；待客户明确需要业务人员自行调整权限后，再升级为数据库表 + 配置 UI。
  - 已拆分完成：「路由收件人配置」已在 §2.11 完成并归档到 `prd/user-management.md`，不再与「权限矩阵自助编辑」捆绑。

### 2.10 角色精简（6→4）+ 路由收件人单独配置（方案 A）

> 📋 设计规划：`doc/角色精简与路由配置-开发规划.md`（2026-06-05）
> 背景：现有 6 角色权限只有 4 套（lead_agent≡team_lead、escalation_handler≡visa_verifier 权限重复）；角色身兼「权限+路由信箱」两职是 UX 复杂的根因。目标：角色回归纯权限收敛到 4 个，路由收件人解耦到 `routing_rules` 配置表。
> 最新状态：该方案已被 `doc/角色5分与路由并入用户表-开发规划.md` 取代；最终实现见 §2.11 和 `prd/user-management.md`。

- [x] **已归档** → 见 `prd/user-management.md`（2026-06-05）
  - 已实现：后端角色收敛为 `admin`/`agent`/`quality_lead`/`reviewer`；`user_roles` 幂等迁移；`routing_rules(category,user_id)`；路由引擎按 category 查收件人并空配置兜底 active admin；`GET/PUT /api/v1/routing/rules`；前端 `Routing` 配置页；Users 页角色 chip 收敛；`types.ts`/`constants.ts` 旧人名 mock 清理。
  - 验证：容器后端 `python -m unittest discover /app/tests` 55/55 ✅；目标测试 `test_auth_service`/`test_users_api`/`test_routing_service`/`test_routing_rules_api`/`test_database_migrations` 16/16 ✅；`npm run lint` ✅；`npm run build` ✅；重建 app/worker 后 `GET /api/v1/users/roles` 返回 4 角色，`GET /api/v1/routing/rules` 返回 4 category 且 fallback_to_admin=true。

### 2.11 角色按职责重切（4→5）+ 路由并入用户表

> 📋 最新规划：`doc/角色5分与路由并入用户表-开发规划.md`（2026-06-06）
> 背景：4 角色方案把最终审批权限仍压在 `admin` 上，且独立 `Routing` 页面让管理员需要在 Users 与 Routing 间来回切换。最新方案把角色按职责拆成 5 个，并把路由 category 作为用户属性在 Users 编辑弹窗中维护。

- [x] **已归档** → 见 `prd/user-management.md`（2026-06-06）
  - 已实现：角色调整为 `superadmin` / `approver` / `agent` / `quality_lead` / `reviewer`；`superadmin` 拥有全部 7 项权限，`approver` 负责最终批准，`agent` 负责看线索/改草稿/退回，`quality_lead` 负责 DNQ/Bad 拒绝确认，`reviewer` 只读。
  - 已实现：`user_roles` 改为业务上一人一角色；新增/更新用户接口强制 exactly one role；前端用户创建与编辑均用单选 role radio。
  - 已实现：启动迁移把历史 `admin` 幂等改为 `superadmin`；空路由兜底也从 active admin 改为 active superadmin。
  - 已实现：路由配置并入 Users 表；`ManagedUser.routing_categories` 随用户列表返回；新增 `PUT /api/v1/users/{user_id}/routing-categories` 按用户保存 category；Users 表展示路由 tags，编辑弹窗按 category 勾选。
  - 已实现：删除前端独立 `Routing` 入口；`GET /api/v1/routing/rules` 保留只读总览；旧 `PUT /api/v1/routing/rules/{category}` 已废弃并返回 410，提示改用按用户配置 API。
  - 验证：目标后端测试 23/23 ✅；完整后端测试 62/62 ✅；`npm run lint` ✅；`npm run build` ✅；本地 API 冒烟确认 5 角色、用户列表包含 `routing_categories`、空配置兜底 `fallback_to_superadmin=true`、Willem 签证路由可通过 Users 路由接口设置并反映到只读路由总览。
  - 仍未完成：权限矩阵自助编辑继续延后；真实 Slack / Push / Email 通知通道仍未接入，当前仍使用 `ConsoleNotifier` 插座。

### 2.12 线索详情抽屉化 + 就地编辑（详见 `docs/lead-detail-drawer-plan.md`）

- [x] 阶段一：抽屉骨架（F1–F7）
  - 完成：2026-06-06，修复 `LeadDetailDrawer` 半成品导致的类型检查失败；详情不再替换 Dashboard / Review Queue 列表，而是以右侧宽抽屉叠加打开；抽屉包含 Overview / Research Brief / Activity Audit 三个 Tab，Overview 顺序为 60 秒呼叫提示 → 基础信息/AI 评分/原文 → 沟通草稿；底部 Actions 吸底，固定为 3 个按钮：Approve & Send / Return / Archive；Header 与 Esc 可关闭抽屉。
  - 验证：`npm run lint` ✅；`npm run build` ✅；`curl -I http://localhost:3001/` ✅。当前会话未暴露 Browser 控制工具，本轮未做截图级视觉验收。
- [x] 阶段二：就地编辑 + 审计（B1–B4 / F8–F12）
  - [x] B1/B2/F8/F9 基础字段编辑链路：新增 `PATCH /api/v1/leads/{lead_id}/fields`，复用 `lead.draft.edit` 权限；仓储层逐字段 diff，仅真实变化时写 `lead.fields.edited` 审计；前端 `editLeadFields` 已接入，基础信息姓名/邮箱/电话/签证/来源/负责人/品牌已出现就地编辑入口。
  - [x] 负责人字段持久化：新增 `leads.assigned_consultant` schema/迁移字段，并映射到前端 `assignedConsultant`，避免刷新后丢失。
  - [x] F10 草稿区独立就地编辑：Email / Phone / WhatsApp 三块各自有 Edit / Save / Cancel，保存时只提交对应草稿字段，继续复用现有 `/edit-draft`。
  - [x] B3 前端审计文案：补 `lead.fields.edited`、`lead.drafts.edited`、批准、退回、DNQ 确认的人话文案与图标；字段编辑只显示字段名，不显示隐私原文。
  - [x] F12 草稿“已修改”标记：单块草稿保存后显示 Modified 标记，提示审批人当前发送内容已被人工改过。
  - [x] B4 权限矩阵级后端测试：补 HTTP 级 `/fields` 权限测试，覆盖 reviewer / approver / quality_lead 返回 403，agent / superadmin 可通过；补仓储层 no-change 测试，确认未变化字段不写审计。
  - 验证：`npm run lint` ✅；`npm run build` ✅；`python3 -m py_compile backend/app/api/leads.py backend/app/repositories/leads.py backend/app/schemas.py backend/app/database.py backend/tests/test_lead_review_api.py` ✅；挂载当前 `backend/` 到后端镜像执行 `python -m unittest tests.test_lead_review_api` 7/7 ✅。
- [x] 阶段三：联调验收（V1–V4）
  - 完成：2026-06-06，使用 Playwright 在认证模式后端下覆盖 superadmin / agent / approver / quality_lead / reviewer 角色；验证抽屉打开、抽屉打开时切换线索、底部 3 按钮顺序、agent 可编辑且不可批准、reviewer/approver/quality_lead 只读且 pipeline failed / 无草稿时批准禁用。
  - 验证：`npm run lint` ✅；`npm run build` ✅；`test-results/lead-detail-drawer/verify.mjs` ✅，报告 `test-results/lead-detail-drawer/report.json`，截图 `superadmin-drawer-open.png` / `superadmin-drawer-switched.png` / `agent-editable.png` / `reviewer-readonly.png` / `approver-readonly.png` / `quality_lead-readonly.png`。
- 决策已定：不扩权限（沿用 `lead.draft.edit`）/ 可改字段=姓名·邮箱·电话·签证·来源·负责人·品牌 / 禁用规则见 `docs/lead-detail-drawer-plan.md` D-Q3。

---

## 3. 非功能性需求与合规（PRD §5）

- 邮件到达至草稿就绪 < 2 分钟（依赖异步流水线）
- 评分一致率 > 85%（回归集验收，见 §2.3）
- DNQ 命中准确率 95%+（独立 fixture 验证）
- POPIA 合规：PII 除 LLM 外不发往第三方；数据存储位置；DPA
- PII 静态加密 + 不用于训练
- 调用日志 + 脱敏（见 §1.4）

---

## 10. 后续功能 / Phase 2（PRD §7）

- LinkedIn 调研（Proxycurl/Apollo 付费 API，先做 1 周 POC）
- WhatsApp 接入（Wati/Twilio，ML393；来源默认评分降一档，`业务规格.md §13.2`）
- WhatsApp 发帖获赞门控（如客户确认继续用 WhatsApp 群作为内部审批渠道，再替代/补充 MVP 系统内 admin 审核）
- 自动跟进计划（Tracker 写跟进日期 + 触发跟进邮件）
- 每周五线索报告自动发 Rebecca
- 数据分析仪表盘（当前 Analytics 页为假数据，需接真实统计）
- 电话线索通话转录
- 剩余签证模板补齐至 20+
- 完整 CRM 集成（HubSpot/Salesforce 迁移）
- 训练反馈闭环（顾问标记评分对错 → 改进 prompt）
- 15 天质检独立工作流（案例管理，PRD §8.7，明确不混入线索分级）
- 前端 `researchService.ts` 的 `generateResearchBrief` 迁移到后端异步 Web Search / LLM adapter；当前仅完成前端服务文件通用命名，尚未迁移 research 执行位置。

---

## 待客户/团队确认项（PRD 中 ⬜ 标记，阻塞实现）

> 📧 以下多项已整理进给 Brandon 的英文对齐邮件（2026-06-02 草拟，待发送）。

**A. 部署与维护（本轮新增，阻塞交付落地）**

- 目标服务器操作系统（Linux / Windows）+ 是否已装 Docker
- 谁拥有服务器 root/管理员权限来部署运行容器
- 公网入口：域名或静态 IP（Microsoft Graph 接收实时邮件 webhook 必需；开发期用轮询/ngrok 兜底）
- 上线后系统的日常运维归属人 + 客户团队偏好技术栈（影响长期可维护性）
- 评分阈值/模板/路由规则：客户团队是否需**自助可编辑**（要做配置界面）还是写死配置（找我们改）；用户管理 UI 已按 MVP 最小范围完成，权限矩阵自助配置仍延后。
- 团队成员真实邮箱（用于替换当前 seed / 历史占位账号）
- 一个人是否可兼多角色：最新实现已按业务职责收敛为一人一角色；如客户后续确认需要兼岗，需要再调整用户角色模型与前端编辑交互。
- 管理员审核提醒通知 channel（Email / Slack / Push 三选一或组合）；当前 MVP 先用 ConsoleNotifier 记录日志，客户确认后替换真实通知实现

**B. 数据字段与归属（本轮新增）**

- 哪些字段由客户团队**人工维护/覆盖**（如 `current_quality` 人工 vs `enquiry_lead_quality` AI）
- 是否需镜像客户现有 tracker 的字段名/命名规范，保证数据对齐

**C. PRD 已记录的开放问题**

- 四个品牌收件箱具体邮箱地址（XP/RISA/VLS/SMV）— 阻塞 §2.1 邮件接入
- CRM 最终选型（Sheets / HubSpot / Salesforce）— `业务规格.md §11 OQ-2`
- 60 秒致电通知 channel（Push 还是 Slack DM）— OQ §11 P0-4
- 联系表单平台确认
- 调研来源范围（除 LinkedIn 外是否含官网/News/CIPC）
- 各项 NFR 数值目标是否对客户承诺（PRD §5 全部待对齐）

---

## 开发进度

> 2026-06-01 ~ 06-05 的功能实现轮次（后端骨架、PostgreSQL 持久化、Celery 队列、DNQ 规则、模板库、LLM 合同解耦、Manual Entry 两步闭环）已卸货到 `prd/`，详见各模块文档与「TODO 卸货记录」。以下仅保留摘要 + 最近活跃轮次。

### 2026-06-01 ~ 06-05（已归档功能轮次摘要）

- 技术栈定稿（`doc/技术方案与部署规划.md`）：Docker Compose（FastAPI+Celery/PostgreSQL/Redis）→ 客户服务器；邮件 Microsoft Graph（App Registration 已建并授权 `Mail.Read`）。
- 已交付并验证（详见 `prd/`）：后端基础设施、DNQ 评分规则、回复模板库、LLM 合同解耦、Manual Entry 两步闭环。后端容器单测累计 30/30 ✅。
- 职责边界决策：LLM 提取事实 → 数据校验识别缺失/冲突 → Python 执行硬规则 → 不确定项转人工；`null/unknown`/矛盾/证据不足时不得自动 DNQ。
- 仍开放的横切阻塞：① 有效 LLM Key / 网络可达后复测真实提取→评分→起草；② Graph 邮件入站；③ 登录/用户身份（见 §2.9）。
- ⚠️ 安全待办：Client Secret 曾明文出现，建议 Azure 轮换（§1.5）。

### 2026-06-05（设计：用户/角色/权限体系）

- 本轮：与用户讨论确认「把写死人名的路由抽象为 用户+角色+权限 三层」方向；产出完整设计方案并写入 §2.9（未实现，仅设计）。
- 决策：角色管「收到哪类线索」、权限管「能做什么动作」；按 PRD §3 + 业务规格 §5 现有口径定义 6 个角色 + 7 项权限；认证用自建轻量 JWT；四眼原则强制「批准人 ≠ 起草人」；带 `AUTH_ENABLED` 灰度开关守住现有 demo。
- 未改任何业务代码；§2.5 / §2.6 已加指针指向 §2.9；待客户确认项补充团队邮箱、自助管理 UI、多角色三项。
- 下步（待用户拍板）：可从 §2.9 阶段一后端（users/user_roles 表 + JWT 登录 + 审核动作接口 + 四眼校验 + 路由引擎）起步。

### 2026-06-05（开发：§2.9 阶段一后端）

- 本轮：完成 §2.9 阶段一后端基础，包括 `users`/`user_roles` 表、用户仓库、角色权限常量、登录 `/api/v1/auth/login`、当前用户 `/api/v1/auth/me`、`AUTH_ENABLED` 灰度兜底、默认占位账号 seed。
- 审核动作：新增 `POST /api/v1/leads/{id}/approve`、`/reject`、`/reject-confirm`、`/edit-draft`；状态变更与审计 actor 改用 `current_user.user_id`；批准动作已加后端四眼校验。
- 路由：新增 `routing.py`，pipeline 起草完成后按 `escalation_flag` / `dnq_reason` / 签证核查标记 / 常规评分查角色接收人，并调用现有 `Notifier` 插座；人名只存在 seed 用户数据，不写进业务判断。
- 验证：容器内 `python -m unittest discover /app/tests` 36/36 ✅；`GET /healthz` ✅；`GET /api/v1/auth/me`（AUTH_ENABLED=false dev admin）✅；`POST /api/v1/auth/login`（admin@example.com / seed 密码）✅。
- 当时未完成：前端 `LoginView` / `AuthContext` / `authApi` / token 注入 / 401 跳登录尚未接；详情页审核按钮仍未接新增后端接口。
- 后续状态：已在下一条「§2.9 阶段一前端」完成。

### 2026-06-05（开发：§2.9 阶段一前端）

- 本轮：完成前端登录与权限上下文，新增 `authApi`、`AuthContext`、`LoginView`；所有 `leadApi` 请求统一走 `authFetch` 注入 token，401 时清 token 并回登录。
- 审核接线：详情页 `Approve & Send Drafts` 接 `/approve`，`Edit Drafts` 进入草稿编辑态并保存到 `/edit-draft`，`Reject / Return Draft` 接 `/reject`，BD/DNQ 的质量确认按钮接 `/reject-confirm`；按钮按 `can(permission)` 显隐。
- 验证：`npm run lint` ✅；`npm run build` ✅；`GET http://localhost:3000` ✅；`GET /api/v1/auth/me` ✅；`GET /api/v1/leads?limit=1` ✅。
- 限制：该轮仅完成登录与审核接线；后续 2026-06-05 已完成用户管理 UI，路由/权限矩阵配置 UI 仍延后；当前 Browser 控制工具未暴露，未做交互截图验证。
- 下轮建议：可继续 §2.5 真实通知 channel，或进入 §2.7 后端异步调研。

### 2026-06-05（验收：§2.5 / §2.6 / §2.9 工作流）

- 本轮：用容器内真实 API 创建临时 E2E 测试线索，验证审核与四眼链路；宿主 `curl`/Node fetch 当前无法连 8000，改用 `docker exec xpatweb-ai-lead-triage-system-app-1` 在容器内访问 `127.0.0.1:8000`。
- 通过项：`/auth/login` 200；`/edit-draft` 后状态 `in_review`；同一 actor 直接 `/approve` 返回 409；`/reject` 后状态 `drafted`；`/reject-confirm` 后状态 `dnq`；另一条未编辑线索 `/approve` 后状态 `sent`。
- 审计验证：测试线索包含 `lead.drafts.edited`、`lead.review.rejected`、`lead.reject.confirmed`；直接批准线索包含 `lead.approved`。
- TODO 回写：§2.5 / §2.6 的“全是假”描述已更新为当前事实：后端角色路由和审核动作已真实化；真实 Slack/Push 通知仍未做。
- 后续口径调整：2026-06-05，MVP 改为系统内 admin 审核通过，不再做 WhatsApp 获赞门控；WhatsApp 门控移入 §10 Phase 2。
- 下轮建议：接 §2.5 真实通知 channel，或进入 §2.7 后端异步调研。

### 2026-06-05（口径调整：MVP 管理员审核替代 WhatsApp 点赞）

- 本轮：按用户确认，将 MVP 人工门控从“WhatsApp 群发帖获赞”改成“系统内 admin 收到通知并审核通过”；WhatsApp 点赞门控后移到 §10 Phase 2。
- 代码：`lead.approve` 权限收紧为仅 `admin`；`lead_agent`/`team_lead` 保留查看、编辑草稿、退回权限；`routing.py` 将起草后的待审核线索统一路由到 `admin`。
- 验证：容器后端单测 `python -m unittest discover /app/tests` 39/39 ✅；`npm run lint` ✅；容器内登录冒烟确认 `admin` 有 `lead.approve`、`melissa@example.com` 无 `lead.approve` ✅。
- 下轮建议：真实通知 channel 先放入待客户确认；客户确认后再把 `admin` 审核提醒从 ConsoleNotifier 替换为 Slack / Push / Email 通道。

### 2026-06-05（开发：管理员用户管理最小闭环）

- 本轮：按用户确认，实现最小管理员用户管理范围；新增后端 `/api/v1/users` 管理 API、`user_audit_events`、最后一个 active admin 保护，前端新增 `Users` 页面（新增用户、改角色、启停、重置密码）。
- 安全与日志：用户管理 API 和前端调用均记录入口/成功/失败摘要；只记录邮箱域名、角色数量、状态、密码长度，不输出 token、密码或隐私原文。
- 验证：`npm run lint` ✅；`npm run build` ✅；重建 app 容器后后端单测 `python -m unittest discover /app/tests` 46/46 ✅；容器内 `GET /api/v1/users` 冒烟 ✅。
- 文档：已将 §2.9 已完成内容归档到 `prd/user-management.md`，TODO 仅保留“自助配置路由规则 / 权限矩阵”后续项。
- 限制：本轮未做 in-app 浏览器截图验证（当前会话未暴露 Browser 控制工具）；Vite dev server 已在 `http://localhost:3000` 运行。

### 2026-06-05（开发：§2.3 回归测试集 + 低置信度门控）

- 本轮：补上 §2.3 的确定性回归测试集，覆盖 6 条 DNQ 硬规则、2 条软风险、不确定字段不自动 DNQ、明显优质样例；修正样例边界，DNQ-04 只验证硬拒绝，RISK-02 由独立弱证据样例覆盖。
- 代码：`persist_score` 新增低置信度门控，`score_confidence=low` 时把状态置为 `in_review`；`persist_drafts` 保持原有状态保护，草稿写入不会把低置信度线索推进到 `drafted`。
- 验证：容器后端单测 `python -m unittest discover /app/tests` 46/46 ✅；`npm run lint` ✅；容器内真实 API 冒烟确认低置信度评分后状态 `in_review`、写草稿后仍为 `in_review`、审计含 `lead.score.persisted` 与 `lead.drafts.persisted` ✅。
- 未完成：真实 LLM 评分矩阵 ≥85% 一致率仍依赖有效 Key / 网络可达后执行；当前只完成 Python 硬规则与流程门控的回归 gate。

---

### 2026-06-05（设计：角色精简 6→4 + 路由收件人单独配置）

- 本轮：与用户确认方向——角色从 6 个收敛到 4 个（纯权限），路由收件人用方案 A 解耦到独立配置表；产出完整开发规划 `doc/角色精简与路由配置-开发规划.md`（**仅设计，未动代码**）。
- 决策：① 角色合并 lead_agent+team_lead→`agent`、escalation_handler+visa_verifier→`reviewer`；② 新增 `routing_rules(category,user_id)` 表，按 4 类 category（escalation/dnq_reject/visa_verification/standard_review）配收件人；③ 空配置兜底全 admin，保证零回归；④ user_roles 用幂等 SQL 迁移避免多角色用户主键冲突。
- TODO 回写：新增 §2.10 四阶段任务；原 §2.9「自助配置路由规则/权限矩阵」拆分，路由收件人独立为 §2.10，权限矩阵自助编辑仍延后。
- 下步（待用户拍板开工）：从 §2.10 阶段一后端角色收敛起步。

### 2026-06-05（开发：详情页 Original Message）

- 本轮：补齐原文正文链路；后端 `LeadRead` 透出 `raw_message`，前端 `BackendLead`/`Lead` 映射为 `rawMessage`，mock 数据补充原文样例。
- UI：`Leads Information` tab 字段下方新增跨整行 Original Message 折叠块；默认收起，显示字符数；展开后用等宽文本、`max-height` 与内部滚动查看；Copy 只写剪贴板，不在日志输出正文。
- 验证：`npm run lint` ✅；容器内 `python -m unittest tests.test_leads_api_llm tests.test_lead_pipeline tests.test_lead_review_api` 8/8 ✅；容器内 API 冒烟确认 `/api/v1/leads?limit=1` 已包含 `raw_message` 且仅记录长度 ✅。
- 限制：当前会话未暴露 in-app Browser/Playwright 控制工具，未做真实点击截图；本地 Vite `http://localhost:3000` 可访问。

### 2026-06-05（开发：§2.1 表单 webhook 入站）

- 本轮：新增通用表单 webhook 入站端点 `POST /api/v1/leads/webhook/form`；支持常见字段别名映射（`Name/Email/Phone/Visa Type/Message/utm_campaign` 等），自动写 `lead_source`、`email_domain`、`raw_message`，并复用现有 Celery pipeline。
- 安全与日志：新增可选 `FORM_WEBHOOK_SECRET`，配置后请求必须带 `X-Webhook-Secret`；API 日志只记录邮箱域名、字段数量、来源、raw_message 长度，不输出表单原文或 secret。
- 验证：重建 app/worker 后端镜像；容器后端单测 `python -m unittest discover /app/tests` 55/55 ✅；`npm run lint` ✅；`git diff --check` ✅；容器内真实 API 冒烟确认 webhook 创建 `received` 线索、返回 `pipeline_task_id`、写入 `lead_source=XP349`，审计包含 `lead.received.form_webhook` 与 `lead.pipeline.queued` ✅。
- 未完成：Graph 邮件轮询仍待四个品牌收件箱地址；前端手动录入来源代码自动识别未做。

### 2026-06-05（开发：§2.10 角色精简 + 路由配置）

- 本轮：按 `doc/角色精简与路由配置-开发规划.md` 完成 6→4 角色收敛；新增 `routing_rules` 表与幂等旧角色迁移；路由引擎改为先判定 category，再按配置收件人通知，空配置兜底 active admin。
- 后端：新增 `GET/PUT /api/v1/routing/rules`，由 `routing.config` 守护；配置变更写入 `user_audit_events`，metadata 只记录 category、收件人数、fallback 状态，不输出邮箱或隐私原文。
- 前端：新增 `Routing` 管理页；Users 页角色 chip 与新增用户默认角色收敛到 `admin`/`agent`/`quality_lead`/`reviewer`；清理 `types.ts` 与 `constants.ts` 旧人名角色 mock。
- 验证：目标后端测试 16/16 ✅；容器完整后端单测 55/55 ✅；`npm run lint` ✅；`npm run build` ✅；重建 app/worker 后 `GET /api/v1/users/roles` 返回 4 角色，`GET /api/v1/routing/rules` 返回 4 category 且空配置兜底 admin ✅。
- 未完成：权限矩阵自助编辑仍延后；真实 Slack / Push / Email 通知通道仍未接，当前只解决“通知谁”，不解决“用什么渠道通知”。

### 2026-06-05（开发：§2.7 后端异步调研骨架）

- 本轮：把 Research Brief 从前端同步 Gemini 迁到后端异步任务；新增 `research_briefs` 持久化、`POST/GET /api/v1/leads/{lead_id}/research`、Celery `run_lead_research`，前端改为后端排队 + 轮询状态。
- 安全与事实边界：移除前端 `@google/genai` 依赖；未配置真实 Web Search provider 时，后端返回 `failed/WebSearchNotConfigured`，不生成看似真实的客户背景。
- 验证：`npm run lint` ✅；`npm run build` ✅；`package-lock.json` JSON 校验 ✅；重建 app/worker 后端镜像；容器后端单测 `python -m unittest discover /app/tests` 59/59 ✅；`git diff --check` ✅；容器内真实 API 冒烟确认 research 会排队、写 `lead.research.queued/started/failed` 审计，且无 brief 伪造 ✅。
- 未完成：真实 Web Search provider 未接；Research Brief 的来源 URL、Consultant Briefing Note、研究驱动 V2 草稿、pipeline 自动触发 research 仍待做。

### 2026-06-06（检查：项目进度与下一步）

- 本轮：按 `.Codex/rules/*` 和 `TODO.md` 检查项目状态；确认 Docker Compose 后端容器仍在运行（app/worker/postgres/redis），仓库存在大量未提交开发成果，视为当前事实基线。
- 验证：`npm run build` ✅；`npm run lint` ❌，失败于 `src/App.tsx(420,12): Cannot find name 'LeadDetailDrawer'`；`docker exec xpatweb-ai-lead-triage-system-app-1 python -m unittest discover /app/tests` ❌，当前镜像未复制 `backend/tests` 到 `/app/tests`，测试命令不可复现。
- 结论：下一轮第一优先级不是继续外部集成，而是先修复 §2.12 抽屉化半成品导致的类型检查失败，并修正后端测试运行方式（例如本地测试环境或 Docker 镜像/命令包含 tests），恢复可验证基线。
- 下轮建议：修复 `LeadDetailDrawer` 类型检查 → 跑通 `npm run lint`/`npm run build` → 修正并跑通后端单测 → 再继续真实通知 channel、真实 Web Search provider 或 Graph 邮件接入。

### 2026-06-06（开发：§2.12 阶段一抽屉骨架）

- 本轮：按 `docs/lead-detail-drawer-plan.md` 完成阶段一抽屉骨架；`selectedLeadId` 不再整块替换列表，Dashboard / Review Queue 常驻，详情以右侧宽抽屉滑入；抽屉内重排为 Overview / Research Brief / Activity Audit，Activity Audit 从右栏移入 Tab，60 秒呼叫提示放在 Overview 顶部。
- Actions：去掉全局 `Edit Drafts` 工作流按钮，底部吸底动作区保留 Return / Archive / Confirm DNQ / Approve & Send；批准发送按已处理状态、无草稿、无 `lead.approve` 权限给出禁用原因。
- 验证：`npm run lint` ✅；`npm run build` ✅；Vite dev server 在 `http://localhost:3001/` 返回 200 ✅。
- 未完成：阶段二字段就地编辑、字段级后端接口、字段编辑审计、草稿独立 inline edit 未做；阶段三因当前会话未暴露 Browser/Playwright 控制工具，尚未完成截图级交互验收。
- 下轮建议：继续 §2.12 阶段二，先做后端 `PATCH /api/v1/leads/{lead_id}/fields` + 仓储 diff 审计，再接前端基础信息 inline edit。

### 2026-06-06（开发：§2.12 底部按钮顺序 + 基础信息就地编辑）

- 本轮：按用户反馈把抽屉最底部动作栏固定为一行 3 个按钮，顺序为 `Approve & Send` / `Return` / `Archive`；`Approve & Send` 放第一位，并继续保留无草稿、已处理、无权限时的禁用原因。
- 后端：新增 `LeadFieldEditRequest`、`PATCH /api/v1/leads/{lead_id}/fields`、`LeadRepository.edit_fields`；复用 `lead.draft.edit` 权限和 `current_user` actor；字段级 diff 后逐条写 `lead.fields.edited`，metadata 只记录字段名与 changed 标记，不写姓名/邮箱/电话原文。
- 数据：新增 `leads.assigned_consultant` schema/迁移字段，`LeadRead` 与前端 `Lead.assignedConsultant` 已打通。
- 前端：新增 `editLeadFields` API 与基础信息行就地编辑；可编辑字段为姓名、邮箱、电话、签证、来源、负责人、品牌，品牌/签证使用下拉；草稿区右上角新增自己的 `Edit Drafts` 入口，底部动作栏不再承担编辑入口。
- 验证：`npm run lint` ✅；`npm run build` ✅；`git diff --check` ✅；本地 `python3 -m py_compile` ✅；用当前 `backend/` 挂载后端镜像执行 `python -m unittest tests.test_lead_review_api` 4/4 ✅。
- 未完成：草稿编辑还未拆成每块独立编辑；`lead.fields.edited` 审计前端文案/图标还未人话化；字段编辑尚未做真实浏览器点击验收。

### 2026-06-06（开发：§2.12 草稿独立编辑 + 审计文案）

- 本轮：把草稿区从全局 `editingDraft` 改为按块编辑；Email / Phone / WhatsApp 三个草稿块各自有 Edit / Save / Cancel，保存时只提交对应字段。
- UI：每个草稿块保存后显示 `Modified` 标记，提醒审批人当前草稿已经人工改过；底部 3 个工作流按钮保持 `Approve & Send` / `Return` / `Archive`。
- 审计：`Activity Audit` 新增 `lead.fields.edited`、`lead.drafts.edited`、`lead.approved`、`lead.review.rejected`、`lead.reject.confirmed` 的人话文案与图标；字段编辑文案只显示字段名，不显示姓名/邮箱/电话原文。
- 验证：`npm run lint` ✅；`npm run build` ✅；`git diff --check` ✅；`python3 -m py_compile backend/app/api/leads.py backend/app/repositories/leads.py backend/app/schemas.py backend/app/database.py` ✅；挂载当前 `backend/` 到后端镜像执行 `python -m unittest tests.test_lead_review_api` 4/4 ✅。
- 未完成：B4 权限矩阵级 HTTP 测试仍需补足；阶段三浏览器交互验收尚未执行。

### 2026-06-06（开发：§2.12 B4 权限测试补齐）

- 本轮：补齐字段编辑 `/fields` 的 HTTP 权限测试；reviewer / approver / quality_lead 通过 FastAPI 依赖链调用返回 403，agent / superadmin 可通过并进入 repository。
- 仓储测试：补 `LeadRepository.edit_fields` no-change 覆盖，确认字段值不变时返回当前记录且不调用 `execute` 写审计。
- 验证：挂载当前 `backend/` 到后端镜像执行 `python -m unittest tests.test_lead_review_api` 7/7 ✅；`npm run lint` ✅；`npm run build` ✅；`python3 -m py_compile backend/app/api/leads.py backend/app/repositories/leads.py backend/app/schemas.py backend/app/database.py backend/tests/test_lead_review_api.py` ✅；`git diff --check` ✅。
- 结论：§2.12 阶段二代码与目标测试已完成；剩余阶段三为真实浏览器/角色/异常态交互验收。

### 2026-06-06（验证：§2.12 阶段三浏览器验收）

- 本轮：补充抽屉可访问性语义，`LeadDetailDrawer` 容器改为 `motion.aside`，`Lead Detail` 改为可定位 heading；字段编辑保存/取消/编辑按钮补 `aria-label`，便于键盘/读屏和 Playwright 稳定定位。
- 浏览器验收：临时以 `AUTH_ENABLED=true` 启动后端，Playwright 覆盖 superadmin / agent / approver / quality_lead / reviewer；验证抽屉打开、抽屉打开时点击第二条线索可切换、底部按钮为 `Approve & Send` / `Return` / `Archive`、agent 可编辑字段但批准禁用、其他角色无编辑按钮且批准禁用。
- 证据：`test-results/lead-detail-drawer/report.json` 显示 `failures: []`；截图位于 `test-results/lead-detail-drawer/`。
- 验证：`npm run lint` ✅；`npm run build` ✅；Playwright 脚本 `test-results/lead-detail-drawer/verify.mjs` ✅。
- 结论：§2.12 三个阶段均已完成并有静态/后端/浏览器证据；本轮结束前已恢复原 compose app 服务。

## TODO 卸货记录

### 2026-06-05

- 归档（已完成且验证）到 `prd/`：
  - 后端基础设施 → `prd/backend-infrastructure.md`（§1.2 + §1.3 已完成部分 + §1.4 后端日志）
  - 线索评分 DNQ 规则 → `prd/lead-scoring.md`（§2.3 DNQ/risk 部分）
  - 回复模板库 → `prd/reply-drafting.md`（§2.4 模板/费用/DNQ拒绝/品牌）
  - LLM 合同解耦 → `prd/llm-contract-layer.md`（§1.1 + §2.2 提取合同部分）
  - Manual Entry 两步闭环 → `prd/manual-entry.md`（§2.1 手动 + §2.2 两步法）
  - 用户 / 角色 / 权限与管理员用户管理 → `prd/user-management.md`（§2.9 阶段一 + 最小管理员用户管理界面）
- TODO 精简：§1.1–§1.4、§2.1–§2.4 已完成块折叠为「已归档 → prd/xxx.md」一行索引，仅保留未完成项；开发进度日志 06-01~06-05 功能轮次压缩为摘要。
- TODO 行数：496 → 约 235；新增 `prd/README.md` 索引。
- 下轮活跃项：§2.9 用户/角色/权限、§2.3 真实 LLM 评分 + 回归集、§2.5/§2.6 路由与四眼审核真实化。

### 2026-06-05

- 归档：§2.10 角色精简（6→4）+ 路由收件人单独配置 → `prd/user-management.md`
- TODO 精简：§2.10 四阶段 checkbox 折叠为一条已归档索引；§2.9 剩余项收敛为“权限矩阵自助编辑”。
- 下轮活跃项：§2.5 真实通知 channel、§2.7 后端异步调研、§2.3 真实 LLM 评分矩阵复测。

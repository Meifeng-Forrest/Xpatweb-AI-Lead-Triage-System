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
- `geminiService.ts`：`triageLead`（解析+评分+起草合并一次调用）、`generateResearchBrief`
- 3 条写死的 mock 数据（`src/mockData.ts`）、内存态管理（`useState`）

**关键事实：当前已有 FastAPI + Celery Worker + PostgreSQL + Redis 的 Docker Compose 后端；Manual Entry 已实现“自然语言粘贴 → ShengSuanYun 提取 → 用户确认/修改 → DNQ → Kimi 评分/起草 → 详情轮询”的两步闭环。前端启动时会优先加载后端真实线索；真实邮箱/表单接入、Sheets 写入、真实通知与鉴权尚未接通。**

---

## 1. 关键架构差距（动手前必须先定方向）⚠️

> 📌 **技术栈已定稿**：详见 `doc/技术方案与部署规划.md`。
> Docker 容器化（app=FastAPI + Celery / postgres / redis）部署至客户服务器；
> LLM 用 Gemini（结构化字段提取、评分、起草均在后端服务层执行；提取 temperature=0）；
> 邮件接入用 Microsoft Graph（Client Credentials Flow，App Registration 已建好）。

- **1.1 LLM 服务层迁移：前端 Gemini → 后端分步模型调用** 🔴
  - 现状：`src/services/geminiService.ts` 用 `@google/genai` + `GEMINI_API_KEY` + 模型 `gemini-3-flash-preview` / `gemini-3.1-pro-preview`
  - 目标：Gemini Flash/Pro（结构化提取、评分、起草，提取 temperature=0）；所有密钥只在后端读取
  - 待办：在 FastAPI 后端实现 service 层 → structured output / JSON Schema 保证字段 schema 一致 → 后续把前端 triage 调用迁到后端
  - 进度：2026-06-04，本轮已补齐 `.env` 的 Kimi/Gemini 相关变量，并让后端配置读取 `LLM_`*、`KIMI_*`、`GEMINI_*`；前端 Gemini 模型名已改为环境变量。后续决策已改为 Gemini 后端服务层，不再以 Kimi 作为主链路。
  - 进度：2026-06-04（补充），按用户决策将“结构化提取”改为 Gemini Flash + `temperature=0`；新增后端 `/api/v1/extraction/email` 和 Gemini 提取 service。受当前本机网络到 `generativelanguage.googleapis.com` 超时影响，真实 Gemini 回包暂未验通。
  - 进度：2026-06-04（补充），按用户决策评分/起草也继续用 Gemini；新增 `GeminiTriageService`、`POST /api/v1/leads/{lead_id}/score`、`POST /api/v1/leads/{lead_id}/drafts`，并提供 `PUT` 写回接口用于离线验证。真实请求已到达 Google，但当前 Key 无效。
  - ⚠️ 阻塞：2026-06-04 真实请求已确认可到达 Google，但 Google 返回 `API_KEY_INVALID`；需在 `.env` 更换有效 `GEMINI_API_KEY` 后复测完整流水线
  - 2026-06-04：Manual Entry 主链路已改为 ShengSuanYun `google/gemini-3-flash` 提取、Kimi `kimi-k2.6` 评分/起草；Kimi 结构化业务调用关闭思考模式，不再依赖无效 Gemini Key
- **1.2 搭建 FastAPI 后端 + Docker Compose 骨架** 🔴 ✅（2026-06-04）
  - 一份 `docker-compose.yml` 编排 app + postgres + redis，`.env` 注入（`.env` 已建；`.env.example` 已删除，仓库不留模板）
  - 邮箱 OAuth、调研、API Key 安全必须在后端，**不能前端裸跑**
  - 2026-06-04：新增 `backend/` FastAPI 骨架、`docker-compose.yml`、PostgreSQL/Redis 编排、健康检查 `/healthz`
  - 2026-06-04：新增手动线索 API 占位 `/api/v1/leads/manual`，日志只记录邮箱域名、输入长度、来源箱等脱敏摘要
  - 2026-06-04：预留通知/CRM 插座接口（Console/Noop 实现），后续客户确认 Slack/CRM 后替换真实实现
  - 2026-06-04：应用启动时创建数据库连接池并初始化 `leads` / `audit_events` 表
  - 2026-06-04：新增独立 Celery worker 容器，使用 Redis broker/result backend、单并发、晚确认、worker 丢失重投，并以非 root 用户运行
- **1.3 PostgreSQL 数据持久化**（自建，不用 Supabase）（进行中）
  - 现状：后端手动线索 API 已可写入 PostgreSQL；前端启动时已能从后端读取真实线索列表
  - 待办：建 Lead 表与状态机；OneSheet 字段对照 `业务规格.md §8`（Sheets 同步作为 Phase 2 可选导出）
  - 2026-06-04：新增 `leads` 表，覆盖手动入站的核心字段：姓名、邮箱、邮箱域名、电话、签证类别、来源箱、来源代码、原始消息、状态、创建/更新时间
  - 2026-06-04：新增 `audit_events` 表，手动线索落库时写入 `lead.received.manual`
  - 2026-06-04：`POST /api/v1/leads/manual` 已从“接收占位”升级为“落库 + 写审计”；新增 `GET /api/v1/leads/{lead_id}` 读取接口
  - 2026-06-04：真实 Docker 联调通过：`/healthz` 200，手动创建线索后可按 `lead_id` 读回；数据库计数 `leads=2`、`audit_events=2`
  - 2026-06-04：前端手动录入已改为先调用后端 `POST /api/v1/leads/manual`，再把后端返回的 `lead_id`/`created_at` 放入前端列表
  - 2026-06-04：新增 `GET /api/v1/leads?limit=...` 列表接口，前端启动时优先从后端加载真实线索，后端不可用时提示并保留 mock 数据
  - 2026-06-04：新增 `PATCH /api/v1/leads/{lead_id}/status`，状态更新写入 `leads.status/updated_at` 并追加 `lead.status_changed` 审计事件；前端状态按钮已接后端
  - 2026-06-04：扩展 `leads` 表，新增 PRD 提取字段列、`extracted_fields` JSONB 快照、`extracted_at`、提取 provider/model/temperature；新增 `PUT /api/v1/leads/{lead_id}/extracted-fields` 写回接口，并追加 `lead.extracted_fields.persisted` 审计事件
  - 2026-06-04：扩展 `leads` 表，新增 `lead_score`、`score_confidence`、`score_rationale`、`escalation_flag`、草稿字段、评分/起草 provider/model/temperature 与时间戳；评分/草稿写回会生成审计事件
  - 下步：把状态枚举从当前 UI 操作态逐步收敛到 PRD 完整生命周期；把 Graph/表单入站接入同一流水线
  - 2026-06-04：手动入站会自动触发“提取 → DNQ → 评分 → 起草”后台流水线；新增 `POST /api/v1/leads/{lead_id}/pipeline` 支持单条重跑
  - 2026-06-04：后台流水线已迁移到 Celery 可靠队列；手动入站/单条重跑共用 `app.tasks.run_lead_pipeline`，并提供 `GET /api/v1/leads/pipeline-tasks/{task_id}` 查询状态
- **1.4 调用日志规范落地**（CLAUDE.md 强制要求）
  - 所有 LLM/Graph/队列调用需记录：入口、关键参数摘要、成功/失败、错误原因；**禁止输出 Key/Token/PII 原文**
  - 现状：`geminiService.ts` 仅有 `console.error`，无入口/参数/成功日志
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
- 网页表单 webhook：接收 POST，自动填充 lead_id/日期/来源/邮箱/电话
- 手动录入：前端提交已接后端持久化 ✅（2026-06-04）
  - 2026-06-04，`POST /api/v1/leads/manual` 已写入 PostgreSQL；前端 `Manual Entry` 已先调用后端 API，再展示后端返回的 `lead_id`
  - 2026-06-04，前端刷新后已优先加载 `GET /api/v1/leads` 的真实列表；后端不可用时回退显示 `MOCK_LEADS`
  - 2026-06-04：Manual Entry 已改为全局两步弹窗；Step 1 仅粘贴自然语言，Step 2 确认核心字段并可展开修改完整提取字段；确认后自动进入详情并轮询任务结果
- 线索来源标记：自动识别 UTM/活动代码，保留 `lead_source`（XP349/RSA024 等）
  - 现状：`Lead.source` 字段存在，但靠手填，无自动识别
- WhatsApp 接入 — **Phase 2，不在本轮**

### 2.2 AI 解析与提取（PRD §4.2）— 字段不全 + 模型错配

- 按 PRD §4.2 提取完整字段集：`sender_name, email_domain, lead_type, visa_category, job_title, nationality, net_worth_indicator, urgency_flag, multi_visa_flag, email_coherence, raw_message`
  - 现状：`triageLead` 只提取 name/email/phone/visaType 等少数字段，缺 nationality/job_title/net_worth/coherence 等
  - 进度：2026-06-04，后端 schema、数据库列和写回接口已覆盖该字段集；前端旧 `triageLead` 仍未迁移，真实 Gemini 回包因当前 Key 无效暂未验通
- 用 Gemini Flash 做结构化提取，`temperature=0`，structured output / JSON Schema 保证 schema（进行中）
  - 2026-06-04：新增后端 `POST /api/v1/extraction/email`，输入 `source_box/email_subject/email_from/email_body`，返回固定提取字段
  - 2026-06-04：新增 `GeminiExtractionService`，REST 调用 Gemini `generateContent`，配置 `responseMimeType: application/json`、`responseJsonSchema`、`temperature=0.0`
  - 2026-06-04：新增 `PUT /api/v1/leads/{lead_id}/extracted-fields`，可把提取结果写入 PostgreSQL 并生成审计
  - 下步：本机/服务器网络可访问 Gemini 后跑通真实回包；随后把 Graph 邮件轮询和手动/表单入站接到该提取服务
- **两步法拆分（Manual Entry）**：已完成“ShengSuanYun 提取 → 用户确认 → DNQ → Kimi 评分 → Kimi 起草”；确认字段直接进入 DNQ，后台禁止再次提取覆盖人工修改 ✅（2026-06-04）

### 2.3 线索评分引擎（PRD §4.3）— 核心逻辑缺失 🔴

- **DNQ 6 条硬规则**：Python 函数前置判定（零 token），见 `业务规格.md §4.1` ✅（2026-06-04）
  - 新增 `qualification_rules.py`；命中后确定性写入 `BD`、`dnq_reason`、`status=dnq`，跳过 Gemini 评分但继续生成拒绝审核草稿
- **软规则 risk_flags**：PBS 薪资、Visitor 11(6) 关系等高风险标记，不自动拒绝（`业务规格.md §4.2`）✅（2026-06-04）
  - 新增 `risk_flags` JSONB 字段与审计事件；软规则只标记，不进入 DNQ
- 评分矩阵：未命中 DNQ → LLM 评分 → GD/MF/MD/BD（Phase 0 可先 GD vs Not-GD 二分类）
  - 2026-06-04：新增后端 Gemini 评分服务 `POST /api/v1/leads/{lead_id}/score`，输出 `lead_score/score_confidence/score_rationale/escalation_flag/soft_dnq_warning`
  - 2026-06-04：新增 `PUT /api/v1/leads/{lead_id}/score`，可把评分结果持久化到 PostgreSQL 并生成 `lead.score.persisted` 审计
  - 2026-06-04：评分 API 与自动流水线均在 Gemini 前执行 DNQ；真实 fixture 验证返回 `provider=rules`、`BD / DNQ-01`
  - 下步：更换有效 Gemini Key 后复测未命中 DNQ 的真实评分回包
- 置信度标记驱动人工审核：低置信度时**标记待人工确认**，不自动执行
  - 现状：有 `confidence` 字段和徽章，但**不影响任何流程门控**
- 评分解释（白话理由）：已有 `reasons[]` 字段并在 UI 展示 ✅（保留）
- **回归测试集验证 85% 一致率**（`业务规格.md §13.4`，上线前必跑的 gate）— 完全未建

### 2.4 回复起草（PRD §4.4）— 模板库与防捏造缺失

- Top 10 签证回复模板库（Phase 1）：按签证类型自动选模板填充
  - 现状：草稿由 LLM 自由生成，**无模板库**（`业务规格.md §7` 有模板全集种子）
- **费用金额硬编码自模板**（PRD §11 风险表：绝不由 LLM 生成，防捏造）🔴
  - 现状：UI 里 Est. Revenue 是写死的 `R44,760`/`R12,500`，草稿费用靠 LLM
- 品牌署名按 `source_box` 变化（Xpatweb / Retire In SA / Visa Litigation Services）
- 分级差异化草稿：GD（预约邮件+语音话术+电话话术）/ MF·MD（完整报价）/ BD（简短或拒绝模板+替代签证建议）
  - 现状：`triageLead` 统一产出 email/whatsapp/phone 三段，未按评分差异化
  - 进度：2026-06-04，新增后端 Gemini 起草服务 `POST /api/v1/leads/{lead_id}/drafts` 与 `PUT /api/v1/leads/{lead_id}/drafts` 持久化接口；当前 prompt 已按评分/签证类型起草 email/WhatsApp/phone/internal post，但模板库与费用硬编码尚未完成
- 输出 WhatsApp 发帖文案（Box–Quality–Action 格式，PRD §8.10）

### 2.5 路由与分配（PRD §4.5）— 全是前端假按钮 🔴

- 60 秒致电提醒：真实 Push / Slack DM 触发（PRD §8.9 最核心约束）
  - 现状：仅 UI 红色卡片 + `tel:` 链接，**无真实通知推送**
- 升级路由：escalationFlag → 真实通知 Jerry，绕过标准队列
  - 现状：有 `escalationFlag` 字段和图标，无通知动作
- DNQ/Bad → Marisa 拒绝确认路径
  - 现状：UI 有 "SEND TO MARISA" 按钮，**未接任何后端**
- 签证核查 → 标记 Willem Pretorius（prompt 里提了，无真实路由）
- Melissa 每日工作概览
- 不同时区 GD：先 WhatsApp 语音再致电的标记逻辑

### 2.6 四眼审核队列（PRD §4.6）— UI 在，逻辑全假 🔴

- 审核动作真实化：批准 / 编辑后批准 / 拒绝（退回修改）
  - 现状：`Approve & Send`/`Edit Drafts`/`Archive` 只改本地 `status` 或空函数 `onClick={() => {}}`
- 第二人复核门控：外发邮件须经第二人检查（当前无"人"的概念，无登录）
- **完整审计记录**：谁在何时批准（持久化）
  - 2026-06-04：后端新增 `GET /api/v1/leads/{lead_id}/audit-events`，可读取持久化 `audit_events`
  - 2026-06-04：前端详情页 `ACTIVITY AUDIT` 已替换为真实审计时间线；接口失败时显示降级提示
  - 下步：接入登录/操作者身份后，将 `actor` 从 `frontend`/`system` 升级为真实复核人，并覆盖“谁批准”
- WhatsApp 发帖获赞前不可外发的人工门控（PRD §8.10）

### 2.7 客户背景调研（PRD §4.7）— 同步阻塞 + 无真实来源

- **异步执行**：评分后后台触发，绝不阻塞 60 秒致电（PRD §8.13）
  - 现状：`handleResearch` 是用户**手动点按钮同步等待**，不是自动异步
- 真实调研来源：Phase 1 仅 Web Search（LinkedIn 移 Phase 2）
  - 现状：`generateResearchBrief` 让 LLM 凭空"编"背景，**无任何真实检索**
- 输出 1 Research Brief：已有 5 段结构 ✅（personalProfile/employer/immigration/news/consultantTips）
- 输出 2 Consultant Briefing Note（最多 3 条）— 字段未独立建模
- 输出 3 研究驱动草稿 V2，与 V1 并排（PRD §8.14）
  - 现状：UI 有 V1/V2 切换钮，但**两个 tab 显示同一份草稿**，V2 是空壳
- 外发邮件不提及做过调研（PRD §8.15）— 需写入 prompt 约束
- 调研进行中 loading 态显示在致电提醒旁（PRD §8.13）

### 2.8 CRM 记录（PRD §4.8）— 未实现

- 线索入站自动建记录，写入所有提取字段
- 状态机：Received → Scored → Drafted → In Review → Sent / DNQ
  - 现状：`LeadStatus` 枚举存在，但状态流转无持久化、无完整生命周期
- OneSheet 双向同步（`业务规格.md §8`）
- `enquiry_lead_quality`(AI) 与 `current_quality`(人工) 双字段（PRD §8.12）— 未建模

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
- 自动跟进计划（Tracker 写跟进日期 + 触发跟进邮件）
- 每周五线索报告自动发 Rebecca
- 数据分析仪表盘（当前 Analytics 页为假数据，需接真实统计）
- 电话线索通话转录
- 剩余签证模板补齐至 20+
- 完整 CRM 集成（HubSpot/Salesforce 迁移）
- 训练反馈闭环（顾问标记评分对错 → 改进 prompt）
- 15 天质检独立工作流（案例管理，PRD §8.7，明确不混入线索分级）

---

## 待客户/团队确认项（PRD 中 ⬜ 标记，阻塞实现）

> 📧 以下多项已整理进给 Brandon 的英文对齐邮件（2026-06-02 草拟，待发送）。

**A. 部署与维护（本轮新增，阻塞交付落地）**

- 目标服务器操作系统（Linux / Windows）+ 是否已装 Docker
- 谁拥有服务器 root/管理员权限来部署运行容器
- 公网入口：域名或静态 IP（Microsoft Graph 接收实时邮件 webhook 必需；开发期用轮询/ngrok 兜底）
- 上线后系统的日常运维归属人 + 客户团队偏好技术栈（影响长期可维护性）
- 评分阈值/模板/路由规则：客户团队是否需**自助可编辑**（要做配置界面）还是写死配置（找我们改）

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

### 2026-06-01

- 本轮：完成 PRD ↔ 代码库差距分析，建立 TODO.md
- 结论：当前为**纯前端原型**，UI 层基本成型；后端、AI 流水线核心逻辑、数据接入、路由通知、持久化全部待建

### 2026-06-02

- 本轮：技术栈决策定稿，产出 `doc/技术方案与部署规划.md`
  - 部署：Docker Compose（FastAPI+Celery / PostgreSQL / Redis）→ 客户服务器
  - LLM：kimi-k2.5（提取）+ kimi-k2.6（评分/起草），Anthropic 协议
  - 邮件：Microsoft Graph，App Registration 已建并授权 `Mail.Read`
- 安全基线：补建 `.gitignore` + `.env`（含 MS Graph 密钥）+ `.env.example`，已验证 `.env` 被 git 忽略（§1.5 ✅）
- 最高优先级（建议下轮）：§1.2 FastAPI+Docker 骨架 → §1.1 kimi 迁移 → §2.3 DNQ 硬规则与评分引擎
- 待客户：四个品牌收件箱邮箱地址（阻塞 §2.1 邮件接入联调）

### 2026-06-02（补充：安全收口 + 客户对齐）

- 安全收口：删除 `.env.example`；规划文档隐去 App Registration 真实值；`.gitignore` 追加忽略 `.claude/`/`CLAUDE.md`/`API文档/`，已验证四项均被 git 忽略（§1.5）
- 本地 Docker 结论：开发期本地 `docker compose` 可跑通后端；但实时邮件 webhook 需公网入口，生产必须部署到客户服务器（开发期用轮询/ngrok 兜底）
- 客户对齐：草拟给 Brandon 的英文邮件，覆盖「部署环境 / 运维归属 / 字段维护 / 邮箱地址 / CRM 去向」，新增待确认项见上「待客户确认 A/B」段（邮件待发送）
- ⚠️ 安全待办：Client Secret 已明文出现于协作过程，建议 Azure 重新生成轮换（见 §1.5）
- 推进策略定稿（§1.6）：待确认项不阻塞核心开发，采用「接口隔离+假实现」推进约 80%；配置 UI 与真·端到端联调暂缓至客户答复
- 下轮目标：§1.2 FastAPI+Docker 骨架，并从一开始预留邮件/通知/CRM 三个「插座」接口

### 2026-06-04

- 本轮：按用户要求更新 LLM 环境变量接口，`.env` 新增 `LLM_`*、`KIMI_*`、`GEMINI_*` 配置；后端 `Settings` 支持读取 Kimi/Gemini Key 与模型配置；前端 Gemini 服务改为通过环境变量读取 triage/research 模型名。
- 验证：已做配置文件与代码静态检查；未调用外部 LLM，因为 Key 由用户稍后手动填写。
- 下轮建议：继续 §1.1，在 FastAPI 后端新增 Kimi Anthropic 协议 service 层，并把前端手动录入从浏览器 Gemini 调用迁到后端接口。

### 2026-06-04

- 本轮：统一 PRD 引用为 `doc/prd.md`；新增 FastAPI 后端骨架、Docker Compose（app/postgres/redis）、健康检查、手动线索接收 API、通知/CRM 占位接口与脱敏调用日志。
- 验证：`npm run lint` ✅；`python3 -m py_compile backend/app/*.py backend/app/api/*.py backend/app/services/*.py` ✅；`docker compose config --quiet` ✅；旧路径 `doc/产品需求文档.md` 引用扫描无残留 ✅。
- 仍未完成：§1.2 还未真正接数据库/队列执行；§1.1 kimi 迁移、§1.3 Lead 表和状态机仍待做。
- 下轮建议：继续 §1.3，建立 PostgreSQL 表结构/Repository，再把 `/api/v1/leads/manual` 从“接收占位”升级为“落库 + 写审计 + 触发评分队列”。

### 2026-06-04（补充：PostgreSQL 持久化）

- 本轮：完成 §1.3 的第一段落地，新增数据库连接池、启动建表 SQL、`LeadRepository`、`leads` / `audit_events` 表；手动线索 API 已真实落库并写审计。
- 验证：`python3 -m py_compile backend/app/*.py backend/app/api/*.py backend/app/repositories/*.py backend/app/services/*.py` ✅；`docker compose config --quiet` ✅；`npm run lint` ✅。
- 未完成/阻塞：`docker compose up -d postgres redis` 未能运行，因为本机 Docker daemon 未启动（报错：无法连接 `/Users/wangmeifeng/.docker/run/docker.sock`）；待打开 Docker Desktop 后可做真实容器联调。
- 下轮建议：打开 Docker 后跑通真实 API 写库；随后做前端手动录入接后端，或继续实现 Celery 评分队列触发点。

### 2026-06-04（补充：Docker 联调 + 前端接后端）

- 本轮：按用户要求停止占用 `8000` 的旧容器 `enterprise-mock-api`；本项目 app 恢复映射 `8000:8000`；前端默认 API 地址恢复为 `http://localhost:8000`。
- 前端：新增 `src/services/leadApi.ts`，`Manual Entry` 提交现在先写入后端 PostgreSQL，再用后端返回的 `lead_id` 建立前端列表项；调用日志只记录邮箱域名、来源箱、签证类别和输入长度。
- 验证：`curl http://localhost:8000/healthz` ✅；`POST /api/v1/leads/manual` ✅；`GET /api/v1/leads/{lead_id}` ✅；数据库查询 `leads=2`、`audit_events=2` ✅；`npm run lint` ✅；Python 编译检查 ✅。
- 仍未完成：前端 Dashboard 初始数据还来自 `MOCK_LEADS`；刷新页面后不会从后端重新加载数据库线索。下轮建议新增 `GET /api/v1/leads` 列表接口并让前端启动时拉取。

### 2026-06-04（补充：线索列表接口）

- 本轮：新增后端 `GET /api/v1/leads?limit=...` 列表接口；前端 `App` 启动时调用 `listLeads()`，把数据库记录映射为当前 UI 的 `Lead` 结构，后端不可用时显示黄色提示并保留 mock 数据。
- 验证：`curl 'http://localhost:8000/api/v1/leads?limit=10'` ✅，返回 2 条 PostgreSQL 线索；后端日志记录 `[api/leads/list] enter/success` 且只输出数量与 limit；`npm run lint` ✅；Python 编译检查 ✅；`docker compose ps` 显示 app/postgres/redis 正常运行。
- 下轮建议：实现 `PATCH /api/v1/leads/{lead_id}/status`，把前端 Approve/Archive/Review 状态按钮接到后端，并写入 `audit_events`。

### 2026-06-04（补充：状态更新与审计）

- 本轮：新增后端 `PATCH /api/v1/leads/{lead_id}/status`；`LeadRepository.update_status()` 在同一事务内更新 `leads.status/updated_at` 并写入 `audit_events` 的 `lead.status_changed`。
- 前端：`updateLeadStatus` 已改为调用后端状态 API，成功后用后端返回记录刷新当前列表；失败时回滚前端状态并显示提示。当前支持 UI 操作态 `contacted/in_review/sent/dnq/archived` 映射。
- 验证：`PATCH /api/v1/leads/lead-a72c81a8-f967-44ae-b477-ec17b5ef86ca/status` ✅；数据库确认该线索 `status=in_review` ✅；`audit_events` 出现 `lead.status_changed`，metadata 记录 `previous_status=received`、`new_status=in_review` ✅；`GET /api/v1/leads?limit=10` 返回最新状态 ✅；`npm run lint` ✅；Python 编译检查 ✅。
- 下轮建议：新增 `GET /api/v1/leads/{lead_id}/audit-events`，把详情页右侧写死审计时间线替换成真实审计记录。

### 2026-06-04（补充：真实审计时间线）

- 本轮：新增后端 `GET /api/v1/leads/{lead_id}/audit-events`，读取持久化审计事件；前端 `LeadDetailView` 进入详情时加载真实审计，替换原 `09:23/09:24` 硬编码假数据。
- 日志：后端新增 `[api/leads/audit] enter/success/not_found`；前端新增 `[client/leads/audit] enter/success/fail` 与详情页加载失败日志，只记录 `leadId`、数量、HTTP 状态、耗时，不输出邮箱、原文或密钥。
- 验证：`python3 -m py_compile backend/app/*.py backend/app/api/*.py backend/app/repositories/*.py backend/app/services/*.py` ✅；`npm run lint` ✅；`docker compose up -d --build app` ✅；`curl /healthz` ✅；`curl /api/v1/leads/lead-a72c81a8-f967-44ae-b477-ec17b5ef86ca/audit-events` ✅，返回手动入站与状态变更 2 条审计。
- 仍未完成：§2.6 的“谁批准”需要登录/用户身份后才能闭环；当前 actor 仍是 `system`、`frontend` 或验证脚本传入值。
- 下轮建议：继续 §1.1 Kimi 后端 service 层，或继续 §2.6 做审核动作真实化与操作者身份。

### 2026-06-04（补充：Gemini Flash 结构化提取）

- 本轮：按用户要求将结构化邮件字段提取定为 Gemini Flash + `temperature=0`；新增后端 `POST /api/v1/extraction/email`、`GeminiExtractionService`、`EmailExtractionRequest/Response` schema，并把 CORS 补到本地前端 `3001`。
- 文档：同步更新 `doc/prd.md`、`doc/业务规格.md`、`README.md` 与本 TODO，替换原“Haiku/Kimi 提取”口径为“Gemini 后端服务层”。
- 日志：新增 `[api/extraction/email]` 与 `[llm/gemini/extract]` 入口/成功/失败日志，只记录品牌、模型、temperature、输入长度、耗时和字段摘要，不输出邮件正文、API Key 或 Token。
- 验证：Python 编译 ✅；`npm run lint` ✅；`docker compose up -d --build app` ✅；`curl /healthz` ✅。真实 Gemini 样例请求已进入后端，但当前本机/容器访问 `generativelanguage.googleapis.com` 超时，返回 502；需网络连通后复测真实回包。

### 2026-06-04（补充：DNQ 硬规则 + 自动流水线）

- 本轮：新增 6 条确定性 DNQ 硬规则、2 条软风险标记、`dnq_reason` / `risk_flags` 持久化与审计；评分 API 命中 DNQ 后跳过 Gemini，确定性写入 `BD`。
- 自动化：新增 `POST /api/v1/leads/{lead_id}/pipeline`，依次执行并持久化“提取 → DNQ → 评分 → 起草”；手动录入成功后自动投递同一 Celery 流水线。
- 验证：完整依赖容器内后端单测 10/10 ✅（含 DNQ/risk rules 8 个 fixture、流水线顺序、DNQ 跳过 LLM）；Python 编译 ✅；`npm run lint` ✅；真实数据库 fixture 返回 `provider=rules`、`BD / DNQ-01`，审计包含 `lead.qualification.persisted` 与 `lead.score.persisted` ✅；真实手动入站已确认自动触发后台流水线，当前停在 Gemini 提取网络 `ConnectTimeout` 并记录脱敏失败日志。
- 仍未完成：真实 Gemini Key 当前无效，因此完整真实“提取 → 非 DNQ Gemini 评分 → Gemini 起草”待更换 Key 后复测。
- 下轮建议：更换有效 Gemini Key 后复测 `/api/v1/extraction/email`；随后把 Graph 邮件轮询/表单 webhook 接入同一 Celery 流水线。

### 2026-06-04（补充：提取字段持久化）

- 本轮：扩展 PostgreSQL `leads` 表，新增 PRD 提取字段列、`extracted_fields` JSONB 快照、`extracted_at` 与提取模型元数据；新增 `PUT /api/v1/leads/{lead_id}/extracted-fields`，用于把 Gemini/人工验证后的结构化提取结果写回线索。
- 审计：写回提取字段时追加 `lead.extracted_fields.persisted`，metadata 只记录 provider/model/temperature、`email_coherence` 和签证类别是否存在，不记录邮件原文。
- 验证：`python3 -m py_compile backend/app/*.py backend/app/api/*.py backend/app/repositories/*.py backend/app/services/*.py` ✅；`npm run lint` ✅；`docker compose up -d --build app` ✅；`PUT /api/v1/leads/lead-a72c81a8-f967-44ae-b477-ec17b5ef86ca/extracted-fields` ✅；`GET /api/v1/leads/{lead_id}` 可读回独立字段和 JSON 快照 ✅；`GET /api/v1/leads/{lead_id}/audit-events` 可见提取写回审计 ✅。
- 仍未完成：LLM 服务层还缺有效 Gemini Key 下的真实回包验证；PostgreSQL 还缺路由/通知、CRM 同步等后续业务表或字段。
- 下轮建议：更换有效 Gemini Key 后复测完整流水线，并接入 Graph 邮件轮询/表单 webhook。

### 2026-06-04（补充：Gemini 评分/起草服务）

- 本轮：按用户决策将评分/起草也改为 Gemini；新增 `GeminiTriageService`，包含 `score_lead()` 与 `draft_for_lead()`，均使用 Gemini REST `generateContent` + JSON Schema，并按阶段记录脱敏日志。
- API：新增 `POST /api/v1/leads/{lead_id}/score`、`POST /api/v1/leads/{lead_id}/drafts` 调 Gemini 并写回；新增 `PUT /api/v1/leads/{lead_id}/score`、`PUT /api/v1/leads/{lead_id}/drafts` 供离线/调试写入。
- PostgreSQL：扩展 `leads` 表，新增评分字段、草稿字段、模型元数据和时间戳；写入评分/草稿时生成 `lead.score.persisted`、`lead.drafts.persisted` 审计事件。
- 前端：`src/services/leadApi.ts` 现在会把后端返回的 `lead_score/score_rationale/email_draft/whatsapp_draft/phone_script` 映射到现有详情页 UI。
- 验证：Python 编译 ✅；`npm run lint` ✅；`docker compose up -d --build app` ✅；`PUT /score` ✅；`PUT /drafts` ✅；`GET /audit-events` 可见评分和草稿审计 ✅。
- 仍未完成：当前 Gemini Key 无效，`POST /score` 和 `POST /drafts` 的真实模型回包待更换 Key 后复测；模板库、费用硬编码仍待做。
- 下轮建议：更换有效 Gemini Key 后复测完整流水线，并将 Graph 邮件轮询/表单 webhook 接入同一入口。

### 2026-06-04（补充：DNQ 准确性与职责边界文档）

- 本轮：补充 `doc/prd.md`、`doc/业务规格.md`、`doc/技术方案与部署规划.md`，明确“Gemini 理解语言并提取事实 → 数据校验识别缺失/冲突 → Python 执行明确硬规则 → 不确定项转人工”的分工。
- 决策：字段为 `null/unknown`、互相矛盾或证据不足时不得自动 DNQ；Python 的确定性不能弥补上游提取错误或过期规则。
- 后续验证要求：独立 DNQ fixture 除应命中样本外，还需覆盖非 DNQ 与 unknown 防误杀样本，并记录误杀率。

### 2026-06-04（补充：Celery 可靠队列）

- 本轮：新增独立 Celery worker 容器与 `app.tasks.run_lead_pipeline`；手动入站和 `POST /api/v1/leads/{lead_id}/pipeline` 统一投递 Redis 队列并返回 `task_id`，新增任务状态查询接口。
- 可靠性：任务晚确认、worker 丢失重投、单并发；仅网络/超时、HTTP 429/5xx、数据库错误最多重试 3 次，永久 HTTP 4xx 直接失败；审计记录 queued/started/succeeded/failed 与 retry_count。
- 安全与日志：app/worker 容器改为非 root；Gemini 错误日志只输出脱敏 `status_code/error_status/error_reason`，真实验证识别出 `API_KEY_INVALID`，未输出 Key 或用户原文。
- 验证：后端容器单测 14/14 ✅；Python 编译 ✅；`npm run lint` ✅；`docker compose config --quiet` ✅；app/worker/postgres/redis 均运行 ✅；真实手动入站返回任务 ID、worker 消费、状态查询、失败审计与永久错误不重试均通过 ✅。
- 阻塞：当前 `.env` 中 `GEMINI_API_KEY` 无效；更换有效 Key 后才能完成真实提取→评分→起草全链路验证。

### 2026-06-04（补充：Manual Entry 两步引导式闭环）

- 前端：侧边栏 `Manual Entry` 改为全局两步弹窗；Step 1 只接收自然语言粘贴，Step 2 自动填充姓名/邮箱/电话/签证并要求选择品牌，可展开编辑全部评分字段；确认后进入详情并每 2 秒轮询任务与线索结果。
- 后端：新增 `POST /api/v1/extraction/manual`（ShengSuanYun）与 `POST /api/v1/leads/manual-confirmed`；确认字段与原文在同一事务落库并写审计，Celery 使用 `skip_extraction=true` 从 DNQ 开始，禁止覆盖人工修改。
- 模型：新增 OpenAI 兼容 JSON 客户端；提取使用 ShengSuanYun `google/gemini-3-flash`、`temperature=0`，评分/草稿使用 Kimi `kimi-k2.6` 非思考模式、`temperature=0.6`；任务重试时复用已持久化评分，避免重复计费。
- 验证：`npm run lint` ✅；`npm run build` ✅；Python 编译与 `git diff --check` ✅；后端容器单测 17/17 ✅；浏览器确认 Manual Entry 从任意页面打开 Step 1 弹窗 ✅；真实 ShengSuanYun 提取、确认式落库、Kimi 评分均成功，真实 Kimi 草稿在关闭思考模式后 HTTP 200 并持久化成功 ✅。
- 风险：ShengSuanYun 真实请求出现过一次 120 秒 `ReadTimeout`，前端已保留输入并支持重试；后续可增加服务端有限重试或备用提取路由。




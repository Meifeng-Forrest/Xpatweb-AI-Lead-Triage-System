# 开发计划：线索详情改为右侧宽抽屉 + 就地编辑 + 编辑审计

> 创建日期：2026-06-06
> 状态：待评审 / 待开工
> 关联：`src/App.tsx`（前端详情页）、`backend/app/api/leads.py`、`backend/app/services/auth.py`

---

## 1. 目标（这次要做成什么）

把现在的「整页线索详情」改成 **右侧宽抽屉**，让审核员能边看列表边处理，并把编辑模型从「全局编辑模式」改成「就地编辑（inline edit）」。

一句话验收标准：

> 在 Review Queue / Dashboard 列表页，点任意一条线索 → **右侧滑出宽抽屉**（约占屏幕 55–60% 宽），列表仍在左侧可见可继续点选；抽屉内分 Tab，**Actions 按钮常驻底部吸底**；信息/草稿等可编辑处各自带 ✎ 就地编辑；**拥有 `lead.draft.edit` 权限的角色（superadmin / agent）才能编辑，且每次编辑都会写一条活动审计**。

### 1.1 已确认的产品决策（来自需求沟通）

| # | 决策 | 说明 |
|---|---|---|
| D1 | 用右侧**宽抽屉**替代整页详情 | 宽度约 55–60%，左侧列表不被替换、可继续点选切换 |
| D2 | 列表项布局**不动** | 维持现状横排，不为抽屉收紧列表 |
| D3 | 沟通草稿放在「概览」Tab **最下方**，不单独拆 Tab | 阅读动线＝决策动线，避免没看草稿就发送 |
| D4 | **去掉全局「Edit Drafts」按钮**，改为就地编辑 ✎ | 基础信息中姓名/邮箱/电话/签证/来源/负责人/品牌 + 草稿就地可编辑；AI 评分/理由只读 |
| D5 | **编辑沿用现有 `lead.draft.edit` 权限：仅 superadmin / agent 可编辑** | approver / quality_lead **保持只审批/确认（不可编辑）**，reviewer 只读；**不扩大权限模型** |
| D6 | 所有编辑都要**写活动审计** | 谁、改了哪个字段、何时 |
| D7 | 底部 Actions 精简为：退回 / 归档 / 批准发送 | 跟线索状态联动 + 无对应权限时禁用（无草稿/pipeline 失败/无权限 → 禁用发送） |
| D8 | Tab 顺序：概览 / 调研简报 / 活动审计 | 审计放最后 |

---

## 2. 现状（事实基线，开工前先看这里）

### 2.1 前端详情页结构 — `src/App.tsx`

- [`LeadDetailView`](../src/App.tsx#L563)（约 563–1088 行）：当前是 `grid lg:grid-cols-3` 整页布局。
  - 左 2 栏：`info | brief` 两个 Tab + 下方独立「Communication Drafts」区块。
  - 右 1 栏：60 秒呼叫框 + Workflow Actions + Activity Audit。
- 渲染入口在 [`App` 主区](../src/App.tsx#L394)（394–425 行）：`selectedLeadId` 为真时，用 `AnimatePresence mode="wait"` **整块替换**掉列表（DashboardView / ReviewQueueView）。→ **这是改抽屉要动的核心：详情不再替换列表，而是叠加在右侧。**
- 顶部 Header 里有一个「返回箭头」（[App.tsx:352](../src/App.tsx#L352)），抽屉化后语义要从「返回列表」变成「关闭抽屉」。
- 编辑现状：全局 `editingDraft` 布尔开关（[App.tsx:591](../src/App.tsx#L591)），点「Edit Drafts」整片草稿变 textarea；基础信息 [`DetailItem`](../src/App.tsx#L1917) 是纯只读展示，**目前不可编辑**。
- 审计渲染：`AuditStep` / `auditText` / `auditIcon`（[App.tsx:2025-2071](../src/App.tsx#L2025)）已可复用。

### 2.2 权限 — `backend/app/services/auth.py`（[L28 ROLE_PERMISSIONS](../backend/app/services/auth.py#L28)）

| 角色 | 现有权限 |
|---|---|
| superadmin | lead.view / draft.edit / approve / reject / reject.confirm |
| approver | lead.view / **approve** |
| agent | lead.view / **draft.edit** / reject |
| quality_lead | lead.view / reject.confirm |
| **reviewer** | **仅 lead.view（只读）** |

前端 `can(permission)` 来自 [`AuthContext`](../src/contexts/AuthContext.tsx#L72)，已可用。

### 2.3 后端编辑接口现状

| 接口 | 鉴权 | 审计 | actor 来源 | 能否直接用于就地编辑 |
|---|---|---|---|---|
| `POST /{lead_id}/edit-draft`（[leads.py:837](../backend/app/api/leads.py#L837)） | ✅ `lead.draft.edit` | ✅ 有（带 reason） | ✅ `current_user` | ✅ **草稿编辑可直接复用** |
| `PUT /{lead_id}/extracted-fields`（[leads.py:491](../backend/app/api/leads.py#L491)） | ❌ 无 | ❌ 无 | `payload.actor`（pipeline 用） | ❌ **不可用于基础信息就地编辑** |

> 结论：**草稿就地编辑后端已就绪；基础信息就地编辑需要新增一个「带权限 + 带审计」的后端接口。**

---

## 3. 关键决策点 ✅（已拍板，开工依据）

### D-Q1：编辑权限 —— **不扩大权限模型，沿用现有 `lead.draft.edit`**

- 编辑能力（基础信息 + 草稿）一律以现有权限 `lead.draft.edit` 为门槛 → **仅 superadmin / agent 可编辑**。
- **approver / quality_lead 保持现状（只审批 / 确认，不可编辑）**，reviewer 只读。
- **`auth.py` 角色表不改动**：不新增 `lead.edit`、不扩大任何角色权限。基础信息的新后端接口直接复用 `require_permission("lead.draft.edit")`。

> 结论：删除原「方案 A 新增 lead.edit」思路。前后端鉴权统一用 `lead.draft.edit`，零角色表变更。

### D-Q2：基础信息可改字段 —— **姓名 / 邮箱 / 电话 / 签证 / 来源 / 负责人 / 品牌（共 7 项）**

- **可改（7 项）**：姓名、邮箱、电话、签证类型、来源（source）、负责人（assignedConsultant）、品牌（inboxBrand）。
  - 其中**品牌为枚举选择**（取值 `INBOX_BRANDS`，[constants.ts](../src/constants.ts)），用下拉而非自由文本；其余为文本/可约束输入（签证类型建议从 `VISA_TYPES` 选）。
- **只读（不可改）**：AI 评分 / 评分理由 / 置信度 / Est. Revenue（机器产出或模板推导，改了破坏审计可信度）。
- 签证类型改动**本期不触发重新评分**，仅记录字段变更审计。

### D-Q3：底部「批准发送」禁用规则

满足**任一**即禁用并显示原因提示：

1. `status ∈ {approved, rejected, archived}`（已处理完）；
2. **无任何草稿内容**（pipeline 未出草稿 / 失败）；
3. **当前用户无对应权限**（无 `lead.approve` → 禁用批准发送；其余 Action 同理按权限禁用）。

> 截图里 `Webhook Smoke / NOT SCORED`（pipeline failed）就是规则 2 的测试样本。

---

## 4. 目标设计（改成什么样）

### 4.1 布局示意

```
┌──────────────┬───────────────────────────────────┐
│  列表 (~42%)  │  抽屉 Drawer (~58%)                 │
│              │  ┌─────────────────────────────┐  │
│  R Research   │  │ 标题 + 关闭 ✕                │  │
│  W Webhook ◀──┼──│ [Leads Info] [调研简报] [活动审计]   │ ← Tab
│  W Webhook    │  │                             │  │
│  L Low Conf   │  │  基础信息（每项 ✎ 可编辑）     │  │
│  E E2E        │  │  AI 评分 + 理由（只读）        │  │
│  X Xiaoming   │  │  原始消息（折叠）              │  │
│              │  │  ─ 沟通草稿 V1/V2（每块 ✎）─   │  │
│              │  ├─────────────────────────────┤  │
│              │  │ [✕退回] [🗑归档]   [✅批准发送] │ ← sticky 吸底
│              │  └─────────────────────────────┘  │
└──────────────┴───────────────────────────────────┘
```

### 4.2 抽屉行为

- 打开：列表项点击 → 抽屉从右滑入（motion/react，已在用）。
- 关闭：✕ 按钮 / 点遮罩 / Esc。是否要遮罩？建议**半透明轻遮罩**但**不挡左侧列表点击**（即遮罩只覆盖中间空白区，列表仍可点切换下一条）。→ 这点实现上要注意 z-index 与点击穿透，§5 标为注意点。
- 切换：抽屉打开时点列表另一条 → 抽屉内容原地替换（`lead.id` 变化时 `useEffect` 已会重载 research/audit，复用现有逻辑）。

### 4.3 就地编辑交互

- 每个可编辑字段/区块右上角一个 ✎ 图标按钮。
- 点 ✎ → 该字段就地变输入框 + 出现 ✓保存 / ✕取消。
- 保存成功 → 调对应后端接口 → 写审计 → 局部刷新 lead。
- 无编辑权限（reviewer）→ 不渲染 ✎，纯展示。
- 草稿被改过 → 标一个「已修改」小标记，让审批人知道发的是改后版本。

---

## 5. 任务拆解

### 阶段一：抽屉骨架（不改编辑逻辑，先把容器搭出来）

- [ ] **F1** 新增 `LeadDetailDrawer` 容器组件（可由现有 `LeadDetailView` 重构而来），用固定定位右侧面板 + motion 滑入动画。
- [ ] **F2** 改 [`App` 渲染入口](../src/App.tsx#L394)：`selectedLeadId` 不再替换列表，列表常驻；抽屉作为 overlay 叠加渲染。
- [ ] **F3** 抽屉内重排为 Tab：概览 / 调研简报 / 活动审计（审计从右栏挪进 Tab，复用 `AuditStep`）。
- [ ] **F4** 概览 Tab 内容顺序：基础信息 → AI 评分/理由 → 原始消息 → 沟通草稿（草稿从原独立区块移入概览底部）。
- [ ] **F5** 底部 Actions 区做成 `sticky` 吸底：退回 / 归档 / 批准发送（精简掉 Edit Drafts 按钮）。
- [ ] **F6** Header 返回箭头语义改为关闭抽屉；补 Esc / 遮罩关闭。
- [ ] **F7** 60 秒呼叫框（GD/MF 高优先级）如何安放：建议放概览 Tab 顶部醒目位，或 Actions 区上方。（待定，§7 边界）

### 阶段二：就地编辑 + 审计（核心）

**后端**（D-Q1 已定：不改 `auth.py` 角色表，鉴权统一用 `lead.draft.edit`）

- [ ] **B1** 新增接口 `PATCH /{lead_id}/fields`（或 `POST /{lead_id}/edit-fields`）：
  - 鉴权 `require_permission("lead.draft.edit")`，actor = `current_user`（**复用现有权限，不新建**）。
  - 入参：可改字段子集 `name / email / phone / visa_category / source / assigned_consultant / brand`（共 7 项，见 D-Q2）；`brand` 服务端需校验在 `INBOX_BRANDS` 内。
  - **逐字段 diff，对每个真正变化的字段写一条审计**，`event_type = "lead.fields.edited"`，metadata 记录 `field`，**不落原文**（邮箱/电话仅记 `changed: true` 或掩码，遵守 CLAUDE.md 日志规范）。
  - 仿照 [`edit_draft`](../backend/app/api/leads.py#L837) 的日志与返回 `LeadRead` 模式（actor 取 `current_user`，含入口/参数摘要/成功失败日志）。
- [ ] **B2** 仓储层加 `edit_fields(...)`（或扩展现有方法）：更新字段 + 写审计，参考 `LeadRepository.edit_draft`。
- [ ] **B3** 前端审计渲染：在 `auditText` / `auditIcon`（[App.tsx:2038](../src/App.tsx#L2038)）补 `lead.fields.edited`（及现有草稿编辑事件）的人话文案与图标。
- [ ] **B4** 后端单测 `test_lead_fields_edit`：① reviewer / approver / quality_lead 调用 → 403；② superadmin / agent 改字段 → 成功且产生审计；③ 未变化字段 → 不产生审计。

**前端**

- [ ] **F8** `leadApi.ts` 新增 `editLeadFields(leadId, fields)`，对接 B1。
- [ ] **F9** 基础信息 `DetailItem` 升级为可就地编辑版本，姓名/邮箱/电话/签证/来源/负责人/品牌可编辑（品牌用 `INBOX_BRANDS` 下拉、签证建议用 `VISA_TYPES` 下拉；受 `can('lead.draft.edit')` 控制 ✎ 显隐；AI 评分/理由保持只读）。
- [ ] **F10** 草稿区从「全局 editingDraft 开关」改为「每块独立就地编辑」，复用现有 `onEditDraft`，受 `can('lead.draft.edit')` 控制。
- [ ] **F11** Actions 按 D-Q3 规则禁用：状态已处理 / 无草稿 / 无对应权限（如无 `lead.approve`）→ 禁用并显示原因提示。
- [ ] **F12** 草稿「已修改」标记。

### 阶段三：联调与验收

- [ ] **V1** 拿 `Webhook Smoke / NOT SCORED`（pipeline failed）验证：抽屉异常态、批准发送禁用。
- [ ] **V2** 用 reviewer 账号验证：全程只读、无 ✎、无 Actions 编辑。
- [ ] **V3** 用 approver / agent 验证：可编辑基础信息与草稿，审计正确出现。
- [ ] **V4** 边看列表边切换：抽屉打开时点下一条，内容正确刷新。

---

## 6. 数据 / 审计字段约定

新增审计事件（前后端对齐）：

| event_type | 触发 | metadata（脱敏后） |
|---|---|---|
| `lead.fields.edited` | 姓名/邮箱/电话/签证就地保存 | `{ field }`，邮箱/电话/姓名**不落原文**，仅记字段名与变更标记 |
| 草稿编辑事件（沿用 `edit-draft` 现有事件名） | 草稿就地保存 | `{ draft_type: email/whatsapp/phone, reason }`（沿用现有实现） |

> 注意：按 `CLAUDE.md`，审计与日志**不得输出邮箱/电话/姓名原文**，只记字段名 + 是否变更 + 操作人 ID。

---

## 7. 边界与风险

| 项 | 说明 / 处理 |
|---|---|
| 遮罩 vs 列表可点 | 抽屉 overlay 不能挡住左侧列表点击，否则 D1「可继续切换」失效。z-index/点击区域要单独测。 |
| 60 秒呼叫框安放 | 原在右栏，抽屉化后位置待定（建议概览顶部），别被 Tab 藏起来漏掉高优先级线索。 |
| 草稿被改后批准 | 「批准发送」发的是改后版本，需「已修改」标记让审批人有感知。 |
| 权限不外扩 | 已定 D-Q1：不改角色表，approver/quality_lead 仍不可编辑；前端务必用 `lead.draft.edit` 控制 ✎，避免误开放。 |
| 移动端/窄屏 | 58% 宽抽屉在窄屏要降级为全屏抽屉（本期可只保证桌面端）。 |
| 签证类型改动不重评分 | 已定 D-Q2：仅记字段变更审计，不重新触发评分。 |

---

## 8. 验收标准（Given/When/Then）

1. **抽屉切换**：Given 在 Review Queue；When 点一条线索；Then 右侧滑出宽抽屉、左侧列表仍可见，再点另一条抽屉内容原地刷新。
2. **就地编辑+审计**：Given 以 agent 登录、抽屉打开；When 点姓名旁 ✎ 改名并保存；Then 字段更新成功，活动审计新增一条「字段被编辑」记录（操作人=agent，不含原文）。
3. **不可编辑角色**：Given 分别以 reviewer / approver / quality_lead 登录；When 打开抽屉；Then 均看不到 ✎ 与编辑型操作，仅可浏览（approver 仍可批准、quality_lead 仍可确认 DNQ，但不能改字段/草稿）。
4. **字段范围**：Given 任意可编辑角色；Then 姓名/邮箱/电话/签证/来源/负责人/品牌出现 ✎（品牌为下拉），AI 评分/理由/Est. Revenue 无 ✎。
5. **状态联动**：Given 一条 pipeline failed、无草稿的线索；When 打开抽屉；Then「批准发送」禁用并提示原因；无 `lead.approve` 权限者同样禁用。
6. **草稿已改提示**：Given 草稿被就地修改后；Then 草稿区显示「已修改」标记，「批准发送」发送的是修改后内容。

---

## 9. 落地顺序建议

1. 先做 **阶段一（抽屉骨架）** —— 纯前端、风险低、可快速看到形态，先让你确认布局手感。
2. 再做 **阶段二（编辑+审计）** —— 后端接口（B1–B2）+ 前端就地编辑一起联调。
3. **阶段三** 按角色与异常态验收，回写 `TODO.md`（建议新增 §2.12「线索详情抽屉化 + 就地编辑」并把本文件链接进去）。

> Q1/Q2/Q3 已在 §3 拍板，无前置阻塞，可直接开工。

---

## 10. 待办引用

开工后请在 `TODO.md` 新增条目并与本文件双向链接：

```markdown
### 2.12 线索详情抽屉化 + 就地编辑（详见 docs/lead-detail-drawer-plan.md）
- [ ] 阶段一：抽屉骨架（F1–F7）
- [ ] 阶段二：就地编辑 + 审计（B1–B4 / F8–F12）
- [ ] 阶段三：联调验收（V1–V4）
- 决策已定：不扩权限（沿用 lead.draft.edit）/ 可改字段=姓名·邮箱·电话·签证 / 禁用规则见 D-Q3
```

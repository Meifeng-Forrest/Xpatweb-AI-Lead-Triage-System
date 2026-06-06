# 用户 / 角色 / 权限与管理员用户管理

## 功能概述

系统已具备轻量 JWT 登录、用户管理、5 角色权限门控、四眼审核、按用户配置路由 category，以及管理员 `Users` 界面。最新实现把角色限定为纯权限职责，把“谁接收哪类线索”并入用户编辑弹窗维护：角色回答“能做什么”，用户路由 category 回答“收哪类通知”。

## 已实现（自 TODO 归档）

- **归档日期**：2026-06-06
- **原 TODO 位置**：§2.9 用户 / 角色 / 权限 + 管理员用户管理、§2.10 角色精简（6→4）、§2.11 角色按职责重切（4→5）+ 路由并入用户表
- **验证**：2026-06-06，容器后端目标测试 23/23 通过；完整后端测试 `python -m unittest discover /app/tests` 62/62 通过；`npm run lint` 通过；`npm run build` 通过；API 冒烟确认 5 角色、用户列表包含 `routing_categories`、空路由兜底 active superadmin、按用户设置签证路由后只读路由总览同步变化。

### 实现摘要

- **认证与权限**：后端提供 `POST /api/v1/auth/login`、`GET /api/v1/auth/me`；JWT 使用 HMAC-SHA256；`AUTH_ENABLED=false` 时返回 dev `superadmin`，保证 demo 不被登录阻断。
- **角色与权限**：`ROLE_PERMISSIONS` 保留为后端代码常量，角色为 `superadmin`、`approver`、`agent`、`quality_lead`、`reviewer`；权限包括 `lead.view`、`lead.draft.edit`、`lead.approve`、`lead.reject`、`lead.reject.confirm`、`routing.config`、`user.manage`。
- **一人一角色**：`POST /api/v1/users` 与 `PATCH /api/v1/users/{user_id}` 强制 exactly one role；前端新增与编辑均使用 role radio，避免多角色造成职责不清。
- **审核门控**：审核动作从 token 读取真实 `current_user.user_id` 作为 actor；`approver` 与 `superadmin` 可最终批准；后端继续强制“批准人不能等于最近一次草稿编辑/提交人”。
- **路由配置**：底层保留 `routing_rules(category,user_id)` 表；配置入口并入 `Users` 表，每个用户可勾选 `escalation`、`dnq_reject`、`visa_verification`、`standard_review`；无在职配置时自动兜底到 active `superadmin`，防止通知漏发。
- **角色迁移**：启动 schema 初始化时先把历史 `lead_agent/team_lead` 合并为 `agent`，把 `escalation_handler/visa_verifier` 合并为 `reviewer`，再把历史 `admin` 幂等迁移为 `superadmin`；先插新角色再删除旧角色，避免主键冲突。
- **管理员用户管理**：前端 `Users` 页面仅 `user.manage` 可见；支持新增用户、启用/停用、单角色分配、重置密码。用户列表展示状态、角色、路由 tags；编辑弹窗集中维护用户基础信息、角色和路由。
- **路由写入口调整**：`GET /api/v1/routing/rules` 保留为只读总览；旧 `PUT /api/v1/routing/rules/{category}` 已废弃并返回 410，提示改用 `PUT /api/v1/users/{user_id}/routing-categories`。
- **安全日志**：登录、用户管理、路由配置、审核动作均记录入口/成功/失败摘要；日志只保留邮箱域名、角色数量、category 数量、状态、是否修改密码等摘要，不输出 token、密码或用户隐私原文。

### 角色权限矩阵

| 角色 | 权限 | 职责 |
| --- | --- | --- |
| `superadmin` | 全部 7 项 | 系统超级管理员：管用户、配路由、兜底审核和外发 |
| `approver` | `lead.view`、`lead.approve` | 最终批准外发 |
| `agent` | `lead.view`、`lead.draft.edit`、`lead.reject` | 一线顾问：看线索、改草稿、退回 |
| `quality_lead` | `lead.view`、`lead.reject.confirm` | 质量负责人：确认 DNQ / Bad 拒绝 |
| `reviewer` | `lead.view` | 只读审阅者：可作为升级、签证核查或常规审核收件人 |

### 已实现验收

- 管理员可以登录并读取当前用户、角色、权限（已通过）
- `/api/v1/users/roles` 只返回 5 个角色：`superadmin`、`approver`、`agent`、`quality_lead`、`reviewer`（已通过）
- 新增/编辑用户必须且只能设置一个角色，多角色请求返回 422（已通过）
- `approver` 与 `superadmin` 可 `Approve & Send`；`agent` 不能最终批准（已通过）
- 四眼审核同人批准返回 409（已通过）
- 停用/移除最后一个 active `superadmin` 返回 409，避免系统无人可管（已通过）
- 用户列表返回 `routing_categories`，前端 Users 表展示路由 tags（已通过）
- 管理员可在用户编辑弹窗中按用户勾选路由 category，并通过 `PUT /api/v1/users/{user_id}/routing-categories` 保存（已通过）
- `routing_rules` 为空时，四类路由均回退到 active `superadmin`，响应字段为 `fallback_to_superadmin=true`（已通过）
- 旧 `PUT /api/v1/routing/rules/{category}` 返回 410，避免继续使用独立 Routing 页写入口（已通过）
- 用户管理与路由配置操作写入 `user_audit_events`，metadata 不含密码、邮箱原文或隐私原文（已通过）

### 已实现 API

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/api/v1/auth/login` | 登录并签发 token |
| GET | `/api/v1/auth/me` | 当前用户、角色、权限 |
| GET | `/api/v1/users` | 管理员用户列表，包含每个用户的 `routing_categories` |
| GET | `/api/v1/users/roles` | 可分配角色列表 |
| POST | `/api/v1/users` | 新增用户，必须 exactly one role |
| PATCH | `/api/v1/users/{user_id}` | 修改显示名、单角色、启停状态 |
| POST | `/api/v1/users/{user_id}/password` | 重置用户密码 |
| PUT | `/api/v1/users/{user_id}/routing-categories` | 按用户设置路由 category |
| GET | `/api/v1/routing/rules` | 路由规则只读总览，包含 4 个 category 当前收件人和 superadmin fallback 状态 |
| PUT | `/api/v1/routing/rules/{category}` | 已废弃，返回 410 |

### 相关代码文件

- `backend/app/api/auth.py`
- `backend/app/api/users.py`
- `backend/app/api/routing.py`
- `backend/app/services/auth.py`
- `backend/app/services/routing.py`
- `backend/app/repositories/users.py`
- `backend/app/database.py`
- `backend/app/schemas.py`
- `backend/app/api/leads.py`
- `src/contexts/AuthContext.tsx`
- `src/components/LoginView.tsx`
- `src/services/authApi.ts`
- `src/services/usersApi.ts`
- `src/services/routingApi.ts`
- `src/App.tsx`
- 测试：`backend/tests/test_auth_service.py`、`backend/tests/test_database_migrations.py`、`backend/tests/test_lead_review_api.py`、`backend/tests/test_routing_rules_api.py`、`backend/tests/test_routing_service.py`、`backend/tests/test_users_api.py`

## 关联未完成（仍在 TODO）

- 权限矩阵自助编辑暂不做，`ROLE_PERMISSIONS` 继续保留为后端常量；等客户明确需要业务人员自行调整权限后再升级为数据库配置和 UI。
- 真实 Slack / Push / Email 通知通道仍未接入，当前 `Notifier` 仍是 ConsoleNotifier。

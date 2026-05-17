# Iteration: P1 认证与权限边界

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

把 Chronos 当前开发态 `X-User-Id` 用户上下文收束成明确的认证边界：本地开发继续可用，生产 / 准生产必须使用 Bearer JWT，并统一校验用户存在和启用状态。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P1 Frontend API Contract](../chronos-p1-frontend-api-contract.md)

### 背景

当前大多数 API 依赖 `get_current_user_id`，并通过 `X-User-Id` 做开发态 user isolation。这个方式适合早期快速迭代，但不能成为生产边界。Chronos 需要先把认证模式、失败关闭、用户启用状态和服务层 user_id 隔离的责任拆清楚，后续再补完整注册登录和 refresh token 生命周期。

### 目标

- 保留本地 `X-User-Id` 开发体验。
- 新增 `AUTH_MODE=jwt`，支持 `Authorization: Bearer <access_token>`。
- 当 `ENVIRONMENT=production` 或 `ALLOW_DEV_AUTH_HEADER=false` 时，开发态 header 失败关闭。
- 当 production 使用 JWT 时，默认 `SECRET_KEY` 失败关闭。
- 所有 API 入口统一拒绝不存在或 `is_active=false` 的用户。
- 不改变业务 Service 的 `user_id` 隔离模型。

### 非目标

- 不做注册、登录、密码重置。
- 不做 refresh token / session table。
- 不做 OAuth / 第三方身份提供方。
- 不改变现有业务 API path 或 response schema。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Me
- [x] Goals

### 产品人格

认证边界本身不暴露给用户的日常执行界面。它的价值是让 Chronos 在“安静可信”的底层保持清楚边界：不会在生产环境继续信任开发态 header，也不会让停用用户进入执行闭环。

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱
- [x] 不让 Task Detail 变成信息仓库
- [x] 不让 Focus 变成控制面板
- [x] 不让洞察和解释抢走行动感
- [x] 不让“聪明”压过“可信”

---

## 4. 需求范围

### 功能清单

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Auth Mode | `AUTH_MODE=dev_header / jwt` | Must | 默认保持本地开发 |
| Dev Header Guard | production 或禁用时拒绝 `X-User-Id` | Must | 失败关闭 |
| JWT Access Token | 支持 Bearer token 解码和 subject 用户绑定 | Must | 暂不提供登录接口 |
| JWT Config Guard | production JWT 禁止默认 `SECRET_KEY` | Must | 失败关闭 |
| Active User Guard | `is_active=false` 返回 403 | Must | API 入口统一处理 |
| 文档对齐 | 更新 API contract / architecture / guidelines / README | Must | 明确生产边界 |

### 用户故事

```text
作为 Chronos 用户，
我希望我的任务、目标、Focus 和报告只在我的账户上下文里可见，
以便系统足够可信，不会因为开发态 header 被误用而泄露数据。
```

```text
作为开发者，
我希望本地开发仍能用 X-User-Id 快速联调，但生产必须走 JWT，
以便开发效率和安全边界都清楚。
```

### 主要流程

```text
Local dev:
X-User-Id -> get_current_user -> user exists and active -> get_current_user_id -> Service user_id isolation

Production:
Authorization Bearer token -> decode JWT -> sub -> user exists and active -> get_current_user_id -> Service user_id isolation
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [ ] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无。

### API 变更

无 path / body 变更。认证 header 约定扩展：

| Mode | Header | 用途 |
| --- | --- | --- |
| `dev_header` | `X-User-Id: <uuid>` | 本地开发 |
| `jwt` | `Authorization: Bearer <access_token>` | 生产 / 准生产 |

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [x] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 本地 `AUTH_MODE=dev_header` 继续接受合法 `X-User-Id`。
- [x] production 环境不接受开发态 `X-User-Id`。
- [x] `AUTH_MODE=jwt` 接受合法 Bearer token。
- [x] `AUTH_MODE=jwt` 不接受只有 `X-User-Id` 的请求。
- [x] 无效、过期、非 access token 被拒绝。
- [x] production JWT 默认 `SECRET_KEY` 被拒绝。
- [x] inactive user 被拒绝。

### 数据验收

- [x] 无 DB migration。
- [x] Service 层继续使用现有 `user_id` 隔离。

### 体验验收

- [x] 本地开发联调入口保持简单。
- [x] 生产认证失败返回统一 error shape。

---

## 8. 测试计划

### 单元测试

- [x] Auth dependency tests
- [x] Core API smoke tests

### API 测试

- [x] dev header 正常路径
- [x] jwt 正常路径
- [x] invalid / expired token
- [x] inactive user

### 集成测试

- [x] 全量 unittest
- [x] compileall
- [x] git diff check

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 没有登录接口 | 前端暂时无法真实获取 token | 本轮只建立边界，后续补 auth endpoints |
| JWT SECRET_KEY 默认值弱 | 生产不安全 | production JWT 模式在 API 入口失败关闭 |
| dev header 仍默认开启 | 本地方便但可能误用 | production / disabled 配置会失败关闭 |

### 关键取舍

- 先做认证边界，不做完整账户系统，避免偏离核心执行闭环。
- 继续保留开发态 `X-User-Id`，但把它明确限制在非 production。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 认证模式拆为 `dev_header` 和 `jwt` | 兼顾本地效率和生产边界 | API dependency 统一入口 |
| 2026-05-17 | JWT token 只作为 access token 解码 | 本轮不做 session 生命周期 | 后续需补登录和 refresh token |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 JWT helper | `app/core/security.py` | `create_access_token` / `decode_access_token` |
| 2026-05-17 | 重写 API auth dependency | `app/api/deps.py` | dev header / jwt 双模式 |
| 2026-05-17 | 新增配置 | `app/core/config.py` | `ENVIRONMENT` / `AUTH_MODE` / `ALLOW_DEV_AUTH_HEADER` |
| 2026-05-17 | 新增测试 | `tests/test_auth_deps.py` | 9 个认证边界测试 |
| 2026-05-17 | 文档对齐 | docs / README | 明确生产边界 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_auth_deps tests.test_task_goal_api tests.test_capture_inbox_api tests.test_today_api tests.test_settings_api`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

### 未验证

- [ ] 真实登录 / refresh token 生命周期未实现，本轮只完成认证边界。

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 补 Auth endpoints：login / refresh / logout。
- 后续上线前可把当前 API 入口失败关闭升级为 app startup 配置检查。
- 后续接 OAuth / Apple / Google 时，仍复用 `get_current_user` 边界。

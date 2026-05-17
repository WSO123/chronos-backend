# Iteration: P1 Auth Endpoints v1

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

在上一轮认证边界基础上，补齐正式 token 获取入口：register、login、refresh、logout 和 auth/me，让前端不再只能依赖开发态 `X-User-Id`。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P1 Frontend API Contract](../chronos-p1-frontend-api-contract.md)

### 背景

上一轮已经把 API 认证拆成 `AUTH_MODE=dev_header / jwt`，但还没有正式发 token 的入口。为了让 P1 主线能进入真实联调，需要先补一个可用但克制的账号 token 闭环。

### 目标

- 支持用户注册并返回 access / refresh token。
- 支持 email / password 登录。
- 支持 refresh token 轮换，旧 refresh token 不能复用。
- 支持 logout 撤销 refresh token。
- refresh token 只保存 hash，不保存明文。

### 非目标

- 不做密码重置。
- 不做邮箱验证。
- 不做 OAuth / Apple / Google。
- 不做多设备会话管理界面。
- 不改变现有业务接口的 user_id 隔离方式。

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

### 产品人格

Auth endpoints 不进入 Today 的执行界面，也不增加用户日常操作负担。它只让 Chronos 的“可信赖”从开发态走向真实账户上下文。

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
| Register | 创建用户、写入 password hash、返回 token pair | Must | email 归一化小写 |
| Login | email / password 换 token pair | Must | inactive user 拒绝 |
| Refresh | refresh token 轮换 | Must | 旧 token 被撤销 |
| Logout | 撤销 refresh token | Must | 幂等 |
| Auth Me | 当前 Bearer token 返回 user profile | Should | 前端恢复会话 |

### 用户故事

```text
作为 Chronos 用户，
我希望可以通过账号登录并进入自己的执行系统，
以便我的任务、目标和复盘数据不会依赖开发态用户头。
```

```text
作为前端开发者，
我希望可以通过 register / login 拿到 Bearer token，
以便生产联调路径与后端 JWT 认证边界一致。
```

### 主要流程

```text
Register / Login -> access JWT + refresh token
Refresh -> revoke old refresh token -> issue new pair
Logout -> revoke refresh token
Business API -> Authorization Bearer -> get_current_user_id -> Service user_id isolation
```

---

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [x] DB Migration
- [x] Tests

### 数据模型变更

```text
User {
  password_hash nullable
}

AuthRefreshToken {
  user_id
  token_hash unique
  expires_at
  revoked_at
  last_used_at
}
```

### 状态机变更

```text
refresh_token active -> revoked
refresh_token active -> expired
```

### 事件变更

无。

### API 变更

| Method | Path | 用途 | Request | Response |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/auth/register` | 注册并发 token | email/password/name/timezone | token pair |
| POST | `/api/v1/auth/login` | 登录 | email/password | token pair |
| POST | `/api/v1/auth/refresh` | 刷新 token | refresh_token | token pair |
| POST | `/api/v1/auth/logout` | 撤销 refresh token | refresh_token | revoked |
| GET | `/api/v1/auth/me` | 当前用户 | Bearer token | user |

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

- [x] register 返回 token pair，并且密码不明文落库。
- [x] duplicate email 返回 409。
- [x] 空白 name / timezone 不允许注册。
- [x] login 返回 token pair，Bearer token 可访问 `/auth/me`。
- [x] invalid password 返回 401。
- [x] inactive user 不能登录。
- [x] production 默认 `SECRET_KEY` 不允许签发 token。
- [x] refresh 会轮换 token，旧 refresh token 不可复用。
- [x] logout 撤销 refresh token。

### 数据验收

- [x] `users.password_hash` 可为空，兼容已有开发态用户。
- [x] refresh token 只存 `token_hash`。
- [x] refresh token 关联 `user_id` 并随用户删除级联删除。

### 体验验收

- [x] 前端可以不依赖 `X-User-Id` 完成 JWT 会话。
- [x] 业务 API 仍复用统一 error shape。

---

## 8. 测试计划

### 单元测试

- [x] Auth API tests
- [x] Auth dependency tests

### API 测试

- [x] register / login / refresh / logout / auth me

### 集成测试

- [x] 全量 unittest。
- [x] Alembic SQL 检查。
- [x] compileall / diff check。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 没有邮箱验证 | 注册身份真实性不足 | MVP 暂不处理，后续独立迭代 |
| refresh token 只有服务端表，没有设备管理 | 用户无法查看设备会话 | 先保证 token 可撤销和可轮换 |
| 旧 dev seed 用户没有 password_hash | 不能用 login 登录 | 开发态仍可用 `X-User-Id`，正式用户走 register |

### 关键取舍

- 用不透明 refresh token + hash 落库，而不是 refresh JWT，降低撤销难度。
- 先做最小账号闭环，不引入 OAuth 和复杂 session 管理。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | refresh token 只存 hash | 避免 token 明文泄露风险 | logout / refresh 通过 hash 查找 |
| 2026-05-17 | refresh 时轮换 token | 防止旧 refresh token 长期可复用 | 旧 token 复用会被拒绝 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | Auth API | `app/api/v1/auth.py` | register / login / refresh / logout / me |
| 2026-05-17 | Auth service | `app/services/auth_service.py` | token pair / refresh rotation |
| 2026-05-17 | Auth schemas | `app/schemas/auth.py` | request / response |
| 2026-05-17 | Auth model | `app/models/user.py` | password_hash / refresh token |
| 2026-05-17 | Migration | `alembic/versions/20260517_0019_auth_tokens.py` | users + auth_refresh_tokens |
| 2026-05-17 | Tests | `tests/test_auth_api.py` | 9 个 Auth API 测试 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_auth_api tests.test_auth_deps`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`
- [x] `uv run alembic upgrade head --sql`

### 未验证

- [ ] 未在真实 PostgreSQL 连接上执行 `alembic upgrade head`，本轮已验证 SQL 生成。

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 增加密码修改 / 忘记密码。
- 增加邮箱验证。
- 增加会话列表和单设备撤销。
- 给 seed 脚本加可选密码，方便本地直接测试 login。

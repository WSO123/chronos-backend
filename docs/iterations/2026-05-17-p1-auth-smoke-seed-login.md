# Iteration: P1 Auth Smoke and Seed Login Polish

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

把上一轮 Auth endpoints 接到本地开发体验里：seed 用户可以可选写入登录密码并输出 token，新增 auth token smoke，验证 register / login / refresh / logout 和业务 API Bearer 访问能真实跑通。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P1 Frontend API Contract](../chronos-p1-frontend-api-contract.md)

### 背景

Auth endpoints 已经完成，但本地 seed 仍主要服务 `X-User-Id` 开发态。前端下一步联调 JWT 时，如果还要手动注册、复制 token、再准备 demo 数据，会让 P1 主线体验割裂。

### 目标

- `dev_seed_user.py` 支持 `--password` 和 `--emit-token`。
- `dev_seed_demo.py` 支持在准备 demo 数据时同步输出 token。
- 新增 auth token smoke，覆盖 token 获取、业务 API 访问、refresh 轮换和 logout 撤销。
- `verify_local.py` 支持 `--smoke auth`。
- README 和 P1 前端契约同步本地联调方式。

### 非目标

- 不新增 OAuth、邮箱验证、密码重置。
- 不改变业务 API 的 user isolation 逻辑。
- 不把开发态 `X-User-Id` 立即移除。
- 不引入真实外部 provider 或 P4 能力。

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

本轮不增加用户可见复杂度，只让账户上下文更可信、更可联调。用户看到的仍是清晰的执行入口，复杂的 token 生命周期留在系统背后。

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
| Seed password | 本地 seed 用户可写入密码 | Must | email 归一化 |
| Seed token output | seed 脚本可输出 token pair | Must | `--emit-token` 要求 `--password` |
| Auth smoke | register / login / me / business API / refresh / logout | Must | 使用独立 smoke 用户 |
| Verify entry | `verify_local.py --smoke auth` | Should | 不进入默认 CI |
| Docs sync | README 和 P1 contract 更新 | Should | 供前端联调 |

### 用户故事

```text
作为前端开发者，
我希望 seed demo 数据时能直接拿到 Bearer token，
以便用真实 JWT 会话联调 P1 主链路。
```

```text
作为后端开发者，
我希望 Auth token 闭环有 smoke 验证，
以便 register、login、refresh、logout 的回归不会只靠单测兜底。
```

### 主要流程

```text
dev_seed_user / dev_seed_demo --password --emit-token
-> local user has password_hash
-> output access / refresh token
-> frontend uses Authorization Bearer
```

```text
smoke_auth_token_loop
-> register
-> login
-> auth/me and me/overview with Bearer token
-> refresh rotates token
-> old refresh token rejected
-> logout revokes new refresh token
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [ ] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests
- [x] Scripts
- [x] Docs

### 数据模型变更

无。

### 状态机变更

```text
refresh_token active -> revoked
```

### 事件变更

无。

### API 变更

无新增 API。本轮验证既有 Auth endpoints 和业务接口。

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

- [x] `dev_seed_user.py --password` 会给新老用户写入 `password_hash`。
- [x] `dev_seed_user.py --emit-token` 缺少 `--password` 时失败。
- [x] `dev_seed_demo.py --password --emit-token` 会返回 demo 数据和 token pair。
- [x] seed 脚本对 email 做小写归一化。
- [x] auth smoke 能验证业务 API 可用 Bearer token 访问。
- [x] refresh token 轮换后旧 token 被拒绝。
- [x] logout 后 refresh token 被拒绝。
- [x] `verify_local.py --smoke auth` 可运行 auth smoke。

### 体验验收

- [x] 前端可以从一个命令拿到 demo 数据和 token。
- [x] README 与 P1 contract 都包含本地 JWT 联调入口。

---

## 8. 测试计划

### 单元测试

- [x] Auth API tests
- [x] Auth dependency tests
- [x] 全量 unittest discover

### Smoke

- [x] `scripts/smoke_auth_token_loop.py`
- [x] `scripts/verify_local.py --smoke auth`

---

## 9. 风险与取舍

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| seed 脚本输出 token 被误当生产方案 | 账号体系边界混淆 | 文档明确这是本地联调用途 |
| smoke 使用真实本地 DB | 本地迁移未跑会失败 | README 保留先 `alembic upgrade head` |
| refresh token 轮换行为被前端误用 | 旧 token 重复提交失败 | contract 写清旧 token 不能复用 |

---

## 10. 迭代结论

Auth 已从“接口存在”推进到“本地可联调、可 smoke 验证”。这补齐了 P1 主线进入真实用户会话前的最后一段开发体验，不改变 Chronos 的核心执行闭环和 AI 边界。

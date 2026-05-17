# Iteration: P1 Auth Frontend Error Contract

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

收口 P1 注册、登录、refresh、logout 的前端处理契约：不增加短信 / 邮件等账号复杂度，只把错误码、token rotation、logout 幂等和请求拦截建议写清楚，并新增 smoke 防止契约漂移。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos P1 Frontend API Contract](../chronos-p1-frontend-api-contract.md)
- [x] [Chronos Auth MVP Frontend Handling](../chronos-auth-mvp-frontend-handling.md)

### 背景

P1 Auth 已经能注册、登录、refresh、logout，也能通过 Bearer token 进入真实 Capture 主路径。下一步前端要实现登录页和请求拦截器，需要稳定知道每个错误码怎么处理。用户也明确要求注册不要复杂，因此本轮不加新账号功能，只做契约和验证。

### 目标

- 新增 Auth MVP 前端处理文档。
- 新增 `scripts/smoke_auth_frontend_error_contract.py`。
- `verify_local.py` 支持 `--smoke auth-errors`。
- 补充 unknown refresh / logout no-op 单测。
- README 和 P1 contract 暴露 Auth 错误契约入口。

### 非目标

- 不接短信验证码。
- 不接邮件验证。
- 不做 OAuth / Apple / Google。
- 不做密码重置。
- 不改变 token 签发和业务状态。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Focus
- [x] Report

### 产品人格

注册和登录应当轻盈、直接、可信，不让账号系统制造额外压力。本轮把复杂的 token 轮换和错误处理留给系统与文档，不把用户拖进验证码和多步骤认证。

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
| Auth handling doc | 前端注册 / 登录 / refresh / logout 处理建议 | Must | 不加账号新能力 |
| Error contract smoke | 验证关键错误码稳定 | Must | 本地 DB |
| Verify entry | `verify_local.py --smoke auth-errors` | Should | 可选 |
| Unit tests | unknown refresh / logout no-op | Should | 防回归 |

### 用户故事

```text
作为前端开发者，
我希望有一张清楚的 Auth 错误码处理表，
以便登录页和请求拦截器可以保持简单稳定。
```

```text
作为 Chronos 用户，
我希望注册登录不要被验证码、邮件确认或复杂账号流程打断，
以便更快进入今天的执行安排。
```

### 主要流程

```text
Register / Login
-> store access + refresh token
-> API returns ACCESS_TOKEN_EXPIRED
-> single-flight refresh
-> replace both tokens
-> retry once
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [ ] Service
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
refresh_token unknown -> logout no-op
```

### API 变更

无新增 API。本轮只固化既有错误契约。

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

- [x] 文档明确 P1 不做短信、邮件验证、OTP、OAuth。
- [x] 文档说明 register / login / logout 页面状态。
- [x] 文档说明 refresh token rotation 和 single-flight refresh。
- [x] 文档给出前端错误码处理表。
- [x] smoke 覆盖 duplicate register、invalid login、missing bearer、invalid auth header、expired access token、refresh reuse、logout no-op。
- [x] 单测覆盖 unknown refresh token 和 unknown logout token。

---

## 8. 测试计划

- [x] `uv run python -m unittest tests.test_auth_api tests.test_auth_deps`
- [x] `uv run python scripts/smoke_auth_frontend_error_contract.py`
- [x] `uv run python scripts/verify_local.py --smoke auth-errors`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| Auth 过早复杂化 | 分散 P1 核心闭环资源 | 明确不接短信 / 邮件 / OAuth |
| refresh 并发复用 | 前端偶发掉登录 | 文档要求 single-flight refresh |
| 错误码漂移 | 登录页处理失效 | smoke 固化前端错误契约 |

---

## 10. 迭代结论

Auth 现在保持最小可用，同时前端实现路径更清楚。账号系统不扩张，开发资源继续优先服务 Chronos 的输入、编排、执行和反馈闭环。

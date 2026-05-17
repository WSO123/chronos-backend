# Iteration: P1 Bearer Capture Loop Smoke

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

新增 Bearer token 模式下的真实 Capture 主路径 smoke，从 register 开始，经过 Capture、Inbox、Today、Task Detail、Focus、Daily Report 和 Me Overview，验证 P1 第一日使用路径不依赖开发态 `X-User-Id` 或预置 demo task。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos P1 Frontend API Contract](../chronos-p1-frontend-api-contract.md)
- [x] [Chronos P1 Bearer API Walkthrough](../chronos-p1-bearer-api-walkthrough.md)

### 背景

上一轮 Bearer walkthrough 使用 seed demo task 验证 Today -> Focus 主路径，但真实新用户更可能先从 Capture 输入任务。需要一条 smoke 证明正式 token 会话下，Capture 输入能经过 Inbox 确认进入 Today，并最终完成执行和复盘。

用户也明确提醒注册不要变复杂。P1 Auth 只做 email + password + JWT，不引入短信、邮件验证、OTP 或 OAuth。

### 目标

- 新增 `scripts/smoke_p1_bearer_capture_loop.py`。
- `verify_local.py` 支持 `--smoke p1-bearer-capture`。
- README、P1 contract、Bearer walkthrough 同步真实 Capture 主路径。
- 文档明确 P1 注册不接短信 / 邮件服务。

### 非目标

- 不新增注册验证码。
- 不接短信、邮件、OTP、OAuth 或第三方账号服务。
- 不改变 Capture -> Inbox 需要用户确认的产品边界。
- 不让 LLM 直接创建 Task / Goal 绕过 Inbox。

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

这轮强化的是“输入后自然进入行动”的主线，而不是做更重的账号系统。注册保持轻，复杂度留在后台验证链路里。

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
| P1 Bearer Capture smoke | JWT 模式跑真实 Capture 主路径 | Must | 使用本地 DB |
| Verify entry | `verify_local.py --smoke p1-bearer-capture` | Should | 可选验证 |
| Auth MVP boundary docs | 明确无短信 / 无邮件服务 | Must | 控制成本和复杂度 |
| Walkthrough sync | 文档增加真实 Capture smoke | Should | 前端联调 |

### 用户故事

```text
作为新用户，
我希望注册后可以直接输入一条任务并进入今天的执行序列，
以便 Chronos 从第一天就帮我把输入变成行动。
```

```text
作为开发者，
我希望 JWT 模式下的 Capture -> Inbox -> Focus 主路径有 smoke，
以便不会只验证 seed demo 的理想路径。
```

### 主要流程

```text
POST /auth/register
-> POST /captures
-> POST /inbox/{id}/confirm
-> GET /today
-> GET /tasks/{task_id}
-> POST /tasks/{task_id}/breakdown
-> POST /focus-sessions
-> POST /focus-sessions/{id}/complete
-> POST /reports/daily/generate
-> GET /me/overview
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
- [x] Scripts
- [x] Docs

### 数据模型变更

无。

### 状态机变更

```text
Capture parsed -> Inbox pending -> Inbox confirmed -> Task active
Task active -> in_focus -> completed
FocusSession active -> completed
DailyPlanItem planned -> completed
```

### 事件变更

使用既有事件，无新增事件。

### API 变更

无新增 API。本轮只新增 smoke 和文档。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

- Capture Parser Agent：通过 `POST /captures` 解析输入，但结果进入 Inbox，由用户确认后才创建 Task。
- Task Breakdown Agent：通过 `POST /tasks/{task_id}/breakdown` 生成步骤建议，用户仍可编辑。

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

- [x] smoke 使用 `/auth/register` 获取 token，不使用 `X-User-Id`。
- [x] Capture 结果进入 Inbox pending。
- [x] Inbox confirm 后创建 Task。
- [x] Today 能看到该 Task。
- [x] Task Detail 能承接 Today item。
- [x] Task Breakdown 创建 steps 并写入 AIJob。
- [x] Focus complete 后 Today item 变为 completed。
- [x] Daily Report 计入完成任务和 focus minutes。
- [x] Me Overview 用户身份与注册用户一致。
- [x] 文档明确 P1 注册不做短信 / 邮件服务。

---

## 8. 测试计划

- [x] `uv run python scripts/smoke_p1_bearer_capture_loop.py`
- [x] `uv run python scripts/verify_local.py --smoke p1-bearer-capture`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| 注册系统膨胀 | 消耗早期开发资源 | 明确 P1 不接短信 / 邮件 / OTP / OAuth |
| Capture 解析失败影响主路径 | 新用户输入无法进入 Today | 保持 mock / fallback，结果先进入 Inbox |
| 文档和 smoke 漂移 | 前端联调误导 | `verify_local.py --smoke p1-bearer-capture` 做可重复验证 |

---

## 10. 迭代结论

P1 的真实用户输入闭环已经可以在 JWT 模式下验证。账号系统继续保持最小可用，资源优先投入 Capture -> Inbox -> Today -> Focus -> Report 这条核心执行主线。

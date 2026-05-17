# Iteration: P1 Bearer API Walkthrough

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

补一份前端可直接照着跑的 Bearer token 版 P1 API walkthrough，并新增对应 smoke，确保 JWT 模式下 Today -> Task Detail -> Focus -> Daily Report -> Me Overview 的主闭环真实可用。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P1 Frontend API Contract](../chronos-p1-frontend-api-contract.md)

### 背景

上一轮已经让 seed 脚本能输出 token，并补了 Auth token smoke。但前端真正联调时，还需要一条从 token 到 P1 主闭环的最小操作路径。否则接口虽然存在，前端仍要在 Today、Task Detail、Focus、Report 之间自行摸索字段。

### 目标

- 新增 Bearer token 版 P1 walkthrough 文档。
- 新增 `scripts/smoke_p1_bearer_execution_loop.py`。
- `verify_local.py` 支持 `--smoke p1-bearer`。
- README 与 P1 API Contract 指向 walkthrough。

### 非目标

- 不替代完整 OpenAPI / SDK。
- 不新增业务 API。
- 不改变 `X-User-Id` 开发态路径。
- 不扩展 P4 或商业化能力。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Me

### 产品人格

walkthrough 把调试复杂度留给文档和 smoke，让前端实际页面仍保持清晰、轻量、可行动。

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
| Bearer walkthrough | 用 curl 跑 P1 主闭环 | Must | 前端联调 |
| P1 Bearer smoke | 自动验证 walkthrough 主路径 | Must | 使用本地 DB |
| Verify entry | `verify_local.py --smoke p1-bearer` | Should | 可选验证 |
| README link | 开发入口暴露文档和 smoke | Should | 减少信息散落 |

### 用户故事

```text
作为前端开发者，
我希望有一条 Bearer token 版 P1 curl walkthrough，
以便不用猜接口顺序和字段就能完成主闭环联调。
```

```text
作为后端开发者，
我希望 walkthrough 对应的主路径有 smoke，
以便文档不会和真实接口行为漂移。
```

### 主要流程

```text
dev_seed_demo --password --emit-token
-> copy access token
-> GET /auth/me
-> GET /today
-> GET /tasks/{task_id}
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
Task active -> in_focus -> completed
FocusSession active -> completed
DailyPlanItem planned -> completed
```

### 事件变更

使用既有事件：

- `FOCUS_SESSION_STARTED`
- `FOCUS_SESSION_COMPLETED`
- `TASK_COMPLETED`

### API 变更

无新增 API。本轮只验证和记录既有 API 调用顺序。

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

- [x] 文档说明 JWT 模式启动方式。
- [x] 文档说明如何从 seed demo 输出复制 access / refresh token。
- [x] 文档覆盖 Auth Me、Today、Task Detail、Focus、Daily Report、Me Overview。
- [x] 文档列出常见认证和状态错误。
- [x] smoke 使用 Bearer token 而不是 `X-User-Id`。
- [x] smoke 验证 Focus 完成后 Today item 和 Daily Report 更新。

### 体验验收

- [x] 前端可以按文档从 demo token 跑完整 P1 主路径。
- [x] 文档不鼓励展示算法调试字段，仍遵守轻量产品约束。

---

## 8. 测试计划

- [x] `uv run python scripts/smoke_p1_bearer_execution_loop.py`
- [x] `uv run python scripts/verify_local.py --smoke p1-bearer`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 处理 |
| --- | --- | --- |
| curl 文档与接口漂移 | 前端联调浪费时间 | 增加对应 smoke |
| 前端误把 debug 字段搬上 UI | Today / Task Detail 变重 | 文档明确页面映射和展示边界 |
| Bearer 联调忘记切 `AUTH_MODE=jwt` | 请求返回 `MISSING_USER_ID` | walkthrough 写入常见错误 |

---

## 10. 迭代结论

P1 现在不仅有接口合同，也有一条可手动执行、可自动 smoke 的 Bearer token 主闭环。下一步可以继续进入更核心的执行体验打磨，而不是停留在认证接线层。

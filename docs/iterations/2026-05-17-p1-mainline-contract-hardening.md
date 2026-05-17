# Iteration: P1 Mainline Contract Hardening

> 状态：Done  
> 阶段：P1  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

把 P1 核心闭环从“已有多个局部 smoke”收敛成一条可被前端联调依赖的主线契约验证。

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Today Quick Action -> Daily Report -> Me
```

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

当前 P1 已具备 Capture、Inbox、Today、Task Detail、Focus、Daily Report 和 Me Overview 的独立能力，也已有 Bearer capture smoke 和 mainline state smoke。但继续做 P2 个性化 planning 前，需要先确保 P1 主链路对前端暴露的合同足够稳定：每个关键页面读取到的状态、进度和下一步动作必须一致。

### 目标

- 新增一条 P1 主线契约 smoke，覆盖完整前端主路径。
- 验证 Today 快速操作中的 postpone 与 Focus complete 都会同步 Task Detail、Daily Report 和 Me Overview。
- 将 smoke 接入 `verify_local.py`，后续可通过统一入口显式运行。

### 非目标

- 不新增业务 API。
- 不改变 Planning Engine 排序逻辑。
- 不接 P3 语音、图片、外部数据源或提醒。
- 不接真实 LLM provider。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Daily Report -> Me
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Me
- [ ] Goals
- [ ] AI Agent

### 产品人格

本轮不增加可见复杂度，只补充主线可验证性。用户侧仍然看到轻量、清晰、可信的执行链路；复杂状态一致性留在后端 smoke 中验证。

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
| P1 contract smoke | 新增 `scripts/smoke_p1_mainline_contract.py` | Must | 覆盖完整 P1 前端主路径 |
| verify_local 接入 | 新增 `--smoke p1-mainline` | Must | 统一验证入口 |
| 文档更新 | README / P1 API Contract / Mainline Review 增加命令 | Should | 后续迭代可复用 |

### 用户故事

```text
作为 Chronos 用户，
我希望输入、执行和复盘之间的状态始终一致，
以便我信任 Today 给出的下一步行动。
```

```text
作为前端开发者，
我希望有一条完整 P1 主线 smoke，
以便联调前确认关键页面合同没有回退。
```

### 主要流程

```text
Register / Auth Me
-> Capture 两个 task
-> Inbox confirm
-> GET Today
-> Task Detail
-> Focus start / complete
-> Today item postpone
-> GET Daily Report
-> GET Me Overview
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

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

复用既有事件：

- `TASK_CREATED`
- `TASK_COMPLETED`
- `TASK_POSTPONED`
- `DAILY_PLAN_ITEM_UPDATED`
- `DAILY_REPORT_GENERATED`

### API 变更

无新增 API。本轮只通过现有接口验证合同。

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
- [x] 失败时有 fallback
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] Capture confirm 后在没有 active Today 时不隐式创建 Today。
- [x] GET Today 后能找到已确认任务。
- [x] Task Detail 的 `today_context` 与 Today item 对齐。
- [x] Focus active / completed 状态能被 Task Detail 和 Today 读取。
- [x] Today item postpone 会同步 Task Detail。
- [x] Daily Report 和 Me Overview 指标与执行结果一致。

### 数据验收

- [x] 关键数据正确落库。
- [x] 状态机流转正确。
- [x] ActivityEvent 使用既有事件记录。
- [x] 不新增 AIJob。

### 体验验收

- [x] 用户能清楚知道下一步。
- [x] 页面默认信息不过载。
- [x] 核心流程不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] `tests/test_p1_mainline_contract_smoke_script.py`

### API / Smoke 测试

- [x] `scripts/smoke_p1_mainline_contract.py`
- [x] `uv run python scripts/verify_local.py --smoke p1-mainline`

### 手动验证

```text
uv run python scripts/smoke_p1_mainline_contract.py
uv run python scripts/verify_local.py --smoke p1-mainline
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| smoke 变成业务逻辑替代品 | 测试过重，后续维护困难 | 只验证主线合同，不引入测试专用业务字段 |
| 覆盖 P2/P3 过多 | 偏离 P1 收口 | 本轮不验证 Goals / Energy / Reminder |

### 关键取舍

- 取舍 1：新增独立 P1 contract smoke，而不是继续扩大既有 P2 / mainline state smoke。
- 取舍 2：使用现有 API 验证，不为了测试新增任何接口或字段。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | P1 主线契约单独成 smoke | 后续 P2 planning 个性化会频繁修改状态流，先锁定 P1 前端合同 | 降低核心闭环回退风险 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 P1 主线契约 smoke | `scripts/smoke_p1_mainline_contract.py` | 完整验证 P1 主链路 |
| 2026-05-17 | 新增 smoke helper 单测 | `tests/test_p1_mainline_contract_smoke_script.py` | 验证 smoke payload 判定 |
| 2026-05-17 | 接入统一验证入口 | `scripts/verify_local.py` | 新增 `--smoke p1-mainline` |
| 2026-05-17 | 更新文档命令 | `README.md`, `docs/chronos-p1-frontend-api-contract.md`, `docs/chronos-mainline-capability-review-2026-05-17.md` | 方便后续迭代复用 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_p1_mainline_contract_smoke_script`
- [x] `uv run python scripts/verify_local.py --smoke p1-mainline`

### 未验证

- [ ] 真实前端页面联调。

### 已知问题

- 无。

---

## 13. 后续迭代建议

- 下一轮进入 `P2 Planner Personalization v1`，让历史执行行为开始影响 Today 编排。
- 在 P2 个性化迭代后继续跑 `--smoke p1-mainline`，防止核心闭环被算法调整影响。

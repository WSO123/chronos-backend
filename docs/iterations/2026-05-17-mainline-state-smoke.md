# Iteration: Mainline State Consistency Smoke

> 状态：Done
> 阶段：P1 / P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增一条主线状态一致性 smoke，把最近几轮补上的 `Inbox -> Today`、依赖刷新、优先级刷新、Task Detail、Focus auto-link 和 Daily Report auto-refresh 串成可重复回归的 API 场景。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Mainline Capability Review](../chronos-mainline-capability-review-2026-05-17.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P1/P2 主线已经补齐了多处状态联动，但这些能力分散在不同单测和旧 smoke 中。需要一条更贴近真实前端调用顺序的 smoke，防止后续修改 Today / Task / Focus / Report 时把主线状态一致性改坏。

### 目标

- 通过 API 路径覆盖已有 active Today 后确认 Inbox Task 会刷新当前 plan。
- 覆盖依赖变化触发 Today `system_refresh`，并让 Goal Detail 推荐下一步尊重未完成前置任务。
- 覆盖优先级 / 价值修正触发 Today `manual_adjust`，并在 Strategy Detail 中体现用户修正。
- 覆盖 Task Detail 的 `today_context` 与当前 Today item 一致。
- 覆盖未传 `daily_plan_item_id` 时 Focus 自动绑定当前 Today item。
- 覆盖 Focus 完成只更新执行状态，不触发 Today 重排。
- 覆盖 Daily Report GET 在执行指标变化后刷新同一条 report。

### 非目标

- 不新增业务功能。
- 不新增前端页面。
- 不扩展 P3/P4。
- 不做真实 LLM provider 验收。

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
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

- 轻盈：只验证用户可见主线状态，不新增复杂测试平台。
- 克制：不把 P3/P4 或真实 provider 纳入本轮。
- 可信赖：关键状态联动有可重复 smoke。
- 聪明但不炫耀：Strategy Detail 只验证解释信号存在，不把 score 驾驶舱推到 Today。

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
| Mainline state smoke | 新增 `scripts/smoke_mainline_state_consistency.py` | Must | 真实 API 路径 |
| Verify runner hook | 支持 `--smoke mainline-state` | Must | 进入本地验证入口 |
| Smoke payload validation | 输出结构化 evidence payload | Should | 便于后续 review |
| Unit tests | 覆盖 payload validation | Should | 不依赖真实 DB |

### 用户故事

```text
作为后续开发者，
我希望一次命令能验证核心执行闭环的状态联动，
以便改 Today、Focus 或 Report 时不把用户当天执行数据改分叉。
```

```text
作为产品负责人，
我希望主线 smoke 能覆盖“今天先做什么”和“做完是否更新可信”这两个核心问题，
以便确认迭代仍围绕 Chronos 的 Execution OS 主线。
```

### 主要流程

```text
注册用户
-> 创建 Goal / Task
-> GET Today
-> 添加依赖并刷新 Today
-> Capture / Inbox confirm 新 Task
-> 调整 Task priority
-> Task Detail 校验 today_context
-> 先生成 Daily Report
-> Focus 无 daily_plan_item_id 启动并完成
-> GET Today / Daily Report 校验状态自动对齐
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

无新增状态，只验证现有状态流转：

- `system_refresh`
- `manual_adjust`
- Focus `completed`
- Today item `completed`
- Daily Report same-row refresh

### API 变更

无。

---

## 6. AI / Agent 设计

无新增 Agent。

本轮只验证 Strategy Detail 中的主线解释信号：

- `user_adjusted_count`
- `dependency_protected_count`

不验证真实 provider，不让 LLM 改变排序。

---

## 7. 验证计划

### 自动化测试

- [x] `uv run python -m unittest tests.test_mainline_state_smoke_script`
- [x] `uv run python scripts/verify_local.py --smoke mainline-state`

### 手动验证

- [x] smoke 只覆盖 P1/P2 主线，不包含 P3/P4。
- [x] smoke 使用 API 路径，不绕过 service 直接改状态。
- [x] `git diff --check`

### 验收标准

- `verify_local.py` 支持 `--smoke mainline-state`。
- smoke 成功时输出 `scenario=mainline_state_consistency`。
- payload 包含依赖刷新、Inbox confirm 刷新、优先级刷新、Focus auto-link、Focus 不重排 Today、Daily Report auto-refresh 的状态检查。

---

## 8. 风险与边界

| 风险 | 处理 |
| --- | --- |
| smoke 变成过宽验收平台 | 只覆盖 P1/P2 主线状态一致性 |
| 跟 `ai-mainline` smoke 重叠 | 本轮验证状态联动，`ai-mainline` 验证 bounded Agent 链路 |
| 真实 DB 残留影响脚本 | 使用随机邮箱和标题 suffix |

---

## 9. 迭代完成记录

### 实际完成

- 新增 `scripts/smoke_mainline_state_consistency.py`。
- `scripts/verify_local.py` 支持 `--smoke mainline-state`。
- 新增 `tests/test_mainline_state_smoke_script.py` 覆盖 evidence payload 校验。
- 更新主线能力复盘文档的推荐验证基线。

### 偏航检查

- 未做 P3/P4。
- 未做商业化、前端页面或高级 Auth。
- 未新增业务能力，只补主线回归保护。

### 后续建议

如果本轮 smoke 稳定，下一轮再看 Planning Engine 边界场景是否需要补固定评估，而不是继续扩功能。

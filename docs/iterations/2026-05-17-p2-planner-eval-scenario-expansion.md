# Iteration: P2 Planner Eval Scenario Expansion

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

扩展 Planning Engine 离线评估场景，从 4 个基础容量 / 精力场景增加到 7 个场景，补上依赖链保护、用户手动优先级修正和重复中断行为反馈，提升 AI 编排核心能力的回归覆盖。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Planning Engine Evaluation v1](./2026-05-17-p2-planning-engine-evaluation-v1.md)
- [x] [P2 Planner Offline Eval JSONL](./2026-05-17-p2-planner-offline-eval-jsonl.md)

### 背景

上一轮 JSONL 让 planner eval 可以沉淀结果，但场景仍偏基础，主要覆盖容量和精力。Chronos 的核心不是普通排序，而是保护高价值任务、读懂依赖、尊重用户修正、从执行反馈中学习。若这些信号没有进入评估，后续调权重或接真实 LLM 时可能出现“接口没坏，但编排质量退化”。

本轮扩展固定场景，不改变 Planning Engine 行为，只把已有业务能力纳入离线回归。

### 目标

- 增加 `dependency_chain_protection` 场景。
- 增加 `user_priority_adjustment_protection` 场景。
- 增加 `behavior_feedback_penalizes_interruptions` 场景。
- 将 evaluator version 升级为 `p2-planning-engine-eval-v2`。
- JSONL details 增加 `item_signals`，保留每个 item 的核心评分信号。
- 更新评估测试，scenario count 从 4 到 7。
- 更新 README / LLM 架构 / JSONL 迭代文档。

### 非目标

- 不改变评分公式。
- 不接真实 provider 自动评估。
- 不新增数据库表。
- 不做 JSONL 对比报表。
- 不改变 Today / Strategy Detail 的用户可见信息密度。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Offline Eval
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [x] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本轮增强的是后台质量保护，不增加前台复杂度。它让 Chronos 的“有判断”更可回归：依赖、用户修正和行为反馈都应该安静地影响排序，而不是让用户在 Today 里面对复杂控制台。

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
| Dependency scenario | 前置任务必须排在依赖任务之前 | Must | 保护任务链 |
| User adjustment scenario | 用户手动提升优先级后进入 pinned | Must | 保留控制感 |
| Behavior feedback scenario | 多次中断任务被轻微降权 | Must | 执行反馈进入计划 |
| Item signals | JSONL details 输出评分信号 | Should | 便于对比 |
| Eval version bump | `p2-planning-engine-eval-v2` | Must | 标记场景集合变化 |

### 用户故事

```text
作为 Chronos 用户，
我希望系统能尊重任务依赖、我的手动修正和过去执行反馈，
以便 Today 的顺序更像一个可信的执行伙伴，而不是普通列表排序。
```

```text
作为后端开发者，
我希望这些核心 planner 信号进入离线评估，
以便后续改权重、改 prompt 或换 provider 时能发现编排质量退化。
```

```text
作为系统模块，
我希望 JSONL 记录每个 item 的关键评分信号，
以便后续比较不同 run 时可以定位是哪个信号影响了顺序。
```

### 主要流程

```text
run_evaluation
-> execute 7 deterministic scenarios
-> collect Today / Strategy / AIJob trace
-> collect item_signals
-> print JSON or write JSONL
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

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

使用既有事件：

- `TASK_DEPENDENCY_CREATED`
- `TASK_PRIORITY_ADJUSTED`
- `FOCUS_SESSION_INTERRUPTED`

### API 变更

无。

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

- Agent 名称：Daily Planner Agent
- 输入对象：Planning Engine deterministic candidates
- 输出对象：既有 `DailyPlannerOutput`
- Pydantic schema：不变
- fallback 策略：不变
- 是否需要用户确认：不需要，本轮是离线评估工具

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] evaluator version 升级为 `p2-planning-engine-eval-v2`。
- [x] scenario count 为 7。
- [x] dependency scenario 验证前置任务排在依赖任务之前。
- [x] user adjustment scenario 验证用户修正进入 pinned，并产生 user preference boost。
- [x] behavior feedback scenario 验证重复中断任务降权。
- [x] JSONL 每次输出 1 条 run summary 和 7 条 scenario result。

### 数据验收

- [x] 不新增 migration。
- [x] 不写开发数据库。
- [x] JSONL details 包含 `item_signals`。
- [x] AIJob trace 仍可记录 provider / prompt / usage。

### 体验验收

- [x] 用户主路径无变化。
- [x] Today 不增加技术字段。
- [x] Strategy Detail 不变成评估控制台。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_planning_engine_evaluation`

### API 测试

- [ ] 本轮不涉及 API。

### 集成测试

- [x] full local verify with planner eval and all smoke.

### 手动验证

```bash
uv run python -m unittest tests.test_planning_engine_evaluation
uv run python scripts/evaluate_planning_engine.py --run-id expanded-jsonl --jsonl-output /tmp/chronos-planner-eval-expanded.jsonl
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 场景断言过度绑定实现细节 | 评分微调时误报 | 断言业务结果和关键 signal，不断言完整分数 |
| 场景增多导致验证变慢 | 本地反馈变慢 | 当前 7 场景仍在秒级 |
| JSONL details 过大 | 对比不便 | 只输出核心 item signals |

### 关键取舍

- 取舍 1：新增场景复用已有业务 service，不造专用测试入口。
- 取舍 2：`item_signals` 只记录关键评分信号，不输出完整业务对象。
- 取舍 3：用户修正场景断言 `user_preference_score`，不要求新增 `priority_adjusted` 布尔字段。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | evaluator version 升级到 v2 | 场景集合变化需要可追踪 | JSONL 对比可区分版本 |
| 2026-05-17 | 增加 3 个核心信号场景 | 覆盖 Chronos 编排核心价值 | scenario count 变为 7 |
| 2026-05-17 | JSONL details 增加 item_signals | 支持后续对比和排障 | 不影响默认 UI |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 扩展 eval scenarios | `scripts/evaluate_planning_engine.py` | dependency / adjustment / behavior |
| 2026-05-17 | 更新 evaluation tests | `tests/test_planning_engine_evaluation.py` | 7 scenarios / JSONL 8 records |
| 2026-05-17 | 更新文档 | README / LLM / JSONL iteration | 场景说明 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_planning_engine_evaluation`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id expanded-jsonl --jsonl-output /tmp/chronos-planner-eval-expanded.jsonl`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未接真实 provider 自动评估。

### 已知问题

- 7 个 scenarios 仍不是完整真实用户任务分布；多 Goal 竞争和超期目标恢复已在后续 v3 evaluator 迭代补充。

---

## 13. 后续迭代建议

1. 已在后续迭代补充 JSONL 对比脚本，读取多次评估并输出 provider / prompt 差异摘要。
2. 增加真实 provider 手动验收记录模板，记录 model、usage、prompt checksum 和结论。
3. 已在后续迭代补充多 Goal 竞争 / 超期目标恢复的 planner eval 场景。

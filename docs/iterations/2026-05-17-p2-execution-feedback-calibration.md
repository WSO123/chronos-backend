# Iteration: P2 Execution Feedback Calibration

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Planning Engine 在重新编排时读取真实 Focus 执行结果，把任务估时校准为“剩余工作量”，让 Chronos 开始具备越用越准的执行闭环。

---

## 2. 背景与目标

Chronos 的核心不是一次性排序，而是执行后能学习。上一轮已经让大任务能被切成今天可推进的一步；本轮继续把 Focus 真实投入时间纳入下一轮 Today 编排。

目标：

- Replan 时根据 `Task.actual_duration_min` 和 `Task.progress` 计算剩余估时。
- 不覆盖 `Task.estimated_duration_min`，只影响本次 DailyPlanItem 的今日计划时长。
- 在 `score_breakdown` 和 Strategy Detail 中解释执行反馈如何影响估时。
- Focus 完成 / 中断 / 延后事件记录 planned vs actual 的差异，供后续洞察使用。

非目标：

- 不做自动模型训练。
- 不让 LLM 改写任务估时。
- 不自动调整 Task 原字段。
- 不在 Focus 页面增加复杂控制面板。

---

## 3. 产品约束对齐

```text
Focus -> execution feedback -> next Today replan -> better remaining estimate
```

- [x] 强化执行闭环
- [x] 不扩 P3/P4
- [x] 不做前端页面
- [x] 不让 AI 隐式改业务状态
- [x] 保持 Today 轻解释

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Remaining estimate calibration | 根据实际投入时间计算剩余估时 | Must | 只影响 plan item |
| Progress-based remaining estimate | 若任务有部分进度，按进度计算剩余时长 | Should | 为未来部分完成打基础 |
| Execution feedback factor | Strategy factors 返回 `execution_feedback_count` | Should | 只用于解释 |
| Focus duration delta event | Focus 结束事件记录 planned / actual 差异 | Should | 供 report / insight 后续消费 |

### 用户故事

```text
作为正在持续推进大目标的用户，
我希望 Chronos 记住我已经在一个任务上投入过时间，
下次安排时不要再把它当成完整任务重新压给我。
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [ ] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 关键字段

- `score_breakdown.base_estimated_duration_min`：任务原始 / 语义估时。
- `score_breakdown.actual_duration_min`：任务已累计真实执行时长。
- `score_breakdown.remaining_estimated_duration_min`：本次编排使用的剩余估时。
- `score_breakdown.execution_feedback_applied`：是否应用执行反馈校准。
- `score_breakdown.execution_feedback_reason`：校准原因。
- `factors.execution_feedback_count`：当前主序列中被执行反馈校准的任务数。

---

## 6. AI / LLM 影响

本轮不新增 Agent，也不修改 Prompt。执行反馈校准属于确定性 Planning Engine 逻辑，LLM 仍只提供 bounded suggestion / explanation。

---

## 7. 验收标准

- [x] 已投入过时间但未完成的任务，重新编排时使用剩余估时。
- [x] Task 原估时不被覆盖。
- [x] Strategy Detail 可看到 `execution_feedback_count`。
- [x] task rationale 可解释执行反馈校准。
- [x] Focus 结束事件记录 planned / actual 差异。

---

## 8. 主线偏离 Review

本轮直接服务核心问题：Chronos 是否能根据真实执行变得更懂用户。没有扩展 P3/P4、商业化、前端页面或真实 provider 验收。

---

## 9. 验证记录

```bash
uv run python -m unittest tests.test_today_services tests.test_focus_services
```

结果：32 tests OK。

```bash
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
```

结果：306 tests OK；compile OK；git diff --check OK；9 个 planner eval 场景通过；planner eval policy 无 regression / change。

```bash
.venv/bin/python3 scripts/verify_local.py --smoke mainline-state
```

结果：306 tests OK；compile OK；git diff --check OK；MAINLINE-STATE smoke passed。

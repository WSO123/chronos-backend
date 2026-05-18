# Iteration: P2 Planner Preference Eval Scenario v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-18  
> 关联 Commit：待提交

---

## 1. 迭代摘要

把 Planner Review feedback preference 纳入 Planning Engine 离线评测基线，锁住“用户偏好被解释，但不改变 deterministic Today 编排”的产品边界。

---

## 2. 背景与目标

前两轮已经完成：

- `planner_review.feedback_summary`：从多次 Planner Review 反馈聚合出确定性偏好摘要。
- Strategy Explanation Agent：读取偏好摘要并用中文解释系统如何理解用户。

新的风险是后续重构可能把偏好摘要误用成隐藏控制面，导致 Today 自动扩容、自动拉回滚动任务或让 LLM 间接改变排序。本轮只补离线评测保护，不新增产品行为。

### 目标

- 升级 Planner Evaluator 到 `p2-planning-engine-eval-v7`。
- 新增场景 `planner_feedback_preference_explained_without_reordering`。
- 场景验证用户连续忽略 `respect_rollover` 后：
  - Strategy Detail 能解释“更愿意主动调整容量”。
  - Daily Planner review 建议切换为手动调整容量。
  - Today 仍保持原容量、主序列、滚动任务和确定性排序。
- 更新 golden policy 到 12 个 required scenarios。

### 非目标

- 不修改 Planning Engine 权重。
- 不让偏好摘要自动扩容或自动 replan。
- 不新增 API / DB / Agent。
- 不做 P3/P4、商业化、前端页面或提醒。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Planner Review Feedback -> Preference Explanation -> Today remains deterministic
```

本轮保护的是 Chronos “越来越懂用户”的可信边界：系统能读懂反馈并解释，但不会越权替用户改计划。

### 用户故事

```text
作为持续修正 AI 建议的用户，
我希望 Chronos 能记住并解释我的反馈偏好，
但不要在我没有明确操作时自动改掉今天的任务安排。
```

```text
作为 Planning Engine，
我希望偏好反馈只进入解释和审阅建议层，
以便保持 Today 编排的 source of truth 可测试、可解释、可回归。
```

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱。
- [x] 不让 Task Detail 变成信息仓库。
- [x] 不让 Focus 变成控制面板。
- [x] 不让洞察和解释抢走行动感。
- [x] 不让“聪明”压过“可信”。

---

## 4. 需求范围

| 功能 | 描述 | 优先级 | 备注 |
| --- | --- | --- | --- |
| Planner eval scenario | 新增偏好解释不改排序场景 | Must | deterministic |
| Policy manifest | 升级 active policy 到 v7 / 12 scenarios | Must | exact scenario set |
| Eval tests | 更新 scenario count / JSONL record count | Must | 防止基线漂移 |
| Baseline README | 更新当前 active baseline | Should | 文档同步 |

### 主要流程

```text
短容量 Today 生成滚动任务
-> Daily Planner 提示 respect_rollover
-> 用户连续忽略该建议
-> 重新编排仍保持容量与滚动边界
-> Strategy Detail 解释用户更倾向主动调整容量
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
- [x] Tests / Eval
- [x] Docs

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无，继续使用：

```text
PLANNER_REVIEW_FEEDBACK_RECORDED
```

---

## 6. 验收标准

- [x] 新 evaluator version 为 `p2-planning-engine-eval-v7`。
- [x] policy manifest 指向 `p2-planning-engine-eval-v7`，required scenario count 为 12。
- [x] 新场景验证 `capacity_flexibility_preferred` 出现在 Strategy Detail。
- [x] 新场景验证 Strategy explanation 包含“主动调整容量”。
- [x] 新场景验证容量仍为用户手动设置的 60 分钟。
- [x] 新场景验证滚动任务没有被自动拉回 Today 主序列。

---

## 7. 测试计划

```bash
uv run python -m unittest tests.test_planning_engine_evaluation tests.test_planner_eval_policy
uv run python scripts/evaluate_planning_engine.py
uv run python scripts/verify_local.py --planner-eval-policy
.venv/bin/python -m compileall app tests scripts
uv run python -m unittest discover -s tests
git diff --check
```

---

## 8. 防偏航 Review

- 本轮只补 P2 Planner 质量基线，没有新增功能入口。
- 没有让 LLM 或 feedback summary 控制排序。
- 没有把 Planner Review 做成 Today 首屏驾驶舱。
- 没有进入 P3/P4、商业化、外部集成或前端实现。
- 这轮服务于核心主线：让“越来越懂用户”保持可解释、可回归、可控。

---

## 9. 下一轮建议

P2 Planning User Learning Contract v1：整理并补强“用户反馈 -> 偏好摘要 -> 解释 / 审阅建议”的后端 contract，重点是让 API 返回和测试更清楚地表达哪些信号可影响解释、哪些不能影响 Today 排序。

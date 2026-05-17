# Iteration: P2 Planner Personalization v1

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

让 Planning Engine 开始读取用户的同类任务历史表现，把“越来越懂用户”落到 Today 编排的确定性信号里。

本轮不让 LLM 直接排序，也不让 Agent 隐式改业务状态。LLM 的价值在于提供任务语义类型，例如 `writing`、`admin`、`deep_work`；Planning Engine 再基于同类型任务的真实完成时长、中断、延后和完成率，调整今日估时、排序力度和解释。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Interaction Flow Design](../chronos-interaction-flow-design.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

Chronos 的核心不是普通 Todo，而是帮助用户把今天安排成真正做得出来的一天。只靠全局规则无法体现“懂用户”：同样是 30 分钟任务，有些用户写作经常超时，有些用户处理行政事项很顺手。P2 需要把语义理解和历史执行反馈接起来，但仍然保持可解释、可回退、可测试。

### 目标

- 使用 `TaskPlanningSignal.task_type` 作为同类任务的语义桥梁。
- 基于历史同类任务聚合真实执行画像：实际时长、超时、中断、延后、完成率。
- 将个性化画像写入 Today item 的 `score_breakdown`，并影响估时与排序分数。
- 在 Strategy Detail 中暴露个性化信号数量和自然语言解释。
- 将新增场景纳入 planner eval baseline，防止后续回退。

### 非目标

- 不新增 API。
- 不新增数据库表或 migration。
- 不让 LLM 直接生成最终排序。
- 不让 Daily Planner Agent 接管 Planning Engine。
- 不扩 P3/P4，不做提醒、外部数据源、社交或商业化。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Daily Report
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [x] Task Detail
- [ ] Focus
- [ ] Report
- [x] Goals
- [x] AI Agent

本轮直接作用在 Today 编排和 Strategy Detail 解释上，间接服务 Task Detail 的推荐时长与执行建议。Focus 和 Report 不新增页面能力，但后续执行数据会成为个性化画像输入。

### 产品人格

用户不需要看到复杂模型，只看到更贴近自己的安排：系统知道某类任务过去经常超时，因此今天更保守地估时；或者知道某类任务完成顺畅，因此排序时更敢推进。

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
| 同类任务画像 | 按 `task_type` 聚合同用户历史任务表现 | Must | 排除本次候选任务，避免自我污染 |
| 个性化估时 | 历史实际时长显著高于估时时，提高今日估时 | Must | multiplier 限制在 0.70 到 1.80 |
| 个性化排序信号 | 超时、中断、延后降低排序力度；稳定完成可轻微加分 | Must | 不覆盖 goal / dependency 规则 |
| Strategy 可解释性 | 暴露 `personalization_signal_count` 和 `personalization_signal` | Should | 前端无需新增复杂视图 |
| Planner eval baseline | 新增 `semantic_history_personalizes_duration` 场景 | Must | 锁住“懂用户”能力 |

### 用户故事

```text
作为 Chronos 用户，
我希望系统能记住我过去执行某类任务的真实节奏，
以便 Today 不再机械相信我最初填的估时。
```

```text
作为持续学习者或知识工作者，
我希望高价值任务能被安排得更可执行，
以便在时间不够时仍然最大化接近目标的概率。
```

```text
作为前端开发者，
我希望个性化信号仍然通过 Today / Strategy 的既有合同返回，
以便不用新增复杂页面也能解释排序原因。
```

### 主要流程

```text
TaskPlanningSignal.task_type
-> 历史同类 Task + ActivityEvent / actual_duration
-> 个性化画像
-> Planning Engine score_breakdown
-> Today item recommended_duration / rationale
-> Strategy Detail explanation
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [x] Service
- [ ] Models
- [x] Schemas
- [ ] Workers
- [x] Agents
- [ ] Storage
- [ ] DB Migration
- [x] Tests

### 数据模型变更

无。

### 状态机变更

无。

### 事件变更

无新增事件。个性化画像读取既有任务状态和执行事件。

### API 变更

无新增 API。

`GET /api/v1/today/strategy` 的 factors 增加：

```json
{
  "personalization_signal_count": 1
}
```

Today item 的 `score_breakdown` 增加一组解释字段：

```json
{
  "personalization_score": -4,
  "personalization_applied": true,
  "personalization_task_type": "writing",
  "personalization_sample_count": 2,
  "personalization_duration_multiplier": 1.8,
  "personalized_estimated_duration_min": 54,
  "personalized_duration_adjustment_min": 24
}
```

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] 失败时有 fallback
- [x] 用户保留修正权

### 边界说明

本轮依赖已有 `TaskPlanningSignal`。LLM 可以帮助识别任务语义类型，但个性化排序、估时和解释由确定性 Planning Engine 完成。没有语义信号或历史样本不足时，系统退回原有通用编排逻辑。

---

## 7. 验收标准

### 功能验收

- [x] 当前任务有语义类型且同类型历史样本达到阈值时，Today item 会出现 `personalization_applied=true`。
- [x] 历史同类任务经常超时时，今日估时会更保守。
- [x] 个性化分数进入 `total_score`，但不覆盖高价值目标、依赖和用户手动优先级。
- [x] Strategy Detail 返回 `personalization_signal_count`。
- [x] Today rationale 中能看到 `personalization_signal`。

### 数据验收

- [x] 不新增表，不改变既有业务状态。
- [x] 候选任务不会被纳入自己的历史画像。
- [x] `task_type=general` 不参与个性化画像，避免泛化噪声。
- [x] 样本不足时不应用个性化调整。

### 体验验收

- [x] 用户能理解为什么某类任务被更保守估时。
- [x] 前端无需展示复杂画像细节，也能解释排序依据。
- [x] LLM 失败不会阻塞 Today 生成。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_today_services.TodayServiceTests.test_planning_engine_uses_personalization_from_semantic_task_history`
- [x] `tests.test_planning_engine_evaluation`
- [x] `tests.test_planner_eval_policy`
- [x] `tests.test_llm_acceptance_record_generator`
- [x] `scripts/smoke_p1_mainline_contract.py`

### Planner Eval

- [x] `scripts/evaluate_planning_engine.py`
- [x] `scripts/verify_local.py --planner-eval --planner-eval-policy`
- [x] `scripts/verify_local.py --smoke p1-mainline`

### 手动验证

```text
.venv/bin/python3 scripts/evaluate_planning_engine.py
.venv/bin/python3 scripts/verify_local.py --planner-eval --planner-eval-policy
.venv/bin/python3 scripts/verify_local.py --smoke p1-mainline
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 历史样本过少导致误判 | Today 过早个性化 | 至少 2 个同类历史样本才应用 |
| LLM 语义类型不稳定 | 同类画像噪声 | `general` 不参与，且无信号时 fallback |
| 个性化压过目标价值 | 偏离高价值保护 | 分值保持小幅，不覆盖 goal / dependency 权重 |
| 用户不理解为什么估时变化 | 信任下降 | 返回 `personalization_signal` 和 Strategy explanation |

### 关键取舍

- 取舍 1：先做确定性个性化画像，而不是把 Daily Planner Agent 升级为黑盒调度器。
- 取舍 2：复用 `TaskPlanningSignal`，不新增表，减少迁移风险。
- 取舍 3：只暴露轻量因子，不把 Today 做成复杂数据驾驶舱。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 用 `task_type` 连接 LLM 语义理解和历史执行画像 | 这是让系统越来越懂用户的最小闭环 | Today 可以在不黑盒化的前提下个性化 |
| 2026-05-17 | 个性化只作为 Planning Engine 信号 | 保持确定性排序为主 | 降低 AI 隐式改状态的风险 |
| 2026-05-17 | 新增 planner eval v5 | 个性化是核心能力，需要回归保护 | 后续调整算法必须保留该场景 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增个性化画像与估时调整 | `app/services/planning_service.py` | 同类历史任务影响 Today 编排 |
| 2026-05-17 | Strategy factors 增加个性化计数 | `app/schemas/today.py` | 前端可解释 |
| 2026-05-17 | 新增 planner eval v5 场景 | `scripts/evaluate_planning_engine.py`, `docs/planner-eval-baselines/` | 覆盖语义历史个性化 |
| 2026-05-17 | 更新 API / Agent / 能力 review 文档 | `docs/chronos-p2-frontend-api-contract.md`, `docs/chronos-llm-agent-architecture.md`, `docs/chronos-mainline-capability-review-2026-05-17.md` | 对齐主线能力 |
| 2026-05-17 | 补充测试 | `tests/test_today_services.py`, `tests/test_planning_engine_evaluation.py`, `tests/test_planner_eval_policy.py` | 锁定行为 |

---

## 12. 验证结果

### 已验证

- [x] `.venv/bin/python3 -m unittest tests.test_today_services.TodayServiceTests.test_planning_engine_uses_personalization_from_semantic_task_history`
- [x] `.venv/bin/python3 -m unittest tests.test_today_services tests.test_planning_engine_evaluation tests.test_planner_eval_policy tests.test_llm_acceptance_record_generator`
- [x] `.venv/bin/python3 scripts/evaluate_planning_engine.py`
- [x] `.venv/bin/python3 scripts/verify_local.py --planner-eval --planner-eval-policy`
- [x] `.venv/bin/python3 scripts/verify_local.py --smoke p1-mainline`

### 未验证

- [ ] 真实 provider 生成的 `task_type` 在生产数据中的稳定性。
- [ ] 前端实际展示 Strategy 个性化解释。

### 已知问题

- 个性化画像目前只按 `task_type` 聚合，尚未细分目标、上下文、时段或用户显式偏好。

---

## 13. 后续迭代建议

- 下一轮建议做 `P2 Goal Progress Strategy v1`：把目标剩余任务、deadline、依赖和完成率进一步压进 Today 编排，让系统更明确地“每天帮用户接近目标”。
- 后续可继续做 `Execution Learning v2`：把 Focus 中断原因、实际开始时段、用户手动重排反馈纳入画像，但仍保持确定性可解释。

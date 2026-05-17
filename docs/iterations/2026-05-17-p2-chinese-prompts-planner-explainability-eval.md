# Iteration: P2 中文提示词与 Planner 可解释性评估

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：TBD

---

## 1. 迭代摘要

把 Chronos 已有 LLM Agent 提示词迁移为中文，并把 Planning Engine 的可解释性字段纳入离线 eval / policy，避免后续 planner、prompt 或 provider 迭代只验证排序而丢失“为什么这样安排”的产品信任基础。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

当前核心 AI 主线已经包含 Capture Parser、Task Breakdown、Strategy Explanation、Daily Report、Insight Detail 和 Daily Planner critique / suggestion。用户希望提示词改为中文，因为 Chronos 的产品语气、边界和用户体验本身是中文语境；同时前一轮 Planning Engine 可解释性已经进入 Strategy Detail，但离线 eval policy 仍偏重排序和容量信号。

### 目标

- 让所有已落地 Agent prompt 使用中文表达产品边界、输出要求和语气约束。
- 保持 prompt registry、version、checksum 和 AIJob trace 机制不变，避免迁移变成隐藏行为变更。
- 将 `score_explanation`、`dominant_factor`、`dominant_reason` 和 `score_signals` 纳入 planner eval / policy 必需字段。
- 升级 planner eval baseline 到 `p2-planning-engine-eval-v4`，让 explainability 成为核心规划质量的一部分。

### 非目标

- 不新增 Agent。
- 不让 Daily Planner Agent 接管排序。
- 不改变 Planning Engine 评分权重。
- 不引入真实 provider 默认调用。
- 不在本轮处理生产级认证和权限边界；该项作为下一轮独立迭代。

---

## 3. 产品约束对齐

### 核心路径

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

- [x] Capture
- [x] Today
- [x] Report
- [x] Me
- [x] AI Agent

### 产品人格

中文 prompt 更直接承载 Chronos 的人格：轻盈、克制、安静、可信赖、不施压。Agent 的输出仍被限制在建议、解释、润色和候选项范围内，复杂度留在系统背后，用户看到的是更容易开始的下一步。

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
| 中文 Prompt | 将 6 个 Agent prompt 改为中文边界和中文输出约束 | Must | 保留 schema 字段名 |
| Explainability Eval | planner eval 每个 scenario 必须校验可解释性字段 | Must | 覆盖 9 个固定场景 |
| Policy Baseline v4 | baseline manifest 升级到 v4 并要求解释字段 | Must | 默认 policy 路径同步 |
| 测试断言对齐 | prompt registry 测试改为断言中文边界 | Must | 避免英文 prompt 回流 |

### 用户故事

```text
作为 Chronos 用户，
我希望 AI 的解释和建议是中文、克制、可信的，
以便我能快速理解今天为什么这样安排，而不是被复杂系统细节打断。
```

```text
作为开发者，
我希望 planner eval 不只检查排序，还检查解释信号是否完整，
以便后续调整 Planning Engine 或 LLM provider 时不会损坏 Strategy Detail 的可信度。
```

### 主要流程

```text
Agent 调用 -> 中文 prompt -> structured output validation -> AIJob trace

Planning Engine -> Strategy Detail explainability -> planner eval JSONL -> golden policy check
```

---

## 5. 后端设计

### 影响模块

- [ ] API
- [ ] Service
- [ ] Models
- [ ] Schemas
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

无。

### API 变更

无。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent
- [ ] 新增 Agent
- [x] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

- Agent 名称：Capture Parser、Task Breakdown、Strategy Explanation、Daily Planner、Daily Report、Insight Detail
- 输入对象：沿用现有 service context / fallback output
- 输出对象：沿用现有 Pydantic schema
- fallback 策略：不变，mock / fallback 仍为默认安全路径
- 是否需要用户确认：Capture Parser 仍进入 Inbox；Task Breakdown 仍是可编辑步骤；Strategy / Report / Insight 仍是只读解释或建议

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 6 个 prompt 文件均为中文产品边界和中文输出要求。
- [x] prompt registry 测试断言中文边界语句。
- [x] planner eval 所有 9 个 scenario 都要求 `score_explanation` 和 item-level score signals。
- [x] `scripts/check_planner_eval_policy.py` 默认读取 v4 baseline。

### 数据验收

- [ ] 无 DB 变更。

### 体验验收

- [x] AI 解释克制可信。
- [x] 核心流程不因 AI 失败阻塞。

---

## 8. 测试计划

### 单元测试

- [x] Agent prompt registry tests
- [x] Planning eval tests
- [x] Planner eval policy tests

### API 测试

- [ ] 无 API 变更。

### 集成测试

- [x] planner eval policy smoke
- [x] AI mainline smoke

### 手动验证

```text
1. 运行指定 Agent / planner eval 测试。
2. 运行全量 unittest。
3. 运行 compileall 和 git diff --check。
4. 运行 verify_local --planner-eval-policy。
5. 运行 verify_local --smoke ai-mainline。
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| prompt 语言变化导致真实 provider 输出风格变化 | 真实模型验收可能出现差异 | mock/fallback 默认不变，真实 provider 仍走验收流程 |
| eval policy v4 让旧 JSONL 不再直接通过 | 历史比较需要明确版本 | 保留历史迭代文档，当前 baseline README 指向 v4 |
| 中文 prompt 中仍保留 schema 字段英文 | 可能显得中英混合 | 字段名必须与 structured output schema 对齐，说明文字使用中文 |

### 关键取舍

- 保留 prompt version 名称，不引入 v2 prompt key；本轮是语言和边界表达迁移，不改变 schema 或 agent contract。
- 将 explainability 作为 planner eval 的硬验收字段，而不是只在 Strategy Detail API 测试里覆盖。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | Prompt 统一改为中文 | Chronos 产品语气和主要用户语境更适合中文表达 | 测试断言同步改为中文边界 |
| 2026-05-17 | planner eval 升级为 v4 | explainability 已成为 Today trust 的核心部分 | policy manifest 和默认路径同步升级 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 中文化 Agent prompt | `app/ai/prompts/*/*.md` | 6 个已有 Agent |
| 2026-05-17 | 增加 explainability eval 断言 | `scripts/evaluate_planning_engine.py` | 9 个 scenario |
| 2026-05-17 | 升级 baseline policy | `docs/planner-eval-baselines/p2-planning-engine-eval-v4.json` | 默认 policy 指向 v4 |
| 2026-05-17 | 更新测试 | `tests/test_*agent.py`、`tests/test_planning_engine_evaluation.py`、`tests/test_planner_eval_policy.py` | prompt / eval / policy |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_capture_parser_agent tests.test_task_breakdown_agent tests.test_strategy_explanation_agent tests.test_daily_planner_agent tests.test_daily_report_agent tests.test_insight_detail_agent tests.test_planning_engine_evaluation tests.test_planner_eval_policy tests.test_llm_acceptance_record_generator`
- [x] `uv run python -m unittest discover -s tests`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`
- [x] `uv run python scripts/verify_local.py --planner-eval-policy`
- [x] `uv run python scripts/verify_local.py --smoke ai-mainline`

### 未验证

- [ ] 真实 LLM provider 验收未跑，本轮只确认 mock / fallback 默认主线。

### 已知问题

- 暂无。

---

## 13. 后续迭代建议

- 做第 9 项：生产级 auth / permission boundary，把当前 `X-User-Id` dev auth 和真实认证边界拆清楚。
- 后续真实 provider 验收时，用 v4 policy 作为 explainability baseline。

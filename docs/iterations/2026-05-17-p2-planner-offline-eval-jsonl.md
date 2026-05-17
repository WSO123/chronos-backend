# Iteration: P2 Planner Offline Eval JSONL

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 `scripts/evaluate_planning_engine.py` 增加可选 JSONL 输出，把 Planning Engine 固定场景评估结果沉淀为可追踪记录，用于后续比较不同 provider、prompt 和调度策略。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Planning Engine Evaluation v1](./2026-05-17-p2-planning-engine-evaluation-v1.md)
- [x] [P2 Provider Usage Metadata](./2026-05-17-p2-provider-usage-metadata.md)

### 背景

Chronos 的核心竞争力是 AI 编排质量。当前 Planning Engine 已有固定场景评估，但结果只打印到终端，难以长期保存，也不方便比较不同 provider、prompt 或调度参数调整后的差异。

本轮将评估结果输出成 JSONL，但保持默认行为不变：不传 `--jsonl-output` 时仍只打印 JSON，不写文件，不影响 `verify_local.py`。

### 目标

- 为评估脚本增加 `run_id` 和 `evaluator_version`。
- 增加 `--jsonl-output` 参数，输出离线评估记录。
- 增加 `--append` 参数，支持追加多次评估。
- JSONL 输出包含 run summary 和每个 scenario 的 scenario result。
- scenario details 增加 AIJob trace：provider、model、prompt_version、prompt_checksum、latency、usage。
- 保持默认评估命令和 `verify_local.py --planner-eval` 行为不变。
- 补测试覆盖函数输出、JSONL 写入和 CLI 写入。

### 非目标

- 不接真实 provider 自动评估。
- 不新增数据库表保存评估结果。
- 不做可视化报表。
- 不改变 Planning Engine 评分逻辑。
- 不把评估 trace 暴露到 Today / Strategy Detail 用户体验里。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> AIJob trace -> Offline Eval
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

本轮是开发者评估工具，不进入用户主路径。它服务 Chronos 的“可信”：AI 编排每次调整都应该能被固定场景回归，而不是只凭主观感觉判断。

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
| Run metadata | `run_id`、`evaluator_version` | Must | 支持比较 |
| JSONL output | `--jsonl-output <path>` | Must | 默认不写文件 |
| Append mode | `--append` | Should | 多次实验追加 |
| Scenario trace | 输出 scenario details 和 AIJob trace | Must | provider / prompt 比较 |
| CLI test | 覆盖脚本参数写文件 | Must | 防回归 |

### 用户故事

```text
作为后端开发者，
我希望每次 planner 评估都能输出可保存的 JSONL 记录，
以便后续比较不同 provider、prompt 和策略参数的质量差异。
```

```text
作为系统模块，
我希望评估记录包含 AIJob trace，
以便评估结果能和 provider、model、prompt_version、usage 对齐。
```

```text
作为 Chronos 用户，
我希望 AI 编排能力迭代时有稳定回归机制，
以便 Today 的行动顺序不会因为模型或策略调整而悄悄退化。
```

### 主要流程

```text
uv run python scripts/evaluate_planning_engine.py --jsonl-output /tmp/chronos-planner-eval.jsonl
-> run deterministic scenarios
-> collect Today / Strategy / AIJob trace
-> print summary JSON
-> write run_summary + scenario_result JSONL records
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

无。

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
- 输入对象：既有 Planning Engine deterministic scenarios
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

## 7. JSONL 记录结构

Run summary：

```json
{
  "run_id": "uuid",
  "evaluator_version": "p2-planning-engine-eval-v2",
  "record_type": "run_summary",
  "status": "ok",
  "scenario_count": 7,
  "passed_count": 7,
  "failed_count": 0
}
```

Scenario result：

```json
{
  "run_id": "uuid",
  "evaluator_version": "p2-planning-engine-eval-v2",
  "record_type": "scenario_result",
  "scenario_name": "capacity_rollover",
  "passed": true,
  "failures": [],
  "details": {
    "capacity_status": "within_capacity",
    "planner_agent_provider": "mock",
    "planner_agent_model": "structured-mock-v1",
    "planner_agent_prompt_version": "p2-daily-planner-agent-v1",
    "item_signals": [
      {
        "title": "Protected deep work",
        "section": "pinned",
        "total_score": 52
      }
    ],
    "planner_agent_usage": {
      "input_tokens": null,
      "output_tokens": null,
      "total_tokens": null,
      "cost_usd": null
    }
  }
}
```

---

## 8. 验收标准

### 功能验收

- [x] 默认评估仍打印 JSON 并返回原有 pass/fail。
- [x] `run_evaluation(run_id=...)` 返回稳定 run id 和 evaluator version。
- [x] `--jsonl-output` 写出 1 条 run summary 和 7 条 scenario result。
- [x] JSONL scenario result 包含 planner provider / model / prompt / usage trace。
- [x] `--append` 支持后续追加，不影响默认路径。

### 数据验收

- [x] 不新增数据库表。
- [x] 不写开发数据库。
- [x] 测试使用测试数据库和临时目录。

### 体验验收

- [x] 用户主路径无变化。
- [x] AI trace 只进入离线评估文件。
- [x] Today 和 Strategy Detail 不增加技术噪音。

---

## 9. 测试计划

### 单元测试

- [x] 固定场景仍通过。
- [x] JSONL writer 输出记录数和字段正确。
- [x] CLI 可写 JSONL 文件。

### API 测试

- [ ] 本轮不涉及 API。

### 集成测试

- [x] `verify_local.py --planner-eval --all-smoke`

### 手动验证

```bash
uv run python -m unittest tests.test_planning_engine_evaluation
uv run python scripts/evaluate_planning_engine.py --run-id manual-jsonl --jsonl-output /tmp/chronos-planner-eval.jsonl
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 10. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| JSONL 输出污染 repo | 产生无意义文件 | 文档示例使用 `/tmp`，默认不写文件 |
| 评估文件暴露技术细节 | 用户体验变复杂 | 只作为开发者工具，不进入 UI |
| 后续真实 provider 评估成本不可控 | 费用风险 | 本轮不自动调用真实 provider |

### 关键取舍

- 取舍 1：输出 JSONL 文件而不是新增数据库表，保持离线评估轻量。
- 取舍 2：默认命令不写文件，避免本地验证产生副作用。
- 取舍 3：AIJob trace 从数据库读取，只进入评估详情，不扩大 Strategy factors。

---

## 11. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | JSONL 默认关闭 | 避免 verify_local 产生文件副作用 | 需要显式传 `--jsonl-output` |
| 2026-05-17 | 输出 run summary + scenario result | 便于按 run 或按场景聚合 | 当前 7 场景输出 8 行 |
| 2026-05-17 | 从 AIJob 读取 planner trace | 保持 Strategy Detail 轻量 | 评估文件仍可比较 provider / prompt |

---

## 12. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 增加 JSONL CLI 参数和 writer | `scripts/evaluate_planning_engine.py` | `--jsonl-output`, `--append`, `--run-id` |
| 2026-05-17 | 评估详情补 AIJob trace | `scripts/evaluate_planning_engine.py` | provider / prompt / usage |
| 2026-05-17 | 补测试 | `tests/test_planning_engine_evaluation.py` | function + writer + CLI |
| 2026-05-17 | 更新文档 | README / LLM / guidelines | JSONL 用法 |

---

## 13. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_planning_engine_evaluation`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id manual-jsonl --jsonl-output /tmp/chronos-planner-eval.jsonl`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未接真实 provider 自动评估。

### 已知问题

- JSONL 目前覆盖 7 个 deterministic scenarios，仍不是完整 planner quality benchmark。

---

## 14. 后续迭代建议

1. 增加对比脚本，读取多份 JSONL 并输出 provider / prompt 差异摘要。
2. 增加真实 provider 手动验收记录模板，记录 model、usage、prompt checksum 和结论。
3. 继续扩展真实日常任务组合场景，例如多 Goal 竞争、超期目标恢复、低价值琐事挤压。

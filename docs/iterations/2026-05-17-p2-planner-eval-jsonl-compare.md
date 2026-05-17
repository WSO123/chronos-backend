# Iteration: P2 Planner Eval JSONL Compare

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 Planning Engine eval JSONL 对比工具，让 provider / prompt / 权重调整前后的编排差异可以被结构化追踪，而不是靠人工肉眼扫 JSONL。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Planner Offline Eval JSONL](./2026-05-17-p2-planner-offline-eval-jsonl.md)
- [x] [P2 Planner Eval Scenario Expansion](./2026-05-17-p2-planner-eval-scenario-expansion.md)

### 背景

上一轮已把 Planning Engine eval 扩展到 7 个核心场景，并在 JSONL details 中输出 `item_signals`。这让结果可沉淀，但还缺一个稳定的比较入口：后续接真实 provider、改 prompt、改评分权重时，需要快速判断候选 run 是否退化，以及退化来自通过状态、排序、容量还是具体 item signal。

本轮只增加离线 compare script，不改变线上 Planning Engine、Daily Planner Agent 或 Today 行为。

### 目标

- 增加 `scripts/compare_planner_eval_jsonl.py`。
- 支持读取两份 JSONL，并默认选择文件中最新 `run_id`。
- 支持通过 `--baseline-run-id` / `--candidate-run-id` 指定 run。
- 输出 missing / added / regression / improvement / scenario diff。
- 比较核心 details 字段和 `item_signals`。
- 提供 `--fail-on-regression` 作为显式手动 gate。
- 补充 README、工程规范和 LLM 架构文档。

### 非目标

- 不把 compare 纳入默认 `verify_local`。
- 不自动调用真实 LLM provider。
- 不新增数据库表。
- 不改变 planner 评分公式。
- 不新增线上 API。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Offline Eval -> Compare
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

本轮增强的是后台可信度工具。用户不会在 Today 里看到更多控制项，但团队可以更稳地维护“今天先做什么”的编排质量。复杂度留在离线工具里，用户可见部分继续保持清晰、克制、可行动。

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
| JSONL run loader | 从 JSONL 中按 `run_id` 还原 summary 和 scenarios | Must | 默认最新 run |
| Scenario comparison | 对比 missing / added / passed 变化 | Must | 识别 regression |
| Detail diff | 对比排序、容量、risk、provider、prompt version / checksum、fallback 等核心字段 | Must | 用于排障 |
| Item signal diff | 对比 `section`、`total_score`、goal value / goal urgency / behavior / dependency / preference score | Must | 定位评分信号变化 |
| CLI gate | `--fail-on-regression` 时 regression 返回 exit code 1 | Should | 默认不阻塞 |

### 用户故事

```text
作为 Chronos 用户，
我希望系统升级 AI 编排能力时不会悄悄降低 Today 的可执行性，
以便我继续信任它每天给出的执行顺序。
```

```text
作为后端开发者，
我希望能比较两次 planner eval JSONL，
以便接真实 provider、改 prompt 或调权重后快速发现编排退化。
```

```text
作为系统模块，
我希望对比结果能指出 scenario、核心字段和 item signal 的差异，
以便后续自动化评估可以建立在结构化结果上。
```

### 主要流程

```text
run baseline planner eval
-> run candidate planner eval
-> compare JSONL by run_id
-> report status and scenario diffs
-> optionally fail on regression
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
- 输入对象：既有 planner eval JSONL 输出
- 输出对象：对比报告 JSON
- Pydantic schema：无，本轮为离线 CLI JSON 输出
- fallback 策略：无线上影响；读取失败时 CLI 返回 `status=failed` 和 exit code 2
- 是否需要用户确认：不需要，本轮不调用真实 provider，不写业务数据

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] identical baseline / candidate 输出 `status=ok`。
- [x] candidate 从 passed 变 failed 时输出 `status=regressed`。
- [x] candidate 缺少 baseline scenario 时计为 regression。
- [x] candidate 新增 scenario 或 field diff 时输出 `status=changed`。
- [x] 支持 appended JSONL 默认选择最新 run。
- [x] `--fail-on-regression` 只在 regression 时 exit code 1。

### 数据验收

- [x] 不读写数据库。
- [x] 不创建 migration。
- [x] 不调用外部 LLM。
- [x] 输出 JSON 可被后续脚本消费。

### 体验验收

- [x] Today 用户界面无变化。
- [x] Strategy Detail 不变成评估控制台。
- [x] 默认 compare 只报告，不强制阻断开发。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_planner_eval_compare`

### API 测试

- [ ] 本轮不涉及 API。

### 集成测试

- [x] `scripts/evaluate_planning_engine.py` 生成 baseline / candidate JSONL。
- [x] `scripts/compare_planner_eval_jsonl.py` 对比真实 eval JSONL 输出。
- [x] `scripts/verify_local.py --planner-eval --all-smoke`。

### 手动验证

```bash
uv run python -m unittest tests.test_planner_eval_compare
uv run python scripts/evaluate_planning_engine.py --run-id compare-baseline --jsonl-output /tmp/chronos-planner-compare-baseline.jsonl
uv run python scripts/evaluate_planning_engine.py --run-id compare-candidate --jsonl-output /tmp/chronos-planner-compare-candidate.jsonl
uv run python scripts/compare_planner_eval_jsonl.py /tmp/chronos-planner-compare-baseline.jsonl /tmp/chronos-planner-compare-candidate.jsonl
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 对比字段过多 | 正常调整产生噪音 | 只比较核心 details 和 item signals |
| 默认 gate 阻塞开发 | 本地迭代变重 | 默认只报告，显式 `--fail-on-regression` 才失败 |
| appended JSONL 中有多个 run | 误读旧结果 | 默认选择最新 run，同时支持显式 run id |

### 关键取舍

- 取舍 1：compare 输出 JSON，不做人类化长报告，方便后续自动化消费。
- 取舍 2：missing scenario 视为 regression，added scenario 视为 changed。
- 取舍 3：不纳入默认 `verify_local`，避免把离线评估工具变成日常开发负担。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 默认选择最新 run | JSONL 可能追加多次运行 | 减少 CLI 参数负担 |
| 2026-05-17 | `--fail-on-regression` 作为 opt-in | 避免默认流程过重 | 可用于手动 gate |
| 2026-05-17 | 比较 `item_signals` | 需要定位排序变化原因 | 输出更适合排障 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 compare script | `scripts/compare_planner_eval_jsonl.py` | JSONL run diff |
| 2026-05-17 | 新增 compare tests | `tests/test_planner_eval_compare.py` | 4 个核心场景 |
| 2026-05-17 | 更新文档 | README / Engineering / LLM / iteration docs | 使用方式和边界 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_planner_eval_compare`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id compare-baseline --jsonl-output /tmp/chronos-planner-compare-baseline.jsonl`
- [x] `uv run python scripts/evaluate_planning_engine.py --run-id compare-candidate --jsonl-output /tmp/chronos-planner-compare-candidate.jsonl`
- [x] `uv run python scripts/compare_planner_eval_jsonl.py /tmp/chronos-planner-compare-baseline.jsonl /tmp/chronos-planner-compare-candidate.jsonl`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未用真实 provider 输出做实际差异对比。

### 已知问题

- compare 只判断结构化 scenario 结果，不覆盖完整真实用户任务分布。
- 多 Goal 竞争 / 超期目标恢复场景已在后续 v3 evaluator 迭代补充，但仍需要更多真实分布样本。

---

## 13. 后续迭代建议

1. 已在后续迭代补充真实 provider 手动验收记录模板，记录 model、usage、prompt checksum、JSONL compare 结果和结论。
2. 已在后续迭代补充多 Goal 竞争 / 超期目标恢复的 planner eval 场景。
3. 将 compare 输出接入后续手动发布 checklist。

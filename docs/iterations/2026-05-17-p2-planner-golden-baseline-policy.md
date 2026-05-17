# Iteration: P2 Planner Golden Baseline Policy

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

为 Planning Engine evaluator 增加 golden baseline policy，让后续 planner 权重、prompt、真实 provider 或 fallback 改动能用统一标准判断：哪些是可记录的 changed，哪些是必须阻断的 regression。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Planner Eval Golden Baseline](../planner-eval-baselines/README.md)
- [x] [P2 Planner Goal-Aware Evaluation](./2026-05-17-p2-planner-goal-aware-eval.md)

### 背景

前序迭代已经让 planner eval 覆盖容量、Energy、依赖、用户修正、行为反馈、多 Goal 竞争和超期 Goal 恢复，也提供了 JSONL compare。缺口在于：compare 能说“变了”，但还没有一个明确的 golden baseline policy 告诉开发者“这次变化是否可以继续”。

Chronos 的核心承诺是“把今天安排成真正做得出来的一天”。因此 planner 质量不能只靠接口可用性判断，而要保护固定产品行为：高价值任务保护、容量不失控、低精力减负、依赖顺序、用户修正权、行为反馈学习、Goal 价值保护和超期 Goal 恢复。

### 目标

- 增加 machine-readable planner eval policy manifest。
- 增加 `scripts/check_planner_eval_policy.py`，检查 eval JSONL 是否满足 baseline。
- 明确 `ok` / `changed` / `regressed` 的含义。
- `regressed` 默认返回非 0，`changed` 可通过 `--fail-on-changed` 作为更严格 gate。
- `verify_local.py` 增加可选 `--planner-eval-policy`。
- 更新 README、工程规范、LLM 架构和真实 provider 验收模板。

### 非目标

- 不把 policy check 纳入默认 CI。
- 不保存真实 provider 原始响应。
- 不把 eval JSONL 固定输出提交到仓库。
- 不新增数据库表或 API。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Offline Eval -> Golden Policy -> Real Provider Acceptance
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [x] Goals
- [x] AI Agent

### 产品人格

本轮不增加用户可见复杂度。它把 planner 质量判断放在开发和验收层，保持产品前台轻盈，后台判断更可信。

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
| Golden policy manifest | 固定 evaluator version、required scenarios、required signals | Must | JSON |
| Policy checker | 读取 eval JSONL 并输出 policy status | Must | CLI + pure function |
| Regression classification | 缺失场景、失败场景、字段丢失计为 regression | Must | 默认非 0 |
| Changed classification | evaluator version 或额外 scenario 变化计为 changed | Must | 默认不阻断 |
| Strict gate | `--fail-on-changed` 可阻断 changed | Should | 发布前可用 |
| Verify integration | `verify_local.py --planner-eval-policy` | Should | 可选 |
| Provider acceptance docs | 真实 provider 验收加入 policy check | Should | 手动流程 |

### 用户故事

```text
作为 Chronos 用户，
我希望系统每次升级后仍然保护重要目标和可执行的一天，
以便 AI 编排不会因为内部改动而变得不可预测。
```

```text
作为后端开发者，
我希望 planner eval 有明确 baseline，
以便调权重、改 prompt 或接 provider 时能判断变化是否可接受。
```

```text
作为验收负责人，
我希望真实 provider 验收记录能引用 policy check，
以便结论不只停留在主观观察。
```

### 主要流程

```text
run planner eval JSONL
-> load golden policy
-> verify evaluator version / run status / scenario set
-> verify required scenario pass status
-> verify required detail and item signal fields
-> output ok / changed / regressed
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
- [x] Scripts
- [x] Docs

### 数据模型变更

无。

### Policy Manifest

位置：

```text
docs/planner-eval-baselines/p2-planning-engine-eval-v3.json
```

核心字段：

- `policy_version`
- `evaluator_version`
- `required_run_status`
- `exact_scenario_set`
- `required_detail_fields`
- `required_item_signal_fields`
- `required_scenarios`
- `regression_rules`
- `changed_rules`

### Policy Checker

位置：

```text
scripts/check_planner_eval_policy.py
```

输出状态：

- `ok`：满足当前 baseline。
- `changed`：版本或场景集合发生变化，需要记录或更新 policy。
- `regressed`：必需行为失败，默认退出码为 1。

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

- Agent 名称：Planning Engine v1 / Daily Planner Agent shell
- 输入对象：不变
- 输出对象：不变
- Pydantic schema：不变
- fallback 策略：不变
- 是否需要用户确认：不涉及用户确认

### LLM 安全边界

- [x] policy check 不调用真实 provider
- [x] policy manifest 不保存真实用户输入
- [x] policy manifest 不保存 provider 原始响应
- [x] 真实 provider 验收仍必须显式手动触发

---

## 7. 验收标准

### 功能验收

- [x] policy manifest 覆盖 `p2-planning-engine-eval-v3` 的 9 个必需场景。
- [x] checker 能识别 matching run 为 `ok`。
- [x] checker 能识别 missing scenario / failed scenario 为 `regressed`。
- [x] checker 能识别 extra scenario 为 `changed`。
- [x] checker 能识别 item signal 字段丢失为 `regressed`。
- [x] `verify_local.py --planner-eval-policy` 可生成 JSONL 并检查 policy。

### 数据验收

- [x] 不新增 migration。
- [x] 不写真实业务数据。
- [x] 不提交 eval JSONL 输出。

### 体验验收

- [x] 不改变 Today 首屏。
- [x] 不增加用户可见解释负担。
- [x] 开发者验收标准更清晰。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_planner_eval_policy`
- [x] `tests.test_planner_eval_compare`
- [x] `tests.test_planning_engine_evaluation`

### 集成测试

- [x] `scripts/verify_local.py --planner-eval-policy`
- [x] `scripts/verify_local.py --planner-eval --all-smoke`

### 手动验证

```bash
uv run python -m unittest tests.test_planner_eval_policy tests.test_planner_eval_compare tests.test_planning_engine_evaluation
uv run python scripts/verify_local.py --planner-eval-policy
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| policy 过严 | 每次加场景都需要更新 policy | 将 extra scenario 归类为 changed，默认不阻断 |
| policy 过松 | 真实退化被误判为可接受变化 | missing / failed / field missing 都归为 regression |
| JSONL 输出含临时数据 | 仓库污染 | eval JSONL 只写 `/tmp`，不提交 |

### 关键取舍

- 取舍 1：policy check 不进默认 CI，保持日常开发轻。
- 取舍 2：`changed` 默认不失败，但验收时必须记录。
- 取舍 3：policy manifest 记录规则，不记录完整 golden JSONL。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 使用 JSON manifest | 既能人工阅读，也能脚本检查 | policy 可追踪 |
| 2026-05-17 | 不提交完整 eval JSONL | 避免 UUID / 临时 run 噪声 | baseline 更稳定 |
| 2026-05-17 | changed 默认不阻断 | 支持迭代中显式记录变化 | 发布前可用 `--fail-on-changed` |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 policy manifest | `docs/planner-eval-baselines/p2-planning-engine-eval-v3.json` | 9 scenarios |
| 2026-05-17 | 新增 policy README | `docs/planner-eval-baselines/README.md` | 判定标准 |
| 2026-05-17 | 新增 checker | `scripts/check_planner_eval_policy.py` | JSONL policy check |
| 2026-05-17 | verify optional gate | `scripts/verify_local.py` | `--planner-eval-policy` |
| 2026-05-17 | 新增 tests | `tests/test_planner_eval_policy.py` | unit + CLI |
| 2026-05-17 | 更新文档 | README / Engineering / LLM / Acceptance | 使用入口 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_planner_eval_policy tests.test_planner_eval_compare tests.test_planning_engine_evaluation`
- [x] `uv run python scripts/verify_local.py --planner-eval-policy`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未用真实 provider candidate JSONL 做 policy check。

### 已知问题

- policy 只覆盖固定 evaluator 场景，不代表完整真实用户任务分布。
- policy 当前只检查结构和 pass/fail，不做数值阈值比较；数值变化仍由 compare 脚本和验收记录承接。

---

## 13. 后续迭代建议

1. 增加验收记录生成脚本，从 smoke JSON、compare JSON 和 policy check JSON 自动生成 Markdown 草稿。
2. 为 Today Strategy Detail 增加更清晰的 goal-aware explanation 文案，但仍不进入 Today 首屏。
3. 增加 planner eval 数值阈值 policy，例如 selected minutes、over capacity 和关键 score signal 的允许范围。

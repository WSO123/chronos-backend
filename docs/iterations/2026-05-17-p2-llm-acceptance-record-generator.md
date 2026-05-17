# Iteration: P2 LLM Acceptance Record Generator

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 LLM provider 验收记录生成脚本，把真实 provider smoke、planner eval compare 和 golden policy check 的 JSON 输出汇总为 Markdown 草稿，减少验收结果散落在终端和聊天里的风险。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [LLM Provider Acceptance Template](../llm-provider-acceptance/TEMPLATE.md)
- [x] [Planner Eval Golden Baseline](../planner-eval-baselines/README.md)
- [x] [P2 Planner Golden Baseline Policy](./2026-05-17-p2-planner-golden-baseline-policy.md)

### 背景

真实 provider 接入链路已经具备三类验收输入：

- `scripts/smoke_llm_provider.py`：确认 provider 能返回 Daily Planner structured output。
- `scripts/compare_planner_eval_jsonl.py`：比较 planner eval baseline / candidate。
- `scripts/check_planner_eval_policy.py`：确认 candidate 满足 golden baseline policy。

缺口在于：每次验收后仍需要手动把 JSON 摘要搬进 Markdown，容易漏掉 provider / model、prompt checksum、usage、compare status、policy status 或安全边界说明。本轮补一个只读 JSON 的草稿生成器。

### 目标

- 新增 `scripts/generate_llm_acceptance_record.py`。
- 支持读取 smoke / compare / policy 三份 JSON。
- 支持输出 Markdown 到 stdout 或指定文件。
- 自动推断 `Accepted` / `Accepted with Notes` / `Rejected` / `Blocked` 草稿状态。
- 默认脱敏 `provider_response_id`，不输出 API key 或 provider 原始响应。
- 更新 README、工程规范、LLM 架构和验收模板。

### 非目标

- 不调用真实 provider。
- 不替代人工 review。
- 不保存完整 provider 原始响应。
- 不新增数据库表、API 或 worker。

---

## 3. 产品约束对齐

### 核心路径

```text
Daily Planner Agent -> Smoke -> Planner Eval Compare -> Policy Check -> Acceptance Record
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

本轮是后台工程质量工具，不增加用户可见复杂度。它让 AI 接入更可信、更可追踪，避免“聪明”越过验收边界。

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
| JSON input loader | 读取 smoke / compare / policy JSON | Must | 支持带命令前缀的输出文件 |
| Markdown generator | 生成验收记录草稿 | Must | stdout 或 `--output` |
| Conclusion inference | 自动推断 Accepted / Notes / Rejected / Blocked | Must | 仍需人工 review |
| Sensitive redaction | 默认隐藏 provider response id | Must | 不记录 API key |
| CLI metadata | 支持 provider / model / purpose / commit / iteration | Should | 便于归档 |
| Tests | 覆盖状态推断、脱敏、CLI 输出 | Must | 单元测试 |

### 用户故事

```text
作为后端开发者，
我希望真实 provider 验收记录能从 JSON 输出自动生成，
以便每次接入或调参后都能留下完整、可追踪的证据。
```

```text
作为验收负责人，
我希望脚本能自动标出 compare / policy 的 regression 或 changed，
以便我知道哪些地方必须人工判断。
```

```text
作为 Chronos 用户的代理人，
我希望 AI provider 接入不会绕过安全边界，
以便 Today 编排仍然可信、可解释、可回退。
```

### 主要流程

```text
smoke JSON + compare JSON + policy JSON
-> parse payloads
-> infer draft conclusion
-> redact provider response id
-> render Markdown acceptance draft
-> human review
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

### CLI 设计

```bash
uv run python scripts/generate_llm_acceptance_record.py \
  --smoke-json /tmp/chronos-llm-smoke.json \
  --compare-json /tmp/chronos-planner-compare.json \
  --policy-json /tmp/chronos-planner-policy.json \
  --provider openai \
  --model gpt-4.1-mini \
  --purpose daily-planner-smoke \
  --output docs/llm-provider-acceptance/YYYY-MM-DD-openai-gpt-4-1-mini-daily-planner-smoke.md
```

### 状态推断

- `Blocked`：smoke 是 `skipped`，不足以验收真实 provider。
- `Rejected`：smoke 非 `ok`，或 compare / policy 出现 regression。
- `Accepted with Notes`：smoke ok 且无 regression，但 compare / policy 为 changed。
- `Accepted`：smoke ok、compare ok、policy ok。

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
- 输入对象：已生成的 smoke / compare / policy JSON
- 输出对象：Markdown 验收草稿
- Pydantic schema：不变
- fallback 策略：不变
- 是否需要用户确认：验收草稿必须人工 review

### LLM 安全边界

- [x] 生成器不调用真实 provider。
- [x] 生成器不读取 API key。
- [x] 生成器默认隐藏 provider response id。
- [x] 生成器不保存真实用户输入或 provider 原始响应。

---

## 7. 验收标准

### 功能验收

- [x] clean smoke / compare / policy 会生成 `Accepted` 草稿。
- [x] changed compare / policy 会生成 `Accepted with Notes` 草稿。
- [x] compare regression 会生成 `Rejected` 草稿。
- [x] skipped smoke 会生成 `Blocked` 草稿。
- [x] provider response id 不以原文出现在 Markdown。
- [x] CLI 可把 Markdown 写入指定路径。

### 数据验收

- [x] 不新增 migration。
- [x] 不写业务表。
- [x] 不调用真实 provider。
- [x] 不提交生成的验收记录实例。

### 体验验收

- [x] 文档说明脚本只生成草稿，不代表免 review。
- [x] 真实 provider 验收模板保留人工判断空间。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_llm_acceptance_record_generator`
- [x] `tests.test_llm_provider_acceptance_template`
- [x] `tests.test_planner_eval_policy`
- [x] `tests.test_planner_eval_compare`

### 集成测试

- [x] `scripts/verify_local.py --planner-eval-policy`
- [x] `scripts/verify_local.py --planner-eval --all-smoke`

### 手动验证

```bash
uv run python -m unittest tests.test_llm_acceptance_record_generator tests.test_llm_provider_acceptance_template tests.test_planner_eval_policy tests.test_planner_eval_compare
uv run python scripts/verify_local.py --planner-eval-policy
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 自动结论被误当最终结论 | 跳过人工判断 | 文档明确为 Draft，模板保留 Review 区 |
| 输出包含敏感标识 | 泄露 provider trace id | 默认脱敏 response id |
| JSON 输入格式有命令前缀 | 解析失败 | loader 支持从文本中提取第一个 JSON object |

### 关键取舍

- 取舍 1：脚本只生成草稿，不做真实 provider 调用。
- 取舍 2：默认脱敏 response id，宁可少记录一点也不泄露。
- 取舍 3：不提交生成实例，避免临时验收噪声进入仓库。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 使用 JSON 输入而不是直接跑命令 | 避免脚本隐式调用真实 provider | 更安全、更可复现 |
| 2026-05-17 | 自动结论只作为 Draft | 保留人工判断权 | 避免过度自动化 |
| 2026-05-17 | 默认脱敏 provider response id | 降低外部标识泄露风险 | 需要时人工补充安全摘要 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增生成器 | `scripts/generate_llm_acceptance_record.py` | JSON -> Markdown |
| 2026-05-17 | 新增测试 | `tests/test_llm_acceptance_record_generator.py` | 6 cases |
| 2026-05-17 | 更新验收模板 | `docs/llm-provider-acceptance/TEMPLATE.md` | 生成草稿入口 |
| 2026-05-17 | 更新工程文档 | README / Guidelines / LLM Architecture | 使用说明 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_llm_acceptance_record_generator tests.test_llm_provider_acceptance_template tests.test_planner_eval_policy tests.test_planner_eval_compare`
- [x] `uv run python scripts/verify_local.py --planner-eval-policy`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未用真实 provider smoke 输出生成正式验收记录。

### 已知问题

- fallback 检查已在后续 [P2 Daily Planner Fallback Smoke Evidence](./2026-05-17-p2-daily-planner-fallback-smoke.md) 中改为结构化 smoke JSON。

---

## 13. 后续迭代建议

1. 已在后续迭代补充真实 provider smoke 的 task id preservation 明细，减少验收记录中的人工核对项。
2. 为 Today Strategy Detail 增加更清晰的 goal-aware explanation 文案，但仍不进入 Today 首屏。
3. 增加 planner eval 数值阈值 policy，例如 selected minutes、over capacity 和关键 score signal 的允许范围。

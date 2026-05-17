# Iteration: P2 LLM Acceptance Dry Run

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 LLM provider acceptance dry-run 文档和生成脚本，用 synthetic JSON 演练 `provider smoke -> fallback smoke -> planner compare -> golden policy -> acceptance record` 的完整链路。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [LLM Provider Acceptance README](../llm-provider-acceptance/README.md)
- [x] [P2 Daily Planner Fallback Smoke Evidence](./2026-05-17-p2-daily-planner-fallback-smoke.md)

### 背景

真实 provider 验收目前已经具备 provider smoke、fallback smoke、planner eval compare、golden policy check 和 acceptance generator。但这些能力分散在多个命令里，第一次接真实 provider 前，开发者仍需要理解四份 JSON 如何拼成最终验收草稿。

本轮增加 dry-run：不调用真实 provider，不需要 API key，只生成 synthetic JSON 和一份验收草稿，用来验证流程本身。

### 目标

- 新增 `scripts/generate_llm_acceptance_dry_run.py`。
- 新增 `docs/llm-provider-acceptance/DRY_RUN.md`。
- dry-run 生成四份 synthetic JSON：`smoke.json`、`fallback.json`、`compare.json`、`policy.json`。
- dry-run 生成一份 acceptance Markdown 草稿，预期状态为 `Accepted`。
- README / Engineering / LLM 架构文档增加 dry-run 入口。
- 补充测试，确保 dry-run payload、CLI 和文档入口可用。

### 非目标

- 不调用真实 LLM。
- 不替代真实 provider 验收。
- 不提交真实 provider 验收记录。
- 不改变 Planning Engine、Daily Planner Agent 或 fallback 行为。

---

## 3. 产品约束对齐

### 核心路径

```text
Synthetic JSON fixtures
-> acceptance generator
-> dry-run Markdown
-> developer understands real provider acceptance flow
```

- [ ] Capture
- [ ] Inbox
- [x] Today
- [ ] Task Detail
- [ ] Focus
- [ ] Report
- [ ] Me
- [ ] Goals
- [x] AI Agent

### 产品人格

这轮仍是后台可信度建设。它不增加用户侧复杂度，只让开发和验收流程更清澈：真实 provider 上线前，先用 dry-run 确认路径、证据和结论判断都能工作。

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
| Dry-run generator | 生成 synthetic JSON 和 acceptance Markdown | Must | 默认输出到 `/tmp` |
| Dry-run doc | 解释四份 JSON 的角色和真实 provider 替换方式 | Must | `DRY_RUN.md` |
| README entry | 开发入口加入 dry-run 命令 | Should | 可发现 |
| Engineering / LLM docs | 架构和规范同步 dry-run 入口 | Should | 防漂移 |
| Tests | 覆盖 payload、CLI、文档关键项 | Must | 不调用真实 provider |

### 用户故事

```text
作为后端开发者，
我希望在没有 API key 的情况下跑通 provider acceptance 流程，
以便接真实 provider 前先验证工具链和文档路径。
```

```text
作为验收负责人，
我希望看到四份 JSON 如何汇总成最终 Markdown，
以便知道每个证据项对应哪个安全边界。
```

```text
作为 Chronos 用户的代理人，
我希望 AI provider 上线前有可追踪验收流程，
以便“聪明”不会压过“可信”。
```

### 主要流程

```text
uv run python scripts/generate_llm_acceptance_dry_run.py --date 2026-05-17
-> write /tmp/chronos-llm-acceptance-dry-run/smoke.json
-> write /tmp/chronos-llm-acceptance-dry-run/fallback.json
-> write /tmp/chronos-llm-acceptance-dry-run/compare.json
-> write /tmp/chronos-llm-acceptance-dry-run/policy.json
-> write /tmp/chronos-llm-acceptance-dry-run/dry-run-openai-gpt-4-1-mini-daily-planner.md
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

### 输出文件

默认输出到：

```text
/tmp/chronos-llm-acceptance-dry-run/
```

不默认写入 repo，避免把 synthetic dry-run 误当成真实 provider 验收记录。

### 生成器 API

- `build_dry_run_payloads()`：生成四份 synthetic JSON payload。
- `generate_dry_run(json_dir, output, record_date)`：写出 JSON 和 Markdown。

---

## 6. AI / LLM 影响

### 是否涉及 AI

- [ ] 不涉及
- [x] 涉及已有 Agent 文档 / 验收流程
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### Agent 设计

- Agent 名称：Daily Planner Agent
- 输入对象：synthetic acceptance payloads
- 输出对象：acceptance dry-run Markdown
- Pydantic schema：不变
- fallback 策略：不变
- 是否需要用户确认：不涉及用户确认

### LLM 安全边界

- [x] 不调用真实 provider。
- [x] 不读取 API key。
- [x] 不使用真实用户输入。
- [x] provider response id 会被 acceptance generator 脱敏。
- [x] dry-run 明确标注不等于真实 provider accepted。

---

## 7. 验收标准

### 功能验收

- [x] dry-run 脚本能生成四份 JSON。
- [x] dry-run 脚本能生成 acceptance Markdown。
- [x] Markdown 预期状态为 `Accepted`。
- [x] Markdown 包含 fallback evidence。
- [x] Markdown 中 provider response id 被脱敏。
- [x] `DRY_RUN.md` 说明 dry-run 不证明真实 provider 可用。

### 数据验收

- [x] 不新增 migration。
- [x] 不写真实 provider 验收记录。
- [x] 默认输出到 `/tmp`。
- [x] 不提交 API key 或真实 provider 原始响应。

### 体验验收

- [x] 真实 provider 验收前有可重复演练入口。
- [x] 验收流程从散命令变成可理解链路。
- [x] 用户侧 Today / Focus / Task Detail 不受影响。

---

## 8. 测试与验证

### 单元测试

- [x] `tests.test_llm_acceptance_dry_run`
- [x] `tests.test_llm_acceptance_record_generator`
- [x] `tests.test_llm_provider_acceptance_template`

### 本地验证

- [x] `uv run python -m unittest tests.test_llm_acceptance_dry_run tests.test_llm_acceptance_record_generator tests.test_llm_provider_acceptance_template`
- [x] `uv run python scripts/generate_llm_acceptance_dry_run.py --date 2026-05-17`
- [x] `uv run python scripts/verify_local.py --planner-eval-policy`
- [x] `git diff --check`

---

## 9. 风险与边界

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| dry-run 被误解为真实 provider accepted | 错误上线判断 | 文档和生成内容明确标注 dry-run / no network |
| 默认输出污染 repo | 误提交 synthetic record | 默认写 `/tmp` |
| synthetic payload 与 generator 字段漂移 | dry-run 失效 | 增加测试覆盖 payload 和 CLI |

---

## 10. Review

### 自查结论

- 符合 Chronos AI provider 接入前的可信度建设方向。
- 不改变业务行为，只补齐验收流程可追踪性。
- dry-run 让后续真实 provider 验收更像工程流程，而不是临时手工操作。

### 后续建议

- 下一轮可以补齐真实 provider 验收的 “candidate eval JSONL 生成与 compare 命令顺序” 一键化，进一步降低手动操作错误。

---

## 11. 变更记录

| 日期 | 变更 | 文件 | 说明 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 dry-run generator | `scripts/generate_llm_acceptance_dry_run.py` | synthetic JSON -> acceptance Markdown |
| 2026-05-17 | 新增 dry-run 文档 | `docs/llm-provider-acceptance/DRY_RUN.md` | 四份 JSON 流程说明 |
| 2026-05-17 | 补测试 | `tests/test_llm_acceptance_dry_run.py` | payload / CLI / markdown |
| 2026-05-17 | 更新入口文档 | README / Engineering / LLM / Acceptance README | 可发现 |

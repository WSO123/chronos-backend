# Iteration: P2 Real Provider Acceptance Template

> 状态：Done
> 阶段：P2
> 创建日期：2026-05-17
> 负责人：Codex
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增真实 LLM provider 手动验收记录模板，把 model、usage、prompt checksum、JSONL compare、fallback 和最终结论沉淀为可追踪文档。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 Real LLM Provider Manual Smoke](./2026-05-17-p2-real-llm-smoke-script.md)
- [x] [P2 Planner Eval JSONL Compare](./2026-05-17-p2-planner-eval-jsonl-compare.md)

### 背景

真实 provider 接入链路已经具备安全 smoke、usage metadata、provider guardrails、planner eval JSONL 和 JSONL compare。缺口在于：真实 provider 每次手动验收后，如果没有标准记录，model、prompt checksum、usage、latency、compare 结论和风险判断容易散落在聊天或终端输出里。

本轮不调用真实 provider，只定义验收记录格式和使用规范，确保后续真实模型验证可追踪、可复查、可拒绝。

### 目标

- 新增 `docs/llm-provider-acceptance/README.md`。
- 新增 `docs/llm-provider-acceptance/TEMPLATE.md`。
- 模板覆盖配置、安全边界、smoke 输出、usage、prompt checksum、planner compare 和最终结论。
- 更新 README、工程规范、LLM 架构文档。
- 增加轻量测试，避免模板缺失关键字段。

### 非目标

- 不调用真实 LLM。
- 不新增 provider adapter。
- 不改变 `scripts/smoke_llm_provider.py`。
- 不改变 Planning Engine / Daily Planner Agent 行为。
- 不把真实 provider 验收加入默认 CI。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Provider Acceptance Record
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

本轮服务 Chronos 的“可信”：真实 provider 可以更聪明，但每次引入模型能力都必须有清楚、克制、可复查的记录。用户不需要看到这些复杂度，但系统团队必须能证明 AI 没有压过业务边界。

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
| Acceptance directory | `docs/llm-provider-acceptance/` | Must | 存放模板和记录 |
| README | 说明记录命名、安全边界和推荐命令 | Must | 不含密钥 |
| Template | 标准验收记录模板 | Must | 可复制 |
| Docs links | README / Engineering / LLM 架构入口 | Must | 后续可发现 |
| Template coverage test | 校验关键字段存在 | Should | 防止模板漂移 |

### 用户故事

```text
作为后端开发者，
我希望每次真实 LLM provider 验收都有统一记录模板，
以便后续比较 model、prompt、usage 和编排质量时有可靠证据。
```

```text
作为产品负责人，
我希望真实 provider 验收必须记录是否影响 Today 的可执行顺序和用户控制感，
以便 Chronos 不会因为“更聪明”而变得不可解释或不可控。
```

```text
作为系统模块，
我希望验收记录强制包含 fallback、schema、task id 和 JSONL compare 检查，
以便真实 provider 失败或退化时不阻塞核心闭环。
```

### 主要流程

```text
copy TEMPLATE.md
-> run default skipped smoke
-> run explicit real provider smoke
-> record provider / model / prompt checksum / usage
-> run planner eval JSONL compare
-> fill safety checklist
-> decide Accepted / Rejected / Blocked
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
- 输入对象：真实 provider smoke / planner eval compare 结果
- 输出对象：手动验收记录
- Pydantic schema：不变
- fallback 策略：不变
- 是否需要用户确认：真实 provider 调用必须由开发者显式执行，本轮不发请求

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

---

## 7. 验收标准

### 功能验收

- [x] 模板包含 provider、model、base URL、agent、prompt version、prompt checksum。
- [x] 模板包含默认 skipped smoke 和真实 provider smoke 命令。
- [x] 模板包含 usage、latency、provider response id。
- [x] 模板包含 planner eval JSONL compare。
- [x] 模板包含 safety checklist 和最终结论。

### 数据验收

- [x] 不新增 migration。
- [x] 不调用真实 provider。
- [x] 不写数据库。
- [x] 不提交 API key 或真实用户数据。

### 体验验收

- [x] 用户主路径无变化。
- [x] Today 不增加技术字段。
- [x] 真实 provider 复杂度保留在开发验收层。

---

## 8. 测试计划

### 单元测试

- [x] `tests.test_llm_provider_acceptance_template`

### API 测试

- [ ] 本轮不涉及 API。

### 集成测试

- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`

### 手动验证

```bash
uv run python -m unittest tests.test_llm_provider_acceptance_template
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 模板过重导致没人填 | 验收记录流于形式 | 只要求核心字段和结论，真实输出用摘要 |
| 记录误提交敏感信息 | 密钥或用户数据泄露 | README 和模板明确禁止，API key 只写 `<redacted>` |
| 验收记录与实际命令漂移 | 后续复查困难 | README / Engineering / LLM 架构统一入口 |

### 关键取舍

- 取舍 1：先做 Markdown 模板，不做数据库化验收记录。
- 取舍 2：记录 provider response id 摘要，而不是完整原始响应。
- 取舍 3：真实 provider 调用仍是手动显式动作，不进入默认验证链路。

---

## 10. 决策记录

| 日期 | 决策 | 原因 | 影响 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增 `docs/llm-provider-acceptance/` | 真实 provider 验收需要独立记录空间 | 后续记录可追踪 |
| 2026-05-17 | 模板强制记录 prompt checksum | prompt 漂移是 LLM 质量回归的重要来源 | 便于复查 |
| 2026-05-17 | 模板强制记录 JSONL compare | 真实 provider 不能只看 smoke 成功 | 能发现 planner 质量退化 |

---

## 11. 变更记录

| 日期 | 变更 | 文件 / 模块 | 备注 |
| --- | --- | --- | --- |
| 2026-05-17 | 新增验收目录说明 | `docs/llm-provider-acceptance/README.md` | 命名和安全边界 |
| 2026-05-17 | 新增验收模板 | `docs/llm-provider-acceptance/TEMPLATE.md` | 手动记录格式 |
| 2026-05-17 | 新增模板测试 | `tests/test_llm_provider_acceptance_template.py` | 关键字段覆盖 |
| 2026-05-17 | 更新文档入口 | README / Engineering / LLM / previous iteration | 可发现 |

---

## 12. 验证结果

### 已验证

- [x] `uv run python -m unittest tests.test_llm_provider_acceptance_template`
- [x] `uv run python scripts/verify_local.py --planner-eval --all-smoke`
- [x] `git diff --check`

### 未验证

- [ ] 未执行真实 provider smoke。
- [ ] 未产生真实 provider 验收实例记录。

### 已知问题

- 模板仍依赖人工填写，后续可以考虑由 smoke / compare JSON 自动生成记录草稿。

---

## 13. 后续迭代建议

1. 已在后续迭代补充多 Goal 竞争 / 超期目标恢复的 planner eval 场景。
2. 增加验收记录生成脚本，从 smoke JSON 和 compare JSON 自动生成 Markdown 草稿。
3. 将真实 provider 验收记录纳入发布 checklist。

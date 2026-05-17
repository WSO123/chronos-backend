# Iteration: P2 Real LLM Provider Manual Smoke

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增真实 LLM provider 手动 smoke 脚本，用于在显式开启真实 LLM、配置 API key 和传入 `--allow-real-llm` 时验证 OpenAI-compatible structured output；默认执行只返回 skipped，不发网络请求，不影响本地和 CI。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [P2 OpenAI-Compatible Provider Adapter](./2026-05-17-p2-openai-provider-adapter.md)
- [x] [P2 Provider Observability v1](./2026-05-17-p2-provider-observability.md)

### 背景

OpenAI-compatible provider adapter 已经存在，但缺少一个安全的手动验证入口。直接把真实 provider smoke 放进默认 `verify_local.py` 会带来网络、密钥、费用和 CI 稳定性风险；完全不提供 smoke，又会让真实 provider 接入只能靠临时脚本。

本轮提供一个“默认跳过、显式执行”的脚本，让真实 provider 验证变得可重复，同时不破坏默认开发体验。

### 目标

- 新增 `scripts/smoke_llm_provider.py`。
- 默认执行时返回 `status=skipped`，不发网络请求。
- 只有传 `--allow-real-llm` 时才可能调用真实 provider。
- `--allow-real-llm` 下必须满足：
  - `AI_ENABLE_REAL_LLM=true`
  - `LLM_PROVIDER=openai` 或 `openai-compatible`
  - `LLM_API_KEY` 非空
  - `LLM_MODEL` 不是 mock model
- 使用 Daily Planner Agent 和真实 provider 做 structured output smoke。
- 校验返回 task ids 不被 provider 改动。
- 测试覆盖默认 skip 和配置校验。

### 非目标

- 不在 CI 默认运行真实 provider smoke。
- 不提交任何 API key。
- 不新增真实网络单元测试。
- 不写数据库。
- 不改变 PlanningService 和 Today 行为。

---

## 3. 产品约束对齐

### 核心路径

```text
Today -> Strategy Detail -> Focus
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

真实 LLM smoke 是开发者工具，不进入用户路径。它服务 Chronos 的“可信”：验证 provider 是否能输出结构化建议，同时保留 Planning Engine 对任务集合和顺序的保护。

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
| Manual smoke script | `scripts/smoke_llm_provider.py` | Must | 默认 skipped |
| Safety flag | `--allow-real-llm` | Must | 防止误发请求 |
| Config validation | 检查 real LLM、provider、key、model | Must | 缺失即失败 |
| Structured output check | 调用 Daily Planner Agent 并校验 task ids | Must | 不写数据库 |
| Unit tests | 覆盖 skip 和校验逻辑 | Must | 不发网络 |

### 用户故事

```text
作为后端开发者，
我希望可以用一个安全脚本手动验证真实 LLM provider，
以便接入真实模型时不用临时拼脚本，也不会影响默认验证链路。
```

```text
作为系统模块，
我希望真实 provider smoke 仍校验 task ids 不被改变，
以便 LLM 只生成结构化建议，不破坏 Planning Engine 的保护边界。
```

### 主要流程

默认：

```text
uv run python scripts/smoke_llm_provider.py
-> status=skipped
-> no network
```

真实 smoke：

```text
AI_ENABLE_REAL_LLM=true LLM_PROVIDER=openai LLM_MODEL=... LLM_API_KEY=...
-> uv run python scripts/smoke_llm_provider.py --allow-real-llm
-> DailyPlannerAgent.run(provider=current_provider)
-> validate structured output and task ids
-> print status=ok
```

---

## 5. 使用方式

默认安全检查：

```bash
uv run python scripts/smoke_llm_provider.py
```

真实 provider：

```bash
AI_ENABLE_REAL_LLM=true \
LLM_PROVIDER=openai \
LLM_MODEL=gpt-4.1-mini \
LLM_API_KEY=... \
uv run python scripts/smoke_llm_provider.py --allow-real-llm
```

OpenAI-compatible：

```bash
AI_ENABLE_REAL_LLM=true \
LLM_PROVIDER=openai-compatible \
LLM_MODEL=<provider-model> \
LLM_API_KEY=... \
LLM_BASE_URL=https://... \
uv run python scripts/smoke_llm_provider.py --allow-real-llm
```

---

## 6. 验收标准

- [x] 默认执行不发网络请求，并返回 `status=skipped`。
- [x] 缺少 `AI_ENABLE_REAL_LLM=true` 时拒绝真实调用。
- [x] `LLM_PROVIDER=mock` 时拒绝真实调用。
- [x] 缺少 `LLM_API_KEY` 时拒绝真实调用。
- [x] `LLM_MODEL=structured-mock-v1` 时拒绝真实调用。
- [x] 真实调用路径校验 provider 输出的 task ids 不变。
- [x] 默认验证阶梯不包含真实 provider smoke。

---

## 7. 验证计划

```bash
uv run python scripts/smoke_llm_provider.py
uv run python -m unittest tests.test_llm_provider_smoke_script tests.test_llm_providers tests.test_daily_planner_agent
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 8. Review Checklist

- [x] 是否默认不发网络请求。
- [x] 是否没有把 API key 写入文档或测试。
- [x] 是否没有写数据库。
- [x] 是否没有进入 CI 默认验证。
- [x] 是否仍然保护 task id / sort order 边界。

---

## 9. 后续迭代建议

1. 从真实 provider response 中提取 token usage，填充 `AIJob.job_metadata.usage`。
2. 增加 planner offline eval JSONL 输出，用于比较不同 provider / prompt 的结果质量。
3. 增加 provider allowlist / environment guard，避免生产外误用高成本模型。

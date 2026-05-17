# Iteration: P2 Daily Planner Prompt Registry

> 状态：Done  
> 阶段：P2  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

把 Daily Planner Agent 的 prompt 从代码字符串迁移为版本化 prompt 文件，并通过 prompt registry 统一加载、记录版本和 checksum，为后续真实 LLM provider、prompt 评估和回滚做准备。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos LLM & Agent Architecture](../chronos-llm-agent-architecture.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P2 Frontend API Contract](../chronos-p2-frontend-api-contract.md)
- [x] [P2 Daily Planner Agent Shell](./2026-05-17-p2-daily-planner-agent-shell.md)

### 背景

上一轮已经接入 Daily Planner Agent shell，但 prompt 仍写在 `DailyPlannerAgent._prompt()` 里。这和工程规范里的“Prompt 文件必须版本化、不要散落在 service 或 worker 中”不一致，也不利于后续真实 LLM 接入、prompt AB、离线评估和问题回滚。

本轮把 prompt 管理从代码逻辑中抽离：Agent 只按 key 获取 prompt；prompt 文件承载目标、输入说明、输出 schema、产品语气和禁止事项；每次调用记录 prompt version 和 checksum。

### 目标

- 新增 `app/ai/prompts/` 目录。
- 新增 Daily Planner v1 prompt Markdown 文件。
- 新增 prompt registry，按 key 加载 prompt 文件。
- Prompt template 暴露 `key`、`version`、`content`、`checksum`。
- Daily Planner Agent 使用 registry，不再内联 prompt 字符串。
- AIJob metadata 记录 prompt checksum。
- 测试覆盖 prompt registry 加载、Agent 使用版本化 prompt、AIJob 记录 prompt trace。

### 非目标

- 不接真实 LLM provider。
- 不做 prompt AB 实验。
- 不做 prompt lint CLI。
- 不引入 LangGraph。
- 不让 prompt 文件决定业务状态机。

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

Daily Planner prompt 明确要求输出轻盈、克制、可信、不施压，不把原始评分暴露为主解释，不让“聪明”压过“可信”。复杂约束进入 prompt 文件和业务层校验，用户仍只看到清楚的 Today 顺序。

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
| Prompt registry | 按 key 加载版本化 prompt | Must | `daily_planner` |
| Prompt file | 新增 `p2-daily-planner-agent-v1.md` | Must | Markdown 可 review |
| Prompt checksum | 对 prompt content 计算 sha256 | Must | 追踪和回滚 |
| Agent integration | Daily Planner Agent 从 registry 获取 prompt | Must | 不再内联文案 |
| AIJob trace | job metadata 记录 prompt checksum | Must | 调用可追踪 |
| Package data | 打包时包含 prompt Markdown | Should | `pyproject.toml` |

### 用户故事

```text
作为 Chronos 用户，
我希望 AI 的语气和边界稳定一致，
以便我对 Today 的推荐顺序保持信任。
```

```text
作为产品 / prompt 维护者，
我希望 prompt 是可 review 的版本化文件，
以便我能清楚知道 AI 为什么以这种方式解释今日计划。
```

```text
作为后端开发者，
我希望 Agent 调用记录 prompt version 和 checksum，
以便后续接真实 LLM 后能定位某次结果来自哪版 prompt。
```

```text
作为系统模块，
我希望 prompt 只影响结构化建议，不直接决定业务落库，
以便 PlanningService 仍然负责最终校验、取舍和 fallback。
```

### 主要流程

```text
DailyPlannerAgent.run
-> prompt_registry.get("daily_planner")
-> provider.generate_structured(prompt=template.content, metadata.prompt=...)
-> PlanningService 写入 AIJob prompt_version / prompt_checksum
-> StrategySnapshot 仍由 Planning Engine 落库
```

---

## 5. 数据与接口

### Prompt 文件结构

```text
app/ai/prompts/
  registry.py
  daily_planner/
    p2-daily-planner-agent-v1.md
```

### PromptTemplate

```text
PromptTemplate {
  key
  version
  content
  checksum
}
```

### AIJob metadata

```json
{
  "mode": "sync_structured_shell",
  "planner_core": "planning-engine-v1",
  "prompt_checksum": "sha256",
  "output_applied": true
}
```

---

## 6. 验收标准

- [x] Daily Planner prompt 不再内联在 `DailyPlannerAgent`。
- [x] Prompt 文件包含目标、输入说明、输出说明、产品语气和禁止事项。
- [x] Agent metadata 传递 prompt key、version、checksum。
- [x] `AIJob.job_metadata.prompt_checksum` 可用于追踪。
- [x] 测试覆盖 prompt registry 与 Agent 使用。
- [x] 文档同步说明 prompt registry 使用方式。

---

## 7. 验证计划

```bash
uv run python -m unittest tests.test_daily_planner_agent tests.test_today_services tests.test_today_api
uv run python scripts/verify_local.py --planner-eval --all-smoke
git diff --check
```

---

## 8. Review Checklist

- [x] 是否符合 Chronos “轻盈、克制、可信赖”的产品人格。
- [x] 是否没有让 prompt 或 LLM 直接写业务表。
- [x] 是否保留 Planning Engine v1 deterministic fallback。
- [x] 是否让 prompt 版本和内容可追踪。
- [x] 是否为真实 provider 接入留下清晰边界。

---

## 9. 后续迭代建议

1. 接入真实 LLM provider adapter，但默认继续关闭。
2. 增加 prompt lint / schema smoke，检查 prompt 文件必填章节。
3. 增加 planner agent 离线评估，把 mock / real output 和 Planning Engine baseline 对比。

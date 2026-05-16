# Iteration: P3 Smoke Developer Entry

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

把 P3 smoke 的运行入口和验证规则补进 README 与工程规范，让后续迭代知道什么时候该跑 P1 / P2 / P3 smoke。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Positioning](../chronos-product-positioning.md)
- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P3 natural growth smoke 已经覆盖数据接入、精力、外部输入、提醒和 scheduler contract，但如果 README 与工程规范没有同步，后续开发容易只跑单测，漏掉跨模块闭环回归。

### 目标

- README 增加 `scripts/smoke_p3_natural_growth_loop.py`。
- README 的本地验收从 P1/P2 扩展为 P1-P3。
- 工程规范增加 smoke 与验证阶梯，说明不同改动需要跑哪些检查。

### 非目标

- 不新增业务代码。
- 不新增测试脚本。
- 不改变 P3 smoke 行为。

---

## 3. 产品约束对齐

### 核心路径

```text
Docs -> Verification -> Stable Execution Loop
```

- [x] Capture
- [x] Inbox
- [x] Today
- [x] Task Detail
- [x] Focus
- [x] Report
- [x] Me
- [x] Goals
- [x] AI Agent

### 产品人格

验证规则也是产品人格的一部分：让复杂模块在后台稳定工作，避免后续迭代因为漏测让用户看到喧闹、不可信的行为。

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
| README smoke entry | 增加 P3 smoke 运行命令 | Must | 本地开发入口 |
| README acceptance flow | P1-P3 验收命令补齐 compileall / diff check | Must | 开发者可直接复制 |
| Engineering validation ladder | 说明不同改动该跑哪些验证 | Must | 约束后续迭代 |

### 用户故事

```text
作为后端开发者，
我希望 README 能直接告诉我 P1/P2/P3 smoke 怎么跑，
以便本地改完代码后能快速验证核心闭环没有断。
```

```text
作为 Chronos 用户，
我希望后台复杂能力每次迭代都经过稳定回归，
以便产品保持轻盈、可信，而不是把系统复杂度暴露给我。
```

### 主要流程

```text
Read README
-> run migration
-> run P1/P2/P3 smoke by scope
-> run tests / compile / diff check
-> commit only after verification
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

- [x] 不涉及
- [ ] 涉及已有 Agent
- [ ] 新增 Agent
- [ ] 修改 Prompt
- [ ] 修改 Structured Output
- [ ] 修改 fallback

### LLM 安全边界

- [x] LLM 不直接写业务表
- [x] LLM 输出经过 schema validation
- [x] 失败时有 fallback
- [x] AIJob 状态可查询
- [x] 用户保留修正权

说明：本轮只更新开发文档，不改 AI 行为。

---

## 7. 验收标准

### 功能验收

- [x] README 包含 P3 smoke 命令。
- [x] README 本地验收包含 P1/P2/P3 smoke、全量测试、编译和 diff check。
- [x] 工程规范说明 smoke 选择规则。
- [x] 工程规范明确 smoke 不重置开发数据库，不绕过 API / worker。

### 数据验收

- [x] 不写数据库。
- [x] 不新增 migration。

### 体验验收

- [x] 后续开发者能更容易保持 Chronos 的稳定闭环。
- [x] 验证规则与“复杂度藏在背后”的产品设计一致。

---

## 8. 测试计划

### 单元测试

- [x] `uv run python -m unittest discover -s tests`

### API 测试

- [x] 复用全量测试。

### 集成测试

- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| README 命令变多 | 新人可能觉得启动成本高 | 区分快速启动和验收流程 |
| 文档可能再次漂移 | 验证规则失效 | 新增 smoke 或关键脚本时同步 README 与工程规范 |

### 关键取舍

本轮没有新增自动化命令封装，而是先把可复制、可理解的验证阶梯写清楚，保持项目早期的透明度。

---

## 10. Review 记录

### 自检结论

- 与前一轮 P3 smoke 对齐。
- 与既有 P1/P2 smoke 文档风格一致。
- 没有扩大产品范围，也没有改变业务行为。

### 后续建议

- 后续可以补一个统一 `scripts/verify_all.py` 或 Makefile，但需要先确认团队偏好的命令入口。

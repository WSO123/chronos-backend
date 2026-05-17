# Iteration: Local Verification Runner

> 状态：Done  
> 阶段：Developer Experience  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 `scripts/verify_local.py`，把 Chronos 后端迭代后的基础验证和可选 smoke 验证编排成一个统一入口，降低后续迭代漏跑命令的概率。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos P3 Frontend API Contract](../chronos-p3-frontend-api-contract.md)

### 背景

过去多个迭代都依赖同一组验证命令：`unittest`、`compileall`、`git diff --check`，并根据影响面补跑 P1/P2/P3 smoke。命令已经在 README 和工程规范里沉淀，但仍需要开发者手动记忆和组合。

### 目标

- 提供统一本地验证入口。
- 默认跑基础验证：单测、编译、diff check。
- 支持按需跑 P1/P2/P3 smoke。
- 支持 migration 变更时显式跑 `alembic upgrade head`。

### 非目标

- 不替代 CI。
- 不隐藏失败输出。
- 不重置数据库。
- 不改变已有 smoke 脚本行为。

---

## 3. 产品约束对齐

本轮是开发体验基础设施，不改变用户可见产品能力。它的价值是让后续功能迭代更稳定地遵守 Chronos 的架构约束和验证阶梯。

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
| Base verification | 默认执行 `unittest`、`compileall`、`git diff --check` | Must | 每轮迭代基础盘 |
| Optional smoke | `--smoke p1/p2/p3` 或 `--all-smoke` | Must | 按影响范围选择 |
| Optional migration check | `--alembic` | Should | schema 变更时使用 |
| Docs | README 和工程规范说明验证入口 | Must | 防止脚本成为隐形工具 |

### 用户故事

```text
作为后端开发者，
我希望用一个命令跑完当前迭代需要的验证梯度，
以便减少漏跑 smoke 或 diff check 的风险。
```

```text
作为项目维护者，
我希望验证入口仍然显式展示每个命令，
以便失败时能快速定位到底是哪一层坏了。
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
- [x] Scripts
- [x] Docs

### 命令设计

```bash
uv run python scripts/verify_local.py
uv run python scripts/verify_local.py --smoke p3
uv run python scripts/verify_local.py --all-smoke
uv run python scripts/verify_local.py --alembic --all-smoke
```

### 执行顺序

```text
optional alembic
-> unit tests
-> compileall
-> git diff --check
-> optional smoke scripts
```

---

## 6. AI / LLM 影响

- [x] 不涉及 LLM。
- [x] 不涉及 Prompt。
- [x] 不涉及 AIJob。

---

## 7. 验收标准

### 功能验收

- [x] 默认命令能跑基础验证。
- [x] `--smoke p3` 能追加 P3 smoke。
- [x] `--all-smoke` 能追加 P1/P2/P3 smoke。
- [x] 每一步输出命令名称和失败位置。
- [x] README / 工程规范说明使用方式。

### 数据验收

- [x] 不新增数据库表。
- [x] 不修改业务数据模型。
- [x] 不重置开发数据库。

---

## 8. 测试计划

- [x] `uv run python scripts/verify_local.py --smoke p3`
- [x] `uv run python scripts/verify_local.py --help`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 脚本掩盖真实命令 | 失败难定位 | 每一步打印具体命令 |
| 默认验证过重 | 每轮耗时增加 | 默认只跑基础验证，smoke 显式选择 |
| CI 和本地脚本分叉 | 规则不一致 | 文档把它定位为本地验证入口，不替代 CI |

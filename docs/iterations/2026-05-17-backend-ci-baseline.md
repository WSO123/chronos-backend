# Iteration: Backend CI Baseline

> 状态：Done  
> 阶段：Developer Experience  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 GitHub Actions 基础 CI，在 push / pull request 上执行 Chronos 后端基础验证，确保单测、编译和 diff check 不依赖人工记忆。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

本地已有 `scripts/verify_local.py` 作为统一验证入口。下一步需要把最基础、最稳定的一层验证接入 CI，让每次 push / pull request 都能自动防止明显回归。

### 目标

- 新增 `.github/workflows/backend-ci.yml`。
- CI 安装 uv 和 Python 3.14。
- CI 执行 `uv sync --locked`。
- CI 执行 `uv run python scripts/verify_local.py`。
- 文档明确 CI 和本地 smoke 的边界。

### 非目标

- 不在 CI 中启动 Docker Compose。
- 不在 CI 中默认执行 P1/P2/P3 smoke。
- 不接入真实第三方服务。
- 不新增部署流程。

---

## 3. 产品约束对齐

本轮不改变用户可见产品能力。它保证后续围绕 Capture、Inbox、Today、Focus、Reports、Me、P3 自然生长模块的迭代拥有更稳定的基础质量门。

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
| GitHub Actions baseline | push / PR 执行基础验证 | Must | 不依赖 Docker |
| uv locked install | 使用 `uv sync --locked` | Must | 保持依赖可重复 |
| Verify runner reuse | CI 调用 `scripts/verify_local.py` | Must | 与本地验证入口一致 |
| Docs | README 和工程规范说明 CI 边界 | Must | smoke 仍本地显式跑 |

### 用户故事

```text
作为项目维护者，
我希望每次 push 或 PR 都自动执行基础验证，
以便明显的测试、编译和格式问题不会进入主分支。
```

```text
作为后端开发者，
我希望 CI 和本地验证使用同一个入口，
以便本地跑过的基础检查和远端检查保持一致。
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
- [x] CI
- [x] Docs

### Workflow

```yaml
on:
  pull_request:
  push:
    branches:
      - main
```

### 执行步骤

```text
checkout
-> setup python 3.14
-> setup uv
-> uv sync --locked
-> uv run python scripts/verify_local.py
```

---

## 6. AI / LLM 影响

- [x] 不涉及 LLM。
- [x] 不涉及 Prompt。
- [x] 不涉及 AIJob。

---

## 7. 验收标准

### 功能验收

- [x] workflow 文件存在。
- [x] workflow 触发 push / pull request。
- [x] workflow 使用 `uv sync --locked`。
- [x] workflow 复用 `scripts/verify_local.py`。
- [x] 文档说明 smoke 不默认进 CI。

### 数据验收

- [x] 不需要数据库服务容器。
- [x] 不需要 Redis / MinIO。
- [x] 不运行 migration。

---

## 8. 测试计划

- [x] `uv run python scripts/verify_local.py`
- [x] `uv run python -m compileall app tests scripts`
- [x] `git diff --check`

说明：GitHub Actions 文件本身需要在远端 push / PR 后由 GitHub 执行。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| Python 3.14 runner 可用性 | CI 可能因运行器支持问题失败 | 与 `pyproject.toml` 保持一致，后续可加 `.python-version` 或调整 setup-python |
| CI 覆盖不含 smoke | 无法捕获本地数据库链路问题 | 文档要求涉及对应范围时本地显式跑 smoke |
| workflow 和本地验证分叉 | 规则漂移 | CI 直接调用 `scripts/verify_local.py` |

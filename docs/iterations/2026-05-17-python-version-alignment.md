# Iteration: Python Version Alignment

> 状态：Done  
> 阶段：Developer Experience  
> 创建日期：2026-05-17  
> 负责人：Codex  
> 关联 PR / Issue / Commit：待提交

---

## 1. 迭代摘要

新增 `.python-version`，并让 GitHub Actions 从该文件读取 Python 版本，减少本地、`pyproject.toml` 和 CI 之间的解释器版本漂移。

---

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)

### 背景

项目当前在 `pyproject.toml` 中声明 `requires-python = ">=3.14"`，CI workflow 也写死了 `python-version: "3.14"`。这会在后续升级 Python 时产生多处修改点。

### 目标

- 新增 `.python-version`，当前值为 `3.14`。
- 调整 `.gitignore`，允许 `.python-version` 被提交。
- CI 使用 `python-version-file: ".python-version"`。
- README 说明本地 Python 版本来源。
- 工程规范约束 `.python-version` 与 `pyproject.toml` 保持兼容。

### 非目标

- 不升级 Python。
- 不修改依赖。
- 不修改应用代码。
- 不改变测试或 smoke 语义。

---

## 3. 产品约束对齐

本轮是开发环境一致性治理，不改变用户可见产品能力。它服务于后续稳定迭代，不影响 Chronos 的轻量执行路径。

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
| Python version file | 新增 `.python-version` | Must | 3.14 |
| CI alignment | setup-python 读取 `.python-version` | Must | 减少重复配置 |
| Docs | README 和工程规范说明版本来源 | Must | 后续升级有约束 |

### 用户故事

```text
作为后端开发者，
我希望本地和 CI 使用同一个 Python 版本来源，
以便版本升级时不会出现隐藏的不一致。
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

### 文件变更

```text
.python-version
.gitignore
.github/workflows/backend-ci.yml
README.md
docs/chronos-engineering-guidelines.md
```

---

## 6. AI / LLM 影响

- [x] 不涉及 LLM。
- [x] 不涉及 Prompt。
- [x] 不涉及 AIJob。

---

## 7. 验收标准

### 功能验收

- [x] `.python-version` 存在且为 `3.14`。
- [x] CI 使用 `python-version-file`。
- [x] README 说明 Python 版本来源。
- [x] 工程规范要求版本配置保持一致。

### 数据验收

- [x] 不新增数据库表。
- [x] 不修改 migration。
- [x] 不修改业务数据。

---

## 8. 测试计划

- [x] `uv run python scripts/verify_local.py`
- [x] `git diff --check`

说明：CI 的 `python-version-file` 行为需要在 GitHub Actions 远端执行时最终确认。

---

## 9. 风险与取舍

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| setup-python 对版本文件支持变化 | CI 失败 | 后续可回退为显式 `python-version` |
| `.python-version` 与 `pyproject.toml` 不兼容 | 本地和依赖解析不一致 | 工程规范要求同步维护 |

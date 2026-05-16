# Iteration: P3 Data Source Foundation

> 状态：Done  
> 阶段：P3  
> 创建日期：2026-05-16  
> 关联提交：本轮提交

## 1. 迭代摘要

建立 P3 Calendar / Email / Health 接入前的 Data Source 连接状态底座，让 Me / Settings 可以展示数据接入状态，并为后续同步 worker 提供统一连接模型。

## 2. 背景与目标

### 关联核心文档

- [x] [Chronos Product Design Principles](../chronos-product-design-principles.md)
- [x] [Chronos App 产品信息架构](../chronos-information-architecture-final.md)
- [x] [Chronos Backend Architecture v1](../chronos-backend-architecture-v1.md)
- [x] [Chronos Engineering Guidelines](../chronos-engineering-guidelines.md)

### 背景

P1/P2 已经跑通 Capture -> Inbox -> Today -> Task Detail -> Focus -> Report，并完成目标和洞察增强。P3 将进入自然生长模块，包括日历、邮件、睡眠 / 压力、自动提醒和来源内容关联。

这些能力不能直接写入 Task，也不能绕过用户确认层，因此需要先建立连接状态、授权范围和同步开关模型。

### 目标

- 新增 `DataSourceConnection` 模型。
- 支持 Calendar / Email / Health 三类数据源目录。
- 支持连接、更新、断开连接。
- 所有变更写入 ActivityEvent。
- 明确当前不保存真实 OAuth token。

### 非目标

- 不接真实 OAuth。
- 不保存 access token / refresh token。
- 不拉取外部日历、邮件或健康数据。
- 不生成外部来源任务。
- 不实现 Energy Dashboard。

## 3. 产品约束对齐

### 核心路径

```text
Me -> Settings -> 数据接入
External Source -> Capture / Inbox -> Today
```

本轮主要服务 Me / Settings 和后续外部输入层。

### 产品人格

- 轻盈：先展示连接状态，不把复杂同步逻辑推给用户。
- 克制：不假装已经接入真实外部数据。
- 可信赖：连接 / 更新 / 断开均有事件记录。
- 聪明但不炫耀：只建立后续调度需要的基础信号。

### 设计护栏

- [x] 不让 Today 变成复杂驾驶舱
- [x] 不让 Task Detail 变成信息仓库
- [x] 不让 Focus 变成控制面板
- [x] 不让洞察和解释抢走行动感
- [x] 不让“聪明”压过“可信”

## 4. 需求范围

| 功能 | 描述 | 优先级 |
| --- | --- | --- |
| Data Source Catalog | 返回 calendar / email / health 三类入口 | Must |
| Connect Data Source | 创建或重连连接记录 | Must |
| Update Data Source | 更新状态、同步开关和同步元数据 | Must |
| Disconnect Data Source | 标记断开并关闭同步 | Must |
| ActivityEvent | 记录连接、更新、断开事件 | Must |

### 用户故事

```text
作为一个希望 Chronos 能逐步理解自己日程和外部信息的用户，
我希望能在 Me / Settings 中看到日历、邮件、健康数据的连接状态，
以便我知道哪些外部信息未来会被系统用于任务捕获、精力判断和每日编排。
```

```text
作为一个不希望外部信息直接打乱计划的用户，
我希望外部来源内容先进入 Capture / Inbox，
以便我保留确认、编辑和归类的控制感。
```

### 开发者故事

```text
作为后续 Calendar / Email / Health worker 的开发者，
我希望有统一的数据源连接模型，
以便不同外部来源都能用一致的状态、授权范围和同步元数据进入后续处理流程。
```

## 5. 后端设计

### 影响模块

- [x] API
- [x] Service
- [x] Models
- [x] Schemas
- [x] DB Migration
- [x] Tests

### 数据模型

```text
DataSourceConnection {
  id
  user_id
  source_type
  provider
  status
  external_account_label
  scopes
  sync_enabled
  sync_cursor
  last_sync_at
  connected_at
  revoked_at
  metadata
}
```

### 状态

```text
disconnected -> connected
connected -> paused
connected -> needs_reauth
connected / paused / needs_reauth -> disconnected
disconnected -> connected
```

### 事件

- `DATA_SOURCE_CONNECTED`
- `DATA_SOURCE_RECONNECTED`
- `DATA_SOURCE_UPDATED`
- `DATA_SOURCE_DISCONNECTED`

### API

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/data-sources` | 数据源目录和连接状态 |
| PUT | `/api/v1/data-sources/{source_type}/{provider}` | 创建或重连数据源 |
| PATCH | `/api/v1/data-sources/{connection_id}` | 更新连接状态和同步元数据 |
| POST | `/api/v1/data-sources/{connection_id}/disconnect` | 断开连接 |

## 6. AI / LLM 影响

- [x] 不涉及

后续外部数据同步进入 Capture / Inbox 后，才会触发解析和归类 Agent。

## 7. 验收标准

- 默认返回 calendar / email / health 三类数据源。
- 支持连接数据源并返回默认 scopes。
- 支持暂停和断开连接。
- 不同 `X-User-Id` 之间不能操作彼此连接。
- 不支持的 provider 返回 `VALIDATION_ERROR`。
- 连接、更新、断开写入 ActivityEvent。

## 8. 风险与后续

- 当前仍是开发态 `X-User-Id`，不是正式鉴权。
- 当前不保存 token，真实 OAuth 需要单独安全设计。
- 后续 Calendar / Email / Health worker 需要读取该表，并把外部来源内容写入 Capture / Inbox。

## 9. 验证结果

| 验证项 | 结果 |
| --- | --- |
| `python -m unittest tests.test_data_source_services tests.test_data_source_api` | 9 tests OK |
| `python -m unittest discover -s tests` | 95 tests OK |
| `python -m compileall app tests scripts` | OK |
| `git diff --check` | OK |
| `alembic upgrade head` | OK |
| `scripts/smoke_p1_execution_loop.py` | OK |
| `scripts/smoke_p2_goal_insight_loop.py` | OK |

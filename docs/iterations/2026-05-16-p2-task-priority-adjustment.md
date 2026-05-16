# Iteration: P2 Task Priority Adjustment

日期：2026-05-16
阶段：P2 目标与洞察增强
状态：Implemented

## 1. 背景

产品设计中，AI 负责每日编排和优先级判断，但用户必须保留修正权和控制感。Task Detail 的 P2 动作包含“调整优先级”，它不应该只是通用编辑表单的一部分，而应该沉淀为可追踪的用户反馈信号。

## 2. 目标

- 新增窄接口支持调整任务 `priority` 和 `value_level`。
- 返回调整前后的摘要，方便前端即时反馈。
- 写入独立事件 `TASK_PRIORITY_ADJUSTED`，为后续 AI 学习用户偏好提供数据。
- 保持 Task Detail 简单，不把它变成策略控制面板。

## 3. 非目标

- 不自动触发 Today 重排。
- 不接真实 LLM 重新判断优先级。
- 不新增数据库表。
- 不替代完整任务编辑接口。

## 4. API

| Method | Path | 用途 |
| --- | --- | --- |
| PATCH | `/api/v1/tasks/{task_id}/priority` | 调整任务优先级 / 价值等级 |

Request:

```json
{
  "priority": 1,
  "value_level": "high",
  "reason": "Protect this task today"
}
```

Rules:

- `priority` 和 `value_level` 至少提供一个。
- `priority` 范围为 `1-5`，数字越小越优先。
- 已归档任务不可调整。

## 5. Response

```json
{
  "task": {},
  "previous_priority": 5,
  "current_priority": 1,
  "previous_value_level": "low",
  "current_value_level": "high",
  "changed_fields": ["priority", "value_level"],
  "reason": "Protect this task today"
}
```

## 6. 事件

- `TASK_PRIORITY_ADJUSTED`

payload 包含：

- changed fields
- previous / current priority
- previous / current value level
- optional reason

## 7. 验收标准

- [x] 可以通过 API 调整 priority。
- [x] 可以通过 API 调整 value_level。
- [x] 空 payload 返回 422。
- [x] 调整后返回 previous / current 摘要。
- [x] 调整动作写入 ActivityEvent。
- [x] 不自动触发 Today replan，前端需要时可显式调用 `/today/replan`。

## 8. 设计约束检查

- 用户保留修正权，AI 不独占判断权。
- 接口足够窄，避免 Task Detail 变成信息仓库。
- 事件独立沉淀，后续可被 Insight / Planner 使用。

## 9. 文件变更

| 文件 | 说明 |
| --- | --- |
| `app/schemas/tasks.py` | 新增 priority adjustment request / response |
| `app/services/task_service.py` | 新增调整优先级业务方法和事件 |
| `app/api/v1/tasks.py` | 新增 `PATCH /tasks/{id}/priority` |
| `tests/test_task_goal_services.py` | Service 覆盖调整和事件 |
| `tests/test_task_goal_api.py` | API 覆盖调整和参数校验 |
| `docs/chronos-backend-architecture-v1.md` | 同步架构设计 |
| `docs/chronos-p1-frontend-api-contract.md` | 同步前端 API 合同 |

## 10. 后续

- P2 Goal Progress Timeline。
- 后续 Today planner 可读取 `TASK_PRIORITY_ADJUSTED` 作为用户偏好信号。

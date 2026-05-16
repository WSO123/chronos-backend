# Iteration: P2 Goal Progress Timeline

日期：2026-05-16
阶段：P2 目标与洞察增强
状态：Implemented

## 1. 背景

Goal Detail 的 `Goal Progress` 需要不仅展示完成率，还要让用户知道目标是如何推进到当前状态的。Chronos 的设计原则是“清晰、可信、可行动”，因此本迭代不做复杂甘特图，而是基于已有 ActivityEvent 生成轻量关键节点时间线。

## 2. 目标

- 新增 Goal Progress Timeline API。
- 基于 Goal、关联 Task、ActivityEvent 返回关键推进节点。
- 汇总目标当前完成率、风险状态和 deadline。
- 保持只读，不改变 Today 排序和任务状态。

## 3. 非目标

- 不实现甘特图 / 项目管理式排期。
- 不自动推断历史完成率曲线。
- 不接真实 LLM。
- 不新增数据库表。

## 4. API

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/goals/{goal_id}/progress-timeline` | 获取目标推进时间线 |

Query:

```text
limit=30
```

## 5. Response

```json
{
  "goal_id": "uuid",
  "generated_at": "2026-05-16T09:00:00Z",
  "summary": {
    "goal_id": "uuid",
    "goal_status": "active",
    "deadline": "2026-05-30",
    "total_task_count": 4,
    "completed_task_count": 2,
    "completion_rate": 0.5,
    "risk_level": "on_track",
    "risk_reason": "Goal has a clear next task and no urgent deadline risk."
  },
  "milestones": [],
  "note": "Timeline is derived from goal and task activity events; it does not change Today ordering."
}
```

## 6. Milestone 类型

- `goal_created`
- `goal_updated`
- `task_added`
- `task_completed`
- `task_postponed`
- `task_activated`
- `priority_adjusted`
- `dependency_added`
- `dependency_removed`
- `deadline`

## 7. 验收标准

- [x] 返回 Goal 当前 progress summary。
- [x] 返回基于 ActivityEvent 的 milestones。
- [x] 包含 deadline milestone。
- [x] 支持 limit。
- [x] 用户隔离沿用 Goal 查询。
- [x] API 合同和架构文档已同步。

## 8. 设计约束检查

- Timeline 是 Goal Detail 的辅助解释，不替代 Today 决策。
- Timeline 不做复杂项目管理界面。
- Milestone 文案保持短，支持前端默认折叠或弱展示。

## 9. 文件变更

| 文件 | 说明 |
| --- | --- |
| `app/schemas/goals.py` | 新增 Timeline response schema |
| `app/services/goal_service.py` | 新增 timeline 聚合逻辑 |
| `app/api/v1/goals.py` | 新增 `GET /goals/{id}/progress-timeline` |
| `tests/test_task_goal_services.py` | Service 覆盖关键 milestones |
| `tests/test_task_goal_api.py` | API 覆盖 timeline |
| `docs/chronos-backend-architecture-v1.md` | 同步架构设计 |
| `docs/chronos-p1-frontend-api-contract.md` | 同步前端 API 合同 |

## 10. 后续

- P2 Today Insights Preview。
- 后续可在 Insight Detail 中复用 timeline signals。

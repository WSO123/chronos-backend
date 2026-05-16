# Iteration: P2 Task Dependency View

日期：2026-05-16
阶段：P2 目标与洞察增强
状态：Implemented

## 1. 背景

产品信息架构中，Task Detail 需要承接 `Dependency`，Goal Detail 需要承接 `Dependency Map`。此前 Goal Detail 只返回节点顺序和空 edges，能表达任务列表，但不能表达“先做什么再做什么”的任务依赖。

本迭代补齐任务依赖基础能力，服务路径：

```text
Goals -> Goal Detail -> Dependency Map -> Task Detail
Today -> Task Detail -> Dependency
```

## 2. 目标

- 支持任务之间的前置依赖关系。
- Task Detail 能返回当前任务的前置任务和后续任务。
- Goal Detail 的 Dependency Map 能返回同一 Goal 内真实依赖边。
- 保持轻量、可信、可解释，不把 Task Detail 做成复杂信息仓库。

## 3. 非目标

- 不实现可视化依赖图布局算法。
- 不实现跨目标复杂项目管理。
- 不接真实 LLM 自动生成依赖。
- 不让 Dependency View 影响 Today 排序策略，后续再纳入 planner。

## 4. 业务规则

- 依赖方向统一为 `prerequisite_task -> dependent_task`。
- 添加依赖时，当前任务是后续任务，payload 中的 `prerequisite_task_id` 是前置任务。
- 同一用户下不允许重复依赖边。
- 不允许自依赖。
- 不允许形成环。
- 跨用户任务不可建立依赖。

## 5. 数据模型

```text
TaskDependency {
  id
  user_id
  prerequisite_task_id
  dependent_task_id
  reason
  created_at
  updated_at
}
```

## 6. API

| Method | Path | 用途 |
| --- | --- | --- |
| GET | `/api/v1/tasks/{task_id}/dependencies` | 获取当前任务的前置任务和后续任务 |
| POST | `/api/v1/tasks/{task_id}/dependencies` | 为当前任务添加前置任务 |
| DELETE | `/api/v1/tasks/{task_id}/dependencies/{prerequisite_task_id}` | 删除当前任务的一条前置依赖 |
| GET | `/api/v1/goals/{goal_id}/detail` | 返回目标内 dependency map edges |

## 7. 事件

- `TASK_DEPENDENCY_CREATED`
- `TASK_DEPENDENCY_DELETED`

这些事件用于后续 Reports / Insights / Planner 学习依赖调整行为。

## 8. 验收标准

- [x] 可以创建任务依赖边。
- [x] 可以查询当前任务的 prerequisites / dependents。
- [x] 可以删除任务依赖边。
- [x] Goal Detail 返回目标内真实 dependency edges。
- [x] 循环依赖返回 `400 INVALID_STATE`。
- [x] 跨用户依赖返回 `NOT_FOUND`。
- [x] 关键动作写入 ActivityEvent。
- [x] API 合同文档和 backend architecture 文档已同步。

## 9. 设计约束检查

- Today 不因此变成复杂驾驶舱。
- Task Detail 只返回当前任务相关依赖，不塞入完整历史。
- Goal Detail 展示目标内依赖图，不承担项目管理套件职责。
- 依赖解释只作为信任辅助，不抢走行动感。

## 10. 文件变更

| 文件 | 说明 |
| --- | --- |
| `app/models/task_dependency.py` | 新增任务依赖模型 |
| `alembic/versions/20260516_0007_task_dependencies.py` | 新增依赖表 migration |
| `app/services/task_service.py` | 新增依赖查询、创建、删除和环检测 |
| `app/services/goal_service.py` | Goal Detail 返回真实 dependency edges |
| `app/api/v1/tasks.py` | 新增 dependencies API |
| `app/schemas/tasks.py` | 新增依赖相关 schema |
| `tests/test_task_goal_services.py` | Service 覆盖依赖创建、删除、环检测 |
| `tests/test_task_goal_api.py` | API 覆盖依赖创建、删除、隔离和 Goal Detail edges |
| `docs/chronos-backend-architecture-v1.md` | 同步架构设计 |
| `docs/chronos-p1-frontend-api-contract.md` | 同步前端 API 合同 |

## 11. 后续

- P2 Task Priority / Value 调整接口。
- P2 Goal Progress Timeline。
- 后续 Today planner 可考虑把 dependency edges 纳入推荐顺序。

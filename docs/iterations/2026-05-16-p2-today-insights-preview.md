# Iteration: P2 Today Insights Preview

日期：2026-05-16
阶段：P2 目标与洞察增强
状态：Implemented

## 1. 背景

信息架构中 Today 首页包含 `Today Insights Preview`，用于展示今日风险提醒、剩余时间建议和 AI 调整建议。但 Today 的核心仍是“今日执行顺序”，不能被洞察解释抢走行动感。

## 2. 目标

- 在 `GET /api/v1/today` 中新增 `insights_preview`。
- 提供轻量风险提醒、剩余时间建议、调整建议。
- 保持规则聚合，不接真实 LLM。
- 不改变 Today 排序和任务状态。

## 3. 非目标

- 不新增独立 Insights 页面。
- 不替代 Strategy Detail。
- 不自动触发 replan。
- 不做完整行为分析。

## 4. Response Shape

```json
{
  "insights_preview": {
    "risk_alerts": [],
    "remaining_time_suggestion": {
      "key": "remaining_time",
      "title": "Remaining time",
      "message": "The remaining plan is light enough to keep a calm pace.",
      "signal": "positive",
      "task_id": null
    },
    "adjustment_suggestions": [],
    "source": "rule-today-insights-v1"
  }
}
```

## 5. 规则

- 过期任务生成 `overdue_task` 风险提醒。
- 高价值且今天截止的任务生成 `high_value_due_today` 风险提醒。
- 剩余主序列任务估时生成 `remaining_time` 建议。
- 存在滚动任务时提醒其“可见但不主导今天”。
- 有风险任务时建议先保护风险项。
- 无风险且尚未完成任务时建议从第一个行动开始。

## 6. 验收标准

- [x] Today response 包含 `insights_preview`。
- [x] 能识别过期任务和今天截止的高价值任务。
- [x] 能根据剩余估时返回轻量建议。
- [x] 不新增数据库表。
- [x] 不改变 Today plan version。
- [x] API 合同和架构文档已同步。

## 7. 设计约束检查

- Today 仍以任务序列为核心。
- Preview 只给短提示，不展开复杂解释。
- 深度解释仍放在 Strategy Detail / Insight Detail。

## 8. 文件变更

| 文件 | 说明 |
| --- | --- |
| `app/schemas/today.py` | 新增 insights preview schema |
| `app/services/planning_service.py` | 新增 preview 规则聚合 |
| `tests/test_today_services.py` | Service 覆盖风险和剩余时间建议 |
| `tests/test_today_api.py` | API 覆盖 response shape |
| `docs/chronos-backend-architecture-v1.md` | 同步架构设计 |
| `docs/chronos-p1-frontend-api-contract.md` | 同步前端 API 合同 |

## 9. 后续

- P2 Me Insights 概览增强。
- 后续真实 LLM Today Agent 可替换 `rule-today-insights-v1`，但 response shape 保持稳定。

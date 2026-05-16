# Iteration: P2 Me Insights Overview

日期：2026-05-16
阶段：P2 目标与洞察增强
状态：Implemented

## 1. 背景

Me 是个人信息、数据反馈、洞察和设置的收敛页。此前 Me Overview 只有基础数据，缺少 P2 `Insights` 入口所需的轻量预览。根据产品约束，Me 不应变成复杂仪表盘，因此本迭代只补少量 high-signal highlights。

## 2. 目标

- 在 `GET /api/v1/me/overview` 中新增 `insights`。
- 根据今日完成率、周 Focus、延期 / 过期任务、高价值任务生成轻量 highlights。
- 给前端提供 `suggested_next_view`，默认指向 `insights_detail`。
- 不生成 Daily Report，不调用真实 LLM。

## 3. 非目标

- 不实现完整 Insight Detail。
- 不实现 Energy / Health。
- 不做复杂行为趋势图。
- 不新增数据库表。

## 4. Response Shape

```json
{
  "insights": {
    "highlights": [
      {
        "key": "strong_today",
        "title": "Strong execution today",
        "message": "Most planned work is complete. A short report can help close the loop.",
        "signal": "positive"
      }
    ],
    "suggested_next_view": "insights_detail",
    "detail_available": true
  }
}
```

## 5. 规则

- 今日计划为空：`no_plan_yet`。
- 今日完成率高：`strong_today`。
- 今日已有计划但未完成：`start_needed`。
- 存在过期任务：`overdue_tasks`。
- 存在延期任务：`postponed_tasks`。
- 本周有 Focus：`weekly_focus`。
- 有高价值活跃任务和活跃目标：`high_value_backlog`。

## 6. 验收标准

- [x] Me Overview 返回 `insights`。
- [x] 不生成 Daily Report。
- [x] 能识别强执行日。
- [x] 能识别过期和延期任务。
- [x] API 合同和架构文档已同步。

## 7. 设计约束检查

- Me 仍是收敛页，不做复杂驾驶舱。
- Highlights 控制数量，避免洞察抢走行动感。
- 深度分析继续由 `/insights/detail` 承接。

## 8. 文件变更

| 文件 | 说明 |
| --- | --- |
| `app/schemas/me.py` | 新增 insights overview schema |
| `app/services/me_service.py` | 新增 highlights 聚合 |
| `tests/test_report_me_services.py` | Service 覆盖 insights 概览 |
| `tests/test_report_me_api.py` | API 覆盖 response shape |
| `docs/chronos-backend-architecture-v1.md` | 同步架构设计 |
| `docs/chronos-p1-frontend-api-contract.md` | 同步前端 API 合同 |

## 9. 后续

- P2 Report / Insight 前端合同补齐。
- 后续可让 Me Overview 复用真实 Insight Agent 输出，但保持当前 response shape。

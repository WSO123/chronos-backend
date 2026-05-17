# Chronos Mainline Capability Review

> 日期：2026-05-17
> 用途：作为后续迭代的主线能力复盘和防偏航检查表。
> 范围：只评估当前后端项目中与 P1 核心闭环、P2 核心增强、bounded AI Agent 直接相关的能力。

---

## 1. 复盘结论

当前后端已经从“基础 CRUD + 文档蓝图”推进到“P1 核心执行闭环基本真实可用”的阶段。

最重要的变化是：

```text
Capture -> Inbox -> Today -> Task Detail -> Focus -> Report
```

这条主线已经不再只是接口拼接，而是有了状态联动：

- Inbox 确认 Task 后，若当天已有 active Today plan，会进入滚动编排。
- Today 由 Planning Engine v1 生成确定性计划快照，并保留可解释 score breakdown。
- Planning Engine 已开始读取 TaskPlanningSignal，把 LLM / 规则的语义理解转成可解释 `semantic_*` 分项，而不是让 LLM 直接排序。
- Task Detail 到 Focus 的 Today 绑定已自动兜底，减少前端漏传导致的状态分叉。
- Focus 完成 / 中断 / 延后会进入 Today / Task / Report 汇总口径。
- Daily Report 在 GET 时会检查关键执行指标，避免返回旧复盘。
- P2 中与主线强相关的 Goals、依赖、优先级修正、Strategy Detail 已接入 Today 解释和刷新机制。

当前最该继续做的不是 P3/P4 扩展，也不是商业化或前端页面，而是继续打磨“用户今天到底先做什么、做完后系统是否可信地更新”的主线质量。

---

## 2. 能力成熟度定义

后续评估功能时使用以下等级：

| 等级 | 含义 | 判断标准 |
| --- | --- | --- |
| L0 暂缓 | 不进入当前主线 | P3/P4、商业化、高级 Auth、前端页面、真实第三方集成等 |
| L1 基础可用 | 有模型 / 接口 / service 雏形 | 可以被调用，但还未串入核心用户路径 |
| L2 路径可用 | 已接入产品路径 | 能服务某个页面或流程，但状态一致性 / 边界解释还需要打磨 |
| L3 主线可信 | 状态一致、可解释、可测试 | 接入核心闭环，有测试或 smoke 覆盖，失败时有明确 fallback / impact |

后续主线迭代优先追求 L3，不为了“功能多”去堆 L1/L2。

---

## 3. P1 核心闭环评估

| 能力 | 当前等级 | 结论 | 仍需关注 |
| --- | --- | --- | --- |
| Capture 文本输入 | L3 | 支持文本 Capture，并通过 Parser / fallback 进入 Inbox | P3 语音 / 图片先不扩展 |
| Inbox 确认 Task / Goal | L3 | Task 确认可返回 `today_impact`，重复 confirm 保持幂等 | Goal confirm 后与 Goal Detail 的体验还可继续细化 |
| Inbox -> Today 滚动纳入 | L3 | active Today 存在时通过 `system_refresh` 纳入新任务；无 plan 时不隐式创建 | 需要 smoke 场景长期覆盖 |
| Planning Engine / Today 编排 | L3 | 确定性排序是 source of truth，读取价值、deadline、剩余估时、依赖、用户修正、执行反馈、容量、Energy 和 TaskPlanningSignal 语义信号 | 后续继续补边界场景和回归基线，不让 LLM 接管排序 |
| Today AI signal preparation | L2-L3 | Today 可受控生成缺失 TaskPlanningSignal，并在有新信号时 deterministic replan | 不做首屏静默 provider 狂跑，保留成本和信任边界 |
| Today 快速操作 | L2-L3 | 完成 / 延后等动作已影响 plan item 和执行事件 | 可继续补完整主线 smoke，覆盖更多 action 组合 |
| Task Detail 承接层 | L3 | 聚合 Goal、AI info、Today context、Focus state 和 actions | 避免继续堆成信息仓库 |
| Task Detail -> Focus | L3 | 未传 `daily_plan_item_id` 时后端会自动绑定当前 Today 中同任务 item | 任务不在 Today 时仍允许 Focus，但要保持 report 口径清晰 |
| Focus 执行状态 | L3 | FocusSession、Task、DailyPlanItem、ActivityEvent 保持一致 | 后续可继续扩充部分完成，但不做复杂控制面板 |
| Daily Report | L3 | GET 会自动刷新关键指标，避免旧数据 | 周/月报告仍是 P2 聚合，不替代 Today |
| Me 基础数据 | L2 | 已能承接基础数据反馈 | 不把 Me 扩成 P3/P4 入口大杂烩 |

---

## 4. P2 主线增强评估

P2 只保留和执行主线强相关的部分：Goals、依赖、洞察、解释。

| 能力 | 当前等级 | 结论 | 边界 |
| --- | --- | --- | --- |
| Goals Home / Goal Detail | L2-L3 | 已能展示目标进度、任务列表、推荐下一步 | 不做复杂项目管理 |
| Goal recommended next task | L3 | 已避开仍有未完成前置任务的后续任务 | 若全部任务被阻塞，允许 fallback 到最高价值未完成任务 |
| Goal Next Action Coverage | L2-L3 | Today 会为高价值 / 临近截止目标各自保护一个下一步行动，避免某个目标的任务列表挤掉其他重要方向 | 只做轻量保护，不做复杂项目排程 |
| Task Dependency | L3 | 依赖新增 / 删除会在涉及当前 Today 时触发 `system_refresh` | 依赖是执行顺序信号，不做甘特图替代品 |
| Priority / Value Adjustment | L3 | 用户调整当前 Today 任务会触发 `manual_adjust` revision，并返回 `today_impact` | 不做复杂手动排序系统 |
| Strategy Detail | L3 | 解释 Planning Engine 结果、依赖保护、用户修正、容量状态和 agent review | 不进入 Today 首屏 |
| Task Semantic Planning Signal | L2-L3 | 能把任务语义、目标对齐、复杂度、语义估时和最小推进动作写入可追踪信号，并被 Today 评分读取 | 后续需要补自动刷新策略 |
| Minimum Viable Progress | L2-L3 | 大任务带有语义信号时，Today 可只安排今日最小推进切片，不覆盖 Task 原估时 | 后续需要把 Focus 实际结果用于校准切片大小 |
| Execution Feedback Calibration | L2-L3 | Replan 时会读取 Task 实际投入时间，把 Today 估时校准为剩余工作量，并在 Strategy Detail 解释 | 先不自动改 Task 原估时，避免系统过度自作主张 |
| Insights / Weekly / Monthly | L2 | 作为复盘与趋势入口可用 | 不能替代 Today 的每日执行决策 |

---

## 5. AI Agent 评估

当前 AI 的正确方向是 bounded、可确认、可解释，而不是隐藏控制业务状态。

| Agent | 当前等级 | 允许做什么 | 禁止做什么 |
| --- | --- | --- | --- |
| Capture Parser Agent | L3 | 解析输入，生成 `AIParseResult` / `InboxItem` | 不绕过 Inbox 直接创建 Task / Goal |
| Task Semantic Planning Agent | L2-L3 | 生成 TaskPlanningSignal，供 Planning Engine 解释和评分 | 不直接改 Task / Goal / DailyPlan，不绕过确定性排序 |
| Task Breakdown Agent | L3 | 生成可编辑步骤建议 | 不覆盖用户已有 steps |
| Strategy Explanation Agent | L3 | 基于 `score_breakdown` 生成自然解释 | 不改变排序和 DailyPlan 状态 |
| Daily Planner Agent | L2-L3 | 对 Planning Engine 结果做 critique / suggestion | 不接管排序 source of truth |
| Daily Report Agent | L2-L3 | 写复盘文案和建议 | 不修改 Task / Goal / DailyPlan / FocusSession |
| Insight Detail Agent | L2-L3 | 生成只读洞察解释 | 不修改事实指标和业务状态 |

LLM 接入的主线原则：

- Planning Engine v1 是排序和 fallback 核心。
- LLM 输出必须 structured output + schema validation。
- LLM 失败时业务路径仍可用。
- Provider 真实调用保持 opt-in。
- 提示词用中文表达产品语气和解释边界，避免“聪明”压过“可信”。

---

## 6. 当前明确暂缓

以下内容不是当前优先级，即使代码或文档中已有部分底座，也不应继续扩展：

| 方向 | 当前处理 |
| --- | --- |
| P3 语音 / 图片 Capture | 暂缓，先不扩展主线之外的输入形态 |
| P3 Calendar / Email / Health 真实集成 | 暂缓，保留已有底座即可 |
| P3 Reminder 深化 | 暂缓，不让提醒系统抢走 Today 主线 |
| P4 Social / Group / Team Reminder | 暂缓 |
| 商业化 / 订阅 / 权限分层 | 暂缓 |
| 高级 Auth、短信、邮件验证 | 暂缓，当前简单注册 / 登录足够 |
| 前端页面实现 | 不属于本后端项目当前范围 |
| 生产级上线安全体系 | 后置到核心功能闭环稳定之后 |

---

## 7. 后续主线优先级

### 下一阶段优先做

1. 主线 smoke 扩展

   覆盖一条更完整的 `Capture -> Inbox confirm -> Today -> priority/dependency refresh -> Task Detail -> Focus -> Daily Report` 场景，确保最近几轮状态联动不会回退。

2. Planning Engine 边界场景

   继续补容量、依赖、用户修正、Goal urgency/value、postpone 行为和 semantic planning signal 的固定场景评估，保证核心算法可回归。

3. Goal / Today / Report 的跨页面一致性

   检查同一任务在 Goal Detail、Today、Task Detail、Focus、Daily Report 中的状态口径是否一致。

4. Strategy Detail 解释收敛

   保持 2-4 条轻量解释，不把原始 score breakdown 暴露成复杂驾驶舱。

5. 语义信号刷新与学习闭环

   当 Task / Goal / dependency 变化、或 Focus 实际时长和语义估时偏差较大时，决定是否刷新 TaskPlanningSignal，并把执行反馈用于下一轮估时校准。

### 后续再做

- P3 自然生长模块真实接入。
- Reminder / Notification 的生产化。
- 真实 provider acceptance 深化。
- 更复杂的用户偏好学习。
- P4 社交与协作。

---

## 8. 每轮迭代防偏航检查

每次新需求进入开发前，至少回答以下问题：

- 是否直接增强 `Capture -> Inbox -> Today -> Task Detail -> Focus -> Report`？
- 如果是 P2，是否只增强 Goals、依赖、洞察、解释中与主线强相关的部分？
- 是否保持 Planning Engine v1 作为排序 source of truth？
- 如果使用 LLM，是否 bounded、可确认、可解释、可 fallback？
- 是否会让 Today 变成复杂驾驶舱？
- 是否会让 Task Detail 变成信息仓库？
- 是否会让 Focus 变成控制面板？
- 是否会绕过 Inbox 确认直接创建正式 Task / Goal？
- 是否属于 P3/P4、商业化、前端页面或高级 Auth？如果是，默认暂缓。

---

## 9. 推荐验证基线

文档或轻量契约变更：

```bash
git diff --check
```

主线后端变更：

```bash
uv run python scripts/verify_local.py --smoke p1-bearer-capture
```

核心状态联动变更：

```bash
uv run python scripts/verify_local.py --smoke mainline-state
```

Planning Engine / Today 变更：

```bash
uv run python scripts/verify_local.py --planner-eval --planner-eval-policy
```

需要真实 provider 时：

- 保持 mock / fallback 默认可用。
- 真实 provider 只做 opt-in 验证。
- 不用 provider smoke 代替主线业务测试。

---

## 10. 最近主线提交索引

| Commit | 作用 |
| --- | --- |
| `235c4a7` | Inbox confirm Task 后纳入当前 Today plan，并返回 `today_impact` |
| `6b6a5ef` | Focus start 自动绑定当前 Today item |
| `2633157` | 依赖变化后刷新当前 Today |
| `7f491a8` | 优先级 / 价值修正后刷新当前 Today |
| `f76abb3` | Goal 推荐下一步任务避开未完成依赖 |
| `ac1f67d` | Daily Report 在指标变化时自动刷新 |

这些提交共同把 P1/P2 主线从“接口存在”推进到“状态会跟着用户行为滚动”。

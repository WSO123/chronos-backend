# Chronos App 产品信息架构（最终版 / 含分期标注）

## 一、产品顶层结构

### 全局层
- `Capture` `[P1]`
  - 文本输入
  - 语音输入
  - 图片输入
  - 快速创建 Task
  - 快速创建 Goal
- `Inbox / 待处理池` `[P1]`
  - 待确认输入
  - 待归类任务
  - 待关联 Goal
- `AI Agent` `[P1-P4]`
  - Task / Goal 自动解析 `[P1]`
  - 优先级判断 `[P1]`
  - Rolling Plan 调度 `[P1]`
  - 洞察生成 `[P2]`
  - 自动提醒 `[P3]`
  - 多人任务分配 `[P4]`
- `Notification / Reminder` `[P3-P4]`
  - 执行提醒 `[P3]`
  - 截止提醒 `[P3]`
  - 小组提醒 `[P4]`

### 底部导航（Tab）
1. `Today` `[P1]`
2. `Goals` `[P2]`
3. `Me` `[P1]`

> `Focus` 不作为 Tab，作为任务执行态二级页存在  
> `Task Detail` 不作为一级导航，作为 Today / Goals 的中间承接页存在

---

## 二、页面级信息架构

## 1. Today（首页 / AI 调度中心）`[P1]`

### 页面定位
- 每日任务调度中心
- AI 输出今日推荐执行顺序
- 用户完成快速操作与进入执行态的核心入口

### 页面结构
- `Header`
  - 日期
  - 问候语
  - 今日精力状态 `[P2]`
  - Capture 入口
  - 提醒入口 `[P3]`

- `AI Strategy Card`
  - 今日策略摘要
  - 高价值优先提示
  - 轻量模式 / 冲刺模式提示
  - AI 调度说明 `[P2]`

- `Task List（核心）`
  - 高优先级任务（Pinned）
  - 推荐执行序列（AI 排序）
  - 低优先级任务（折叠）
  - 被滚动到未来的任务提示 `[P2]`

- `Progress`
  - 今日完成进度
  - 今日 Focus 时长 `[P1]`
  - 高价值任务完成率 `[P2]`

- `Quick Actions`
  - 完成
  - 延后
  - 拆解
  - 重新安排 `[P2]`

- `Today Insights Preview` `[P2]`
  - 今日风险提醒
  - 剩余时间建议
  - AI 调整建议

### 可进入页面
- `Task Detail`
- `Capture`
- `Daily Report` `[P1]`
- `Strategy Detail` `[P2]`
- `Reminder Center` `[P3]`

---

## 2. Task Detail（任务详情页 / 中间承接层）`[P1]`

> `Focus` 的入口页，也是从 AI 决策走向执行的过渡层

### 页面结构
- `Basic Info`
  - 标题
  - 所属 Goal
  - 截止时间
  - 来源 `[P3]`
    - 手动创建
    - 语音输入
    - 图片识别
    - 邮件 / 日程生成

- `AI Info`
  - 推荐时长
  - 优先级
  - 执行建议
  - 推荐执行时段 `[P2]`
  - 滞后风险 `[P2]`

- `Progress`
  - 当前进度
  - 当前状态

- `Subtasks / Steps`
  - 子任务列表
  - 执行步骤
  - AI 拆解建议 `[P2]`

- `Dependency` `[P2]`
  - 前置任务
  - 后续任务

- `Related Context` `[P3]`
  - 关联 Goal
  - 关联日程
  - 关联邮件
  - 关联碎片想法

- `Actions`
  - `Start Focus`
  - 完成
  - 延后
  - 调整优先级 `[P2]`
  - 编辑任务 `[P1]`

### 可进入页面
- `Focus`
- `Goal Detail` `[P2]`
- `Task Edit`

---

## 3. Focus（执行页 / 二级页）`[P1]`

### 进入路径
`Today → Task Detail → Focus`  
`Goals → Task Detail → Focus`

### 页面定位
- 单任务专注执行场景
- 尽量减少信息干扰
- 记录执行时长与过程反馈

### 页面结构
- `Current Task`
  - 任务标题
  - Goal 标签
  - 当前步骤

- `Timer`
  - 正计时
  - 番茄钟
  - 推荐剩余时长 `[P2]`

- `Execution Steps`
  - 子步骤列表
  - 当前步骤勾选

- `Status Feedback`
  - 动画反馈 `[P2]`
  - 吉祥物反馈 `[P4]`
  - 轻量激励提示 `[P2]`

- `Actions`
  - 完成
  - 中断
  - 延后
  - 标记部分完成 `[P2]`

- `Mini Insight` `[P2]`
  - 是否建议休息
  - 是否建议切换轻量任务

---

## 4. Goals（目标系统）`[P2]`

### 页面定位
- 中长期目标管理中心
- 承载目标拆解、任务归属、目标推进反馈

### Goals 首页结构
- `Goal List`
  - 标题
  - 进度
  - Deadline
  - 风险状态
  - 关联任务数

- `Goal Filters`
  - 进行中
  - 即将截止
  - 已完成
  - 高价值目标

- `Goal Summary`
  - 总目标数
  - 本周推进情况

### Goal Detail 结构
- `Goal Overview`
  - 标题
  - 描述
  - Deadline
  - 价值等级

- `Goal Progress`
  - 总体完成率
  - 关键节点
  - 当前滞后情况

- `Goal Task List`
  - 未完成任务
  - 已完成任务
  - 推荐下一步任务

- `Dependency Map`
  - 任务依赖关系
  - 阶段顺序

- `AI Suggestion`
  - 拆解建议
  - 目标优化建议
  - 风险预警

- `Goal Actions`
  - 添加任务
  - 调整目标
  - 标记完成

### 可进入页面
- `Task Detail`
- `Goal Edit`
- `Dependency View`

---

## 5. Me（我的）`[P1]`

> 收敛：个人信息、数据反馈、洞察、设置  
> 社交与健康模块先作为入口保留，按分期逐步增强

### 页面结构
- `Profile`
  - 头像 / 名字
  - 连续使用
  - 成就 / 里程碑 `[P2]`

- `Data Overview`
  - 今日完成率
  - 本周专注时间
  - Goal 完成情况 `[P2]`

- `Insights` `[P2]`
  - AI 洞察卡片
  - 行为趋势
  - 精力曲线
  - 高低效时段分析

- `Energy` `[P3]`
  - 睡眠
  - 压力
  - 精力预测结果

- `Social Entry` `[P4]`
  - 小组
  - 好友
  - 点赞互动入口

- `Reports`
  - Daily Report `[P1]`
  - Weekly Report `[P2]`
  - Monthly Report `[P2]`

- `Settings`
  - 通知设置 `[P1]`
  - 数据接入 `[P3]`
    - 日历
    - 邮件
    - 健康
  - AI 策略偏好 `[P2]`
  - Focus 模式设置 `[P1]`

### 可进入页面
- `Daily Report` `[P1]`
- `Weekly Report` `[P2]`
- `Monthly Report` `[P2]`
- `Insight Detail` `[P2]`
- `Energy Dashboard` `[P3]`
- `Social` `[P4]`
- `Settings`

---

## 三、辅助系统信息架构

## 1. Capture System（统一输入层）`[P1-P3]`

### 结构
- `Input Mode Selector`
  - 文本 `[P1]`
  - 语音 `[P3]`
  - 图片 `[P3]`

- `Parsing Result`
  - 识别为 Task `[P1]`
  - 识别为 Goal `[P1]`
  - 识别为日程事项 `[P3]`
  - 识别为碎片想法 `[P3]`

- `User Confirmation`
  - 确认生成 Task
  - 确认生成 Goal
  - 关联到已有 Goal `[P2]`
  - 暂存到 Inbox `[P1]`

- `Post Processing`
  - AI 自动分类 `[P1]`
  - AI 估算时长 `[P1]`
  - AI 建议优先级 `[P1]`
  - 自动映射来源内容 `[P3]`

---

## 2. Reports & Insights System（复盘反馈层）`[P1-P3]`

### Daily Report `[P1]`
- 完成任务数
- Focus 时长
- 延后 / 中断记录
- AI 每日建议

### Weekly Report `[P2]`
- 每日趋势
- 高价值任务推进情况
- 滞后任务分析
- 专注时长总量

### Monthly Report `[P2]`
- Goal 完成趋势
- 长期行为模式
- 策略优化建议

### Insight Detail `[P2]`
- 行为模式分析
- 高低效时段判断
- 任务安排优化建议
- 滚动策略解释

### Energy Dashboard `[P3]`
- 睡眠趋势
- 压力趋势
- 精力曲线
- 精力与任务匹配建议

---

## 3. Social System（轻社交与协作扩展层）`[P4]`

### 结构
- `Friends`
  - 好友列表
  - 状态卡
  - 点赞互动

- `Groups`
  - 小组列表
  - 小组目标
  - 成员状态
  - 小组任务推进

- `Team Reminder`
  - 重要事项提醒
  - 协作任务提醒

- `Ranking / Milestone`
  - 小组成就
  - 里程碑展示

---

## 4. Energy & Health System（精力辅助层）`[P3]`

### 结构
- `Energy Summary`
  - 今日精力状态
  - 精力预测

- `Sleep`
  - 睡眠时长
  - 睡眠质量

- `Stress`
  - 压力指数
  - 压力趋势

- `Energy Insight`
  - 高效时段判断
  - 任务类型建议

> 该模块主要服务 `Today` 的 AI 排序与 `Me` 的洞察反馈，不单独作为一级导航

---

## 四、核心用户路径

### 主路径（执行闭环）`[P1]`
`Capture → Inbox → Today → Task Detail → Focus → 完成 → Today → Daily Report`

### 快速路径（轻操作）`[P1]`
`Today → 快速完成 / 延后`

### 目标路径 ` [P2]`
`Goals → Goal Detail → Task Detail → Focus`

### 复盘路径 `[P1-P2]`
`Today / Me → Daily Report / Weekly Report / Monthly Report`

### 洞察路径 `[P2]`
`Me → Insights → Insight Detail`

### 精力路径 `[P3]`
`Me → Energy Dashboard`

### 协作路径 `[P4]`
`Me → Social → Group / Friend Detail`

---

## 五、交互流程图

### 1. 主交互闭环图

```mermaid
flowchart TD
  A["进入 App"] --> B{"起点"}

  B --> C["Capture"]
  B --> D["Today"]
  B --> E["Goals"]
  B --> F["Me"]

  C --> C1["输入内容<br/>文本 / 语音 / 图片"]
  C1 --> C2["AI 解析"]
  C2 --> C3{"生成结果"}
  C3 --> C4["Task"]
  C3 --> C5["Goal"]
  C3 --> C6["暂存 Inbox"]

  C4 --> G["Inbox / 待处理池"]
  C5 --> G
  C6 --> G
  G --> G1["确认 / 编辑 / 归类"]
  G1 --> D

  D --> D1["查看今日策略"]
  D --> D2["查看任务列表"]
  D --> D3["查看进度"]
  D --> D4{"快速操作"}

  D2 --> H["Task Detail"]
  D4 --> D5["快速完成"]
  D4 --> D6["延后"]
  D4 --> D7["拆解"]
  D5 --> D
  D6 --> D
  D7 --> H

  H --> H1["查看任务信息"]
  H --> H2["查看 AI 建议"]
  H --> H3["查看步骤 / 子任务"]
  H --> H4{"下一步"}

  H4 --> I["Start Focus"]
  H4 --> H5["直接完成"]
  H4 --> H6["延后任务"]
  H4 --> H7["编辑任务"]

  H5 --> D
  H6 --> D
  H7 --> H

  I --> I1["开始专注"]
  I1 --> I2["计时 / 执行步骤"]
  I2 --> I3{"执行结果"}
  I3 --> I4["完成任务"]
  I3 --> I5["中断"]
  I3 --> I6["延后"]

  I4 --> J["更新今日进度"]
  I5 --> D
  I6 --> D

  J --> K["返回 Today"]
  K --> L["生成 Daily Report"]
  L --> F

  E --> E1["Goal List"]
  E1 --> E2["Goal Detail"]
  E2 --> E3["查看目标任务与建议"]
  E3 --> H

  F --> F1["查看数据总览"]
  F --> F2["查看 Reports"]
  F --> F3["查看 Insights"]
  F --> F4["查看 Settings"]
```

### 2. 分角色交互流程图

```mermaid
flowchart TB
  subgraph Input["1. 任务输入流"]
    A1["用户发起 Capture"]
    A2["输入文本 / 语音 / 图片"]
    A3["AI 识别内容"]
    A4{"识别结果"}
    A5["生成 Task"]
    A6["生成 Goal"]
    A7["暂存 Inbox"]
    A8["用户确认 / 编辑 / 归类"]
  end

  subgraph Execution["2. 每日执行流"]
    B1["进入 Today"]
    B2["查看 AI Strategy"]
    B3["查看任务列表"]
    B4["进入 Task Detail"]
    B5["查看 AI 建议 / 步骤"]
    B6["进入 Focus"]
    B7["计时并执行"]
    B8{"结果"}
    B9["完成"]
    B10["中断"]
    B11["延后"]
    B12["返回 Today"]
  end

  subgraph GoalFlow["3. 目标管理流"]
    C1["进入 Goals"]
    C2["查看 Goal List"]
    C3["进入 Goal Detail"]
    C4["查看目标进度"]
    C5["查看 Goal Task List"]
    C6["查看 Dependency / AI Suggestion"]
    C7["进入 Task Detail"]
  end

  subgraph Feedback["4. 反馈复盘流"]
    D1["进入 Me"]
    D2["查看 Data Overview"]
    D3["查看 Daily / Weekly / Monthly Report"]
    D4["查看 Insights"]
    D5["查看 Energy Dashboard"]
    D6["查看 Social"]
    D7["调整 Settings / 偏好"]
  end

  A1 --> A2 --> A3 --> A4
  A4 --> A5
  A4 --> A6
  A4 --> A7
  A5 --> A8
  A6 --> A8
  A7 --> A8
  A8 --> B1

  B1 --> B2 --> B3 --> B4 --> B5 --> B6 --> B7 --> B8
  B8 --> B9 --> B12
  B8 --> B10 --> B12
  B8 --> B11 --> B12

  C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7 --> B4

  B12 --> D1
  D1 --> D2
  D1 --> D3
  D1 --> D4
  D1 --> D5
  D1 --> D6
  D1 --> D7
```

---

## 六、分期建议

### Phase 1（P1）核心闭环上线
- `Capture`
- `Inbox / 待处理池`
- `Today`
- `Task Detail`
- `Focus`
- `Me（基础数据）`
- `Daily Report`
- 基础 AI 调度
- 基础任务创建、完成、延后、拆解

### Phase 2（P2）目标与洞察增强
- `Goals`
- `Goal Detail`
- `Weekly Report`
- `Monthly Report`
- `Insight Detail`
- `AI Strategy Detail`
- 任务依赖
- 高价值任务分析
- 滚动策略解释

### Phase 3（P3）自然生长模块接入
- 语音输入
- 图片输入
- 日历接入
- 邮件接入
- 睡眠 / 压力数据接入
- `Energy Dashboard`
- 自动提醒增强
- 来源内容关联

### Phase 4（P4）轻社交与协作扩展
- `Friends`
- `Groups`
- `Team Reminder`
- 点赞互动
- 小组目标推进
- AI 多人任务分配
- 吉祥物增强反馈

---

## 七、设计原则

- `Today` = 决策中心（AI 输出）
- `Task Detail` = 行为承接层
- `Focus` = 执行场景
- `Goals` = 中长期方向管理
- `Me` = 数据反馈与设置收敛
- `Capture` = 全局输入入口
- `Inbox` = 输入与调度之间的缓冲层

---

## 八、一句话总结

`Capture（输入）→ Inbox（整理）→ Today（决策）→ Task Detail（承接）→ Focus（执行）→ Me / Reports（反馈）`

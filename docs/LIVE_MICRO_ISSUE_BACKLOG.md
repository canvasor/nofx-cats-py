# Live Micro Issue Backlog

> 用途：把 `docs/LIVE_MICRO_MODULE_PLAN.md` 继续细化成可执行 issue。
> 使用方式：每一条都可以直接转成一个 issue；建议补充 `Owner / Due / Status` 字段后进入看板。

## 1. 建议标签

- `epic:ops-quality`
- `epic:data-pipeline`
- `epic:state-reconciliation`
- `epic:execution-protection`
- `epic:risk-decision-runtime`
- `priority:p0`
- `priority:p1`
- `priority:p2`
- `type:infra`
- `type:feature`
- `type:test`
- `type:docs`
- `type:monitoring`
- `blocked`

## 2. 优先级规则

- `P0`：不完成就不能进 `shadow` 或 `live_micro`
- `P1`：建议在 `shadow` 稳定前完成
- `P2`：可延后到 `paper` 或 `live_micro` 后续优化

## 3. Epic A: Ops / Quality

### LM-001 建立稳定的 dev/test 依赖基线

- Priority: `P0`
- Labels: `epic:ops-quality`, `type:infra`
- 目标：
  确保本地和 CI 中的 `pytest`、`pytest-asyncio`、`ruff`、`mypy` 行为一致。
- 交付：
  - 校验并修正虚拟环境安装流程
  - 确认 `make lint`、`make test` 可直接运行
  - 在 README 中补充最小开发环境检查步骤
- 验收标准：
  - 异步测试可正常执行
  - 本地和 CI 执行结果一致
- 依赖：
  - 无

### LM-002 接入 CI 基础门禁

- Priority: `P0`
- Labels: `epic:ops-quality`, `type:infra`
- 目标：
  把 lint、type check、test 变成自动门禁。
- 交付：
  - CI workflow
  - 执行 `ruff check`
  - 执行 `mypy src`
  - 执行 `pytest -q`
- 验收标准：
  - 所有 PR 自动触发检查
  - 失败时能定位到具体步骤
- 依赖：
  - `LM-001`

### LM-003 引入统一结构化日志

- Priority: `P0`
- Labels: `epic:ops-quality`, `type:infra`, `type:monitoring`
- 目标：
  替换 apps 中的 `print`，形成统一日志格式。
- 交付：
  - logger 工具模块
  - 统一字段：
    - `ts`
    - `level`
    - `service`
    - `decision_id`
    - `symbol`
    - `order_id`
    - `reason`
  - 改造所有 app 入口
- 验收标准：
  - 不再在生产路径使用裸 `print`
  - 关键链路日志可串联同一笔决策
- 依赖：
  - 无

### LM-004 收口运行模式配置

- Priority: `P0`
- Labels: `epic:ops-quality`, `type:infra`
- 目标：
  明确定义 `shadow / paper / live_micro` 的行为边界。
- 交付：
  - 配置层模式校验
  - 启动时打印模式摘要
  - 对危险模式增加显式保护
- 验收标准：
  - `live_micro` 下存在 symbol/tier/size 限制
  - 启动参数错误时能立刻失败
- 依赖：
  - 无

### LM-005 增补关键异常路径测试

- Priority: `P1`
- Labels: `epic:ops-quality`, `type:test`
- 目标：
  覆盖进入 `shadow` 前最容易出事故的路径。
- 交付：
  - stale 数据测试
  - 用户流 stale 测试
  - 精度对齐失败测试
  - 拒单/保护单缺失测试
- 验收标准：
  - 关键风险路径均有自动化测试
- 依赖：
  - `LM-001`
  - `LM-002`

## 4. Epic B: Data Pipeline

### LM-101 建立统一 symbol canonical mapping

- Priority: `P0`
- Labels: `epic:data-pipeline`, `type:feature`
- 目标：
  统一处理 `BTC`、`BTCUSDT`、NOFX `pair`、Binance `symbol`。
- 交付：
  - symbol mapping 模块
  - 显式转换函数
  - 测试覆盖大小写、缺后缀、非法 symbol
- 验收标准：
  - 决策、执行、存储内部统一使用 canonical symbol
- 依赖：
  - 无

### LM-102 给 NOFX collector 增加重试、退避与错误分类

- Priority: `P0`
- Labels: `epic:data-pipeline`, `type:infra`
- 目标：
  让采集器可长时间稳定运行。
- 交付：
  - 网络错误重试
  - 指数退避
  - 超时分类
  - HTTP 错误分类
  - 采集失败日志
- 验收标准：
  - 临时性 NOFX 异常不会直接导致服务退出
- 依赖：
  - `LM-003`

### LM-103 扩展原始快照 envelope

- Priority: `P1`
- Labels: `epic:data-pipeline`, `type:feature`
- 目标：
  让快照满足回放与排障需求。
- 交付：
  - 增加 `status_code`
  - 增加 `schema_version`
  - 增加 `latency_ms`
  - 增加采集失败记录
- 验收标准：
  - 任意快照都有足够上下文用于复盘
- 依赖：
  - `LM-102`

### LM-104 给 normalized feature 增加数据质量字段

- Priority: `P1`
- Labels: `epic:data-pipeline`, `type:feature`
- 目标：
  让决策层明确知道数据是否可安全使用。
- 交付：
  - `freshness_ok`
  - `completeness_score`
  - `execution_safe`
  - 对应测试
- 验收标准：
  - stale 或关键字段缺失可被下游显式识别
- 依赖：
  - `LM-101`

### LM-105 改造 UniverseBuilder 为配置驱动

- Priority: `P1`
- Labels: `epic:data-pipeline`, `type:feature`
- 目标：
  从“简单拼接榜单”改成“受白名单/tier/可交易性约束”的候选池构建。
- 交付：
  - 接入 `symbols.yaml`
  - tier 过滤
  - Binance 可交易状态过滤
  - 决策用候选池日志
- 验收标准：
  - `live_micro` 下只产出 `core` symbols
- 依赖：
  - `LM-101`

### LM-106 建立 replay 输入约定

- Priority: `P1`
- Labels: `epic:data-pipeline`, `type:docs`, `type:feature`
- 目标：
  约定后续 replay/shadow 读取方式。
- 交付：
  - snapshot 命名规范
  - feature 命名规范
  - replay 读取接口或目录约定
- 验收标准：
  - 任一决策都可定位其输入快照
- 依赖：
  - `LM-103`

## 5. Epic C: State Reconciliation

### LM-201 设计并实现内部订单状态模型

- Priority: `P0`
- Labels: `epic:state-reconciliation`, `type:feature`
- 目标：
  明确定义本地 order/algo order 生命周期。
- 交付：
  - 普通单状态模型
  - 条件单状态模型
  - 状态迁移规则
  - 单元测试
- 验收标准：
  - 本地状态能表达 Binance 用户流关键状态变化
- 依赖：
  - 无

### LM-202 设计并实现内部持仓与账户状态模型

- Priority: `P0`
- Labels: `epic:state-reconciliation`, `type:feature`
- 目标：
  建立本地持仓、余额、风险摘要模型。
- 交付：
  - position state
  - balance state
  - account snapshot builder
- 验收标准：
  - `RiskKernel` 可直接消费真实账户快照
- 依赖：
  - 无

### LM-203 落盘所有 Binance 用户流关键事件

- Priority: `P0`
- Labels: `epic:state-reconciliation`, `type:feature`
- 目标：
  保证账户状态变化可审计可回放。
- 交付：
  - 落盘 `ORDER_TRADE_UPDATE`
  - 落盘 `ACCOUNT_UPDATE`
  - 落盘 `ALGO_UPDATE`
  - 记录接收时间、listenKey、原始 payload
- 验收标准：
  - 任意订单/持仓变化都可找到原始事件
- 依赖：
  - `LM-003`

### LM-204 构建用户流事件处理器

- Priority: `P0`
- Labels: `epic:state-reconciliation`, `type:feature`
- 目标：
  用用户流事件驱动本地订单与持仓状态更新。
- 交付：
  - event handler
  - 状态更新逻辑
  - 错误事件处理
- 验收标准：
  - 收到增量事件后，本地状态持续更新
- 依赖：
  - `LM-201`
  - `LM-202`
  - `LM-203`

### LM-205 增加 positionRisk / account 全量对账任务

- Priority: `P0`
- Labels: `epic:state-reconciliation`, `type:feature`
- 目标：
  周期性确认本地状态与交易所最终真相一致。
- 交付：
  - `positionRisk` 对账
  - 账户余额对账
  - open orders 对账
  - 差异检测与修复
- 验收标准：
  - 增量与全量结果最终一致
- 依赖：
  - `LM-204`

### LM-206 实现断线重连后的全量状态重建

- Priority: `P0`
- Labels: `epic:state-reconciliation`, `type:feature`
- 目标：
  WS 断线后恢复挂单、条件单、持仓与余额真相。
- 交付：
  - reconnect hook
  - 全量状态拉取
  - 覆盖本地缓存
  - 恢复日志与告警
- 验收标准：
  - 断线恢复后状态无长期漂移
- 依赖：
  - `LM-205`

### LM-207 建立状态不一致告警与 kill switch 条件

- Priority: `P1`
- Labels: `epic:state-reconciliation`, `type:monitoring`
- 目标：
  状态机出错时停止新增风险。
- 交付：
  - mismatch 指标
  - mismatch 日志
  - 触发 kill switch 的阈值定义
- 验收标准：
  - 持续 mismatch 时系统不再开新仓
- 依赖：
  - `LM-205`

## 6. Epic D: Execution Protection

### LM-301 定义开仓后保护单编排流程

- Priority: `P0`
- Labels: `epic:execution-protection`, `type:feature`
- 目标：
  明确“下单 -> 成交 -> 挂保护单 -> 校验”的执行链。
- 交付：
  - 流程状态图
  - 内部命令/事件模型
  - 失败分支定义
- 验收标准：
  - 所有开仓路径都能接入统一保护流程
- 依赖：
  - `LM-201`
  - `LM-202`

### LM-302 开仓成交后自动挂灾难止损

- Priority: `P0`
- Labels: `epic:execution-protection`, `type:feature`
- 目标：
  成交确认后自动提交 `STOP_MARKET + closePosition=true` 保护单。
- 交付：
  - 成交事件触发器
  - 保护价计算接口
  - 调用 `OrderRouter` 提交保护单
- 验收标准：
  - 任一新开仓成交后都能在阈值内看到保护单
- 依赖：
  - `LM-301`
  - `LM-204`

### LM-303 处理 ALGO_UPDATE 生命周期

- Priority: `P0`
- Labels: `epic:execution-protection`, `type:feature`
- 目标：
  正确处理保护单被拒绝、取消、触发的状态变化。
- 交付：
  - `ALGO_UPDATE` handler
  - reject/cancel/triggered 状态处理
  - 补挂或告警策略
- 验收标准：
  - 保护单异常不会沉默失败
- 依赖：
  - `LM-302`

### LM-304 给 PositionGuardian 接入真实事件源

- Priority: `P0`
- Labels: `epic:execution-protection`, `type:feature`
- 目标：
  让 guardian 成为常驻保护进程，而非演示用工具类。
- 交付：
  - 接入订单状态流
  - 接入持仓状态流
  - 接入告警输出
- 验收标准：
  - guardian 可持续识别保护单缺失、心跳异常
- 依赖：
  - `LM-302`
  - `LM-303`

### LM-305 实现 countdownCancelAll heartbeat 管理器

- Priority: `P0`
- Labels: `epic:execution-protection`, `type:feature`
- 目标：
  维持挂单撤单保险丝，并在失联时让交易所自动清理悬挂风险。
- 交付：
  - 每 symbol heartbeat 管理
  - 启停控制
  - 失败重试与告警
- 验收标准：
  - 心跳异常时可及时发现，且不继续裸奔挂单
- 依赖：
  - `LM-304`

### LM-306 增加执行保护集成测试

- Priority: `P1`
- Labels: `epic:execution-protection`, `type:test`
- 目标：
  覆盖保护链路的高风险异常场景。
- 交付：
  - 部分成交测试
  - 保护单拒单测试
  - 保护单缺失测试
  - 用户流短暂失联测试
- 验收标准：
  - 执行保护关键路径有自动化回归
- 依赖：
  - `LM-302`
  - `LM-303`
  - `LM-305`

## 7. Epic E: Risk / Decision Runtime

### LM-401 把 Decision Engine 改为常驻决策服务

- Priority: `P0`
- Labels: `epic:risk-decision-runtime`, `type:feature`
- 目标：
  从一次性 demo 脚本升级为周期性决策服务。
- 交付：
  - feature 输入读取
  - account state 输入读取
  - 周期决策循环
  - 错误恢复
- 验收标准：
  - 决策服务可长期运行并持续产出结果
- 依赖：
  - `LM-104`
  - `LM-202`

### LM-402 用真实账户快照驱动 RiskKernel

- Priority: `P0`
- Labels: `epic:risk-decision-runtime`, `type:feature`
- 目标：
  让风控不再依赖硬编码 `AccountSnapshot`。
- 交付：
  - 从状态层构建真实 `AccountSnapshot`
  - 接入 user stream stale
  - 接入 state mismatch
- 验收标准：
  - 风控审批基于实时账户状态
- 依赖：
  - `LM-205`
  - `LM-401`

### LM-403 增加 live_micro 模式强限制

- Priority: `P0`
- Labels: `epic:risk-decision-runtime`, `type:feature`
- 目标：
  在 `live_micro` 下强制限制风险外扩。
- 交付：
  - 仅允许 `core` symbols
  - 极小 notional 上限
  - 最大持仓数额外约束
  - 非法模式启动失败
- 验收标准：
  - `live_micro` 下不会交易 `liquid_alt/experimental`
- 依赖：
  - `LM-004`
  - `LM-105`
  - `LM-402`

### LM-404 补组合层风险约束

- Priority: `P1`
- Labels: `epic:risk-decision-runtime`, `type:feature`
- 目标：
  在单笔风控外，再加组合级保护。
- 交付：
  - cluster cap
  - leverage bracket cap
  - symbol concentration cap 整理
- 验收标准：
  - 多持仓情况下不会因相关性暴露过高失控
- 依赖：
  - `LM-402`

### LM-405 完善 decision journal

- Priority: `P1`
- Labels: `epic:risk-decision-runtime`, `type:feature`, `type:docs`
- 目标：
  每笔决策都能解释“为什么交易/为什么不交易”。
- 交付：
  - 记录 symbol 来源
  - 记录 regime
  - 记录 action_score
  - 记录 risk veto 或审批理由
  - 记录最终 order request
- 验收标准：
  - 任意一笔 `NO_TRADE/EXECUTE` 可完整复盘
- 依赖：
  - `LM-401`
  - `LM-402`

### LM-406 建立 shadow 运行模式

- Priority: `P0`
- Labels: `epic:risk-decision-runtime`, `type:feature`
- 目标：
  实时读数、持续决策、只记账不下单。
- 交付：
  - shadow 模式运行开关
  - shadow 下决策与 journal 持续输出
  - shadow 与 live 执行路径隔离
- 验收标准：
  - 可连续运行 1-2 周且不发真实订单
- 依赖：
  - `LM-401`
  - `LM-405`

### LM-407 建立 paper 运行模式

- Priority: `P1`
- Labels: `epic:risk-decision-runtime`, `type:feature`
- 目标：
  模拟成交、持仓与 PnL，为进入 `live_micro` 做准备。
- 交付：
  - paper fill 模型
  - paper position state
  - paper pnl journal
- 验收标准：
  - 可在实时数据下模拟持仓与盈亏
- 依赖：
  - `LM-406`

## 8. 上线前监控与告警

### LM-501 建立关键运行指标

- Priority: `P0`
- Labels: `type:monitoring`
- 目标：
  让值守时能看见系统是否安全。
- 交付：
  - NOFX 最后成功采集时间
  - user stream 最后事件时间
  - listenKey keepalive 状态
  - 保护单缺失计数
  - reject 计数
  - state mismatch 计数
- 验收标准：
  - 关键风险指标可被查询与告警
- 依赖：
  - `LM-003`
  - `LM-203`
  - `LM-304`

### LM-502 建立 kill switch 触发器

- Priority: `P0`
- Labels: `type:monitoring`, `type:feature`
- 目标：
  在关键异常发生时停止新增风险。
- 交付：
  - kill switch 状态机
  - 触发原因枚举
  - 对决策服务和执行服务的拦截
- 验收标准：
  - stale、mismatch、guardian 异常可阻止开新仓
- 依赖：
  - `LM-207`
  - `LM-501`

## 9. 推荐排期

### 第一批必须先做

- `LM-001`
- `LM-002`
- `LM-003`
- `LM-004`
- `LM-101`
- `LM-201`
- `LM-202`
- `LM-203`

### 第二批进入 shadow 前完成

- `LM-204`
- `LM-205`
- `LM-206`
- `LM-301`
- `LM-302`
- `LM-303`
- `LM-304`
- `LM-401`
- `LM-402`
- `LM-405`
- `LM-406`

### 第三批进入 live_micro 前完成

- `LM-305`
- `LM-403`
- `LM-501`
- `LM-502`

### 第四批可在 shadow/paper 稳定后补

- `LM-005`
- `LM-103`
- `LM-104`
- `LM-105`
- `LM-106`
- `LM-207`
- `LM-306`
- `LM-404`
- `LM-407`

## 10. Live Micro 最小上线包

如果只定义一个“最小可上线包”，建议必须包含以下 issue：

- `LM-001`
- `LM-002`
- `LM-003`
- `LM-004`
- `LM-101`
- `LM-201`
- `LM-202`
- `LM-203`
- `LM-204`
- `LM-205`
- `LM-206`
- `LM-301`
- `LM-302`
- `LM-303`
- `LM-304`
- `LM-305`
- `LM-401`
- `LM-402`
- `LM-403`
- `LM-405`
- `LM-406`
- `LM-501`
- `LM-502`

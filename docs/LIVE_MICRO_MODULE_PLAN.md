# Live Micro 模块拆工计划

> 目标：把当前仓库从“可联调骨架”推进到“可控上线的 live_micro 版本”。
> 原则：先补真相与保护，再补策略与扩展；先保证不出事故，再考虑收益优化。

## 1. 当前判断

基于当前代码，项目已经具备以下基础：

- NOFX / Binance REST 与 WS 连接器已具备最小形态。
- Decision / Risk / Execution 主链路已经打通最小闭环。
- 条件单与普通单已分路由，灾难止损请求已可构造。
- 原始快照与决策日志已能落本地 jsonl。

当前离 `live_micro` 仍差 4 个关键闭环：

1. 账户与订单状态真相
2. 开仓后的保护单状态机
3. Shadow / Paper / LiveMicro 运行模式收口
4. CI、监控、告警、回放等上线前工程能力

## 2. 模块拆分

建议拆成 5 个模块并行推进，但按依赖顺序验收：

1. `ops-quality`
2. `data-pipeline`
3. `state-reconciliation`
4. `execution-protection`
5. `risk-decision-runtime`

其中：

- `state-reconciliation` 是 `execution-protection` 的前置。
- `execution-protection` 与 `risk-decision-runtime` 共同决定能否进 `live_micro`。
- `ops-quality` 要最先启动，并作为所有模块的共同门禁。

## 3. 模块任务

### A. `ops-quality`

目标：
建立统一运行基线，让后续联调与上线具备最小工程保障。

当前现状：

- 测试已存在，但本地环境缺少 `pytest-asyncio` 时会直接导致异步测试失效。
- 入口脚本仍大量使用 `print`。
- 尚未看到 CI、结构化日志、监控指标输出。

交付物：

- dev 环境依赖校准，确保 `pytest`、`pytest-asyncio`、`ruff`、`mypy` 一致可运行。
- `make lint`、`make test` 成为统一门禁。
- 结构化日志基础设施，至少统一输出：
  - `ts`
  - `level`
  - `service`
  - `decision_id`
  - `symbol`
  - `order_id`
  - `reason`
- 配置按模式收口：
  - `shadow`
  - `paper`
  - `live_micro`
- CI 接入：
  - `ruff`
  - `mypy`
  - `pytest`

建议任务：

1. 修正并锁定开发依赖。
2. 引入统一 logger，替换 apps 中的 `print`。
3. 为配置加入运行模式校验与启动时摘要打印。
4. 建立 CI 工作流。
5. 增补异常场景测试基线。

退出门槛：

- 新机器按 README 可以跑通安装与测试。
- 异步测试稳定执行。
- 所有 apps 启动后都有统一日志格式。
- PR 可自动执行 lint/type/test。

### B. `data-pipeline`

目标：
把“拉数据并落盘”升级成“可持续供给决策引擎的稳定数据面”。

当前现状：

- NOFX collector 已可拉取 AI500、AI300、Query Rank、Coin、Funding、Heatmap。
- 标准化逻辑已具备最小可用性。
- 当前仍是单进程脚本式写 jsonl，没有真正形成长期运行的数据服务。

交付物：

- 稳定的 NOFX 采集循环。
- 明确的 symbol 映射表。
- 统一 feature 快照输出。
- stale / completeness / freshness 质量字段。
- replay 可读取的快照索引或约定目录结构。

建议任务：

1. 建立 symbol canonical mapping：
   - `BTC`
   - `BTCUSDT`
   - NOFX `pair`
   - Binance `symbol`
2. 给 collector 加入：
   - 重试
   - 指数退避
   - 错误分类
   - latency 记录
   - status_code 记录
3. 给 normalized feature 增加质量字段：
   - `freshness_ok`
   - `completeness_score`
   - `execution_safe`
4. 将 `UniverseBuilder` 改为受 `symbols.yaml` 和 tier 控制，而不是简单拼接。
5. 约定 replay 读取格式，确保每笔决策能追溯原始数据。

退出门槛：

- 连续运行 24 小时无异常中断。
- 任意 symbol 的标准化链路可回溯到原始快照。
- stale 数据能显式传递给下游。

### C. `state-reconciliation`

目标：
建立交易所侧“最终真相”，使本地订单、持仓、余额状态可信。

当前现状：

- 用户流连接和 listenKey keepalive 已具备。
- 但还没有真正的订单/持仓状态机。
- 也没有 `positionRisk` 周期对账与断线重建。

这是 `live_micro` 前最关键的模块。

交付物：

- 本地订单状态机。
- 本地持仓状态机。
- 用户流增量处理器。
- `positionRisk` / 账户查询对账器。
- 断线重连状态重建逻辑。

建议任务：

1. 设计内部状态模型：
   - order state
   - algo order state
   - position state
   - balance state
2. 落盘所有关键用户事件：
   - `ORDER_TRADE_UPDATE`
   - `ACCOUNT_UPDATE`
   - `ALGO_UPDATE`
3. 增加定时对账任务：
   - `positionRisk`
   - open orders
   - algo orders
   - account snapshot
4. 定义“状态不一致”的修复策略：
   - 以交易所结果覆盖本地
   - 标记告警
   - 触发 kill switch 的阈值
5. 补断线恢复流程：
   - WS 重连
   - listenKey 恢复
   - 全量状态重建

退出门槛：

- 本地状态可在任意时刻回答真实持仓与挂单。
- WS 断线后可自动恢复状态。
- 增量事件与周期对账结果一致。

### D. `execution-protection`

目标：
保证每一次新增风险都能被交易所侧保护单覆盖，并在异常时自动收缩风险。

当前现状：

- `OrderRouter` 与 `PreTradeValidator` 已可用。
- `PositionGuardian` 已有雏形。
- 但尚未形成“成交后自动挂保护单”的完整状态机。

交付物：

- 开仓成交后的自动保护单编排。
- `countdownCancelAll` 常驻心跳。
- 保护单缺失探测器。
- 拒单、取消、触发后的恢复逻辑。

建议任务：

1. 定义开仓执行后的动作链：
   - 下单
   - 等待成交确认
   - 计算保护价
   - 挂出灾难止损
   - 验证保护单存在
2. 将 `PositionGuardian` 接入真实订单事件，而不是手工调用。
3. 补 `ALGO_UPDATE` 处理：
   - reject
   - cancel
   - triggered
4. 给每个 symbol 建立 auto-cancel heartbeat 管理器。
5. 增加集成测试：
   - 部分成交
   - 拒单
   - 保护单缺失
   - WS 短时失联

退出门槛：

- 任一开仓成交后，保护单会自动出现。
- 保护单丢失能在阈值内被发现并告警。
- 执行异常不会继续新增风险。

### E. `risk-decision-runtime`

目标：
把当前策略/风控骨架升级为能持续运行、能解释、能安全切模式的决策服务。

当前现状：

- `DecisionEngine`、`MetaAllocator`、`RiskKernel` 已可工作。
- 但当前是一次性 demo 脚本，账户快照和 symbol 都是硬编码输入。
- 风控尚未接入更多真实执行约束。

交付物：

- 常驻决策循环。
- 真实账户快照接入。
- 运行模式约束：
  - `shadow`
  - `paper`
  - `live_micro`
- `Core` 池限制与 live_micro 低风险配置。
- 更完整的 veto 与解释日志。

建议任务：

1. 将 `run_decision_engine` 改为常驻服务：
   - 消费最新 feature
   - 消费最新 account state
   - 周期决策
2. 在 `live_micro` 模式下强制限制：
   - 只允许 `core` symbols
   - 只允许极小 notional
   - 限制最大持仓数
3. 将真实 stale 信号接入 `RiskKernel`：
   - NOFX stale
   - user stream stale
   - state mismatch
4. 补组合层风险：
   - cluster cap
   - symbol cap
   - leverage bracket cap
5. 完善 journal：
   - why this symbol
   - why this side
   - why this size
   - why no trade

退出门槛：

- 决策服务可持续运行而非单次执行。
- `shadow`、`paper`、`live_micro` 行为边界清晰。
- 任意一笔 `EXECUTE/NO_TRADE` 都有完整解释。

## 4. 推荐执行顺序

建议按 6 个 sprint 推进：

### Sprint 1

- `ops-quality` 基线
- `data-pipeline` 稳定采集

验收：

- 测试与日志基线完成
- NOFX 数据稳定采集并可回放

### Sprint 2

- `state-reconciliation` 状态模型
- 用户流事件落盘

验收：

- 本地订单/持仓状态机初版可跑

### Sprint 3

- `state-reconciliation` 周期对账
- 断线重建

验收：

- 用户流与交易所全量状态对齐

### Sprint 4

- `execution-protection` 自动保护单
- heartbeat / guardian 接入

验收：

- 新开仓具备保护单闭环

### Sprint 5

- `risk-decision-runtime` 常驻化
- `shadow` 模式稳定运行

验收：

- 实时数据下连续输出可解释决策

### Sprint 6

- `paper` -> `live_micro`
- 上线告警与回滚预案

验收：

- 仅 `Core` 池、极小仓位、人工盯盘条件下上线

## 5. 上线门禁

进入 `live_micro` 前，以下项目必须全部完成：

- [ ] 异步测试、lint、type check 全绿
- [ ] 用户流状态机完成
- [ ] `positionRisk` 对账完成
- [ ] 开仓后自动挂灾难止损完成
- [ ] `countdownCancelAll` 心跳完成
- [ ] `shadow` 连续稳定运行
- [ ] `paper` 模式有可解释成交与 PnL
- [ ] `live_micro` 模式只允许 `Core` 池
- [ ] NOFX stale / user stream stale / protect missing 有告警
- [ ] 任意决策可回溯到原始快照与风险审批结果

## 6. 不建议当前阶段做的事

以下事项建议延后到 `live_micro` 稳定之后：

- 增加更多策略 sleeve
- 扩大交易 symbol 池
- 接入复杂自适应仓位模型
- 做收益导向的参数搜索
- 直接进入全自动 `live`

## 7. 建议 owner 划分

如果是 1 人推进：

- 先按 `ops-quality -> state-reconciliation -> execution-protection -> risk-decision-runtime -> data-pipeline增强` 顺序做。

如果是 2-3 人推进：

- 工程 owner：`ops-quality + state-reconciliation`
- 执行 owner：`execution-protection`
- 策略 owner：`data-pipeline + risk-decision-runtime`

如果是 4 人推进：

- Owner A：连接器与数据面
- Owner B：状态机与对账
- Owner C：执行与保护单
- Owner D：决策、风控、模式治理

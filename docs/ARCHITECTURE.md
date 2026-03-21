# 架构设计

## 1. 目标架构

Python v1 的目标不是把所有逻辑都塞进一个大进程，而是先形成 **清晰的边界与责任**，让团队可以并行开发。

### 核心边界
- **Connectors**：只负责采集和发送，不负责做策略判断。
- **Feature / State**：负责把原始数据转成内部统一表达。
- **Decision**：生成候选动作，但不直接下单。
- **Risk**：唯一有权批准交易。
- **Execution**：只执行被批准的命令。
- **Journal**：对每笔决策和结果留痕。

## 2. 服务职责

### 2.1 NOFX Collector
职责：
- 拉取 AI500 / AI300 / `coin/{symbol}` / Funding / Heatmap / Query Rank。
- 保留原始响应。
- 对接 Universe Builder 的候选池输入。

输入：
- 配置中的 symbol 白名单与抓取频率
- NOFX API Key

输出：
- 原始快照事件
- 归一化后的中间数据

### 2.2 Binance Market Gateway
职责：
- 订阅 `/public` 高频盘口。
- 订阅 `/market` 标记价格、kline、ticker。
- 产出最小可信行情状态。

### 2.3 Binance User Gateway
职责：
- 维护 listenKey。
- 监听 `ORDER_TRADE_UPDATE`、`ACCOUNT_UPDATE`、`ALGO_UPDATE`。
- 更新本地订单与持仓状态。

### 2.4 Feature Engine
职责：
- 对齐时间窗口。
- 做量纲统一。
- 产出 FeatureVector。

### 2.5 Regime Engine
职责：
- 判断当前 regime：
  - `TREND`
  - `RANGE`
  - `CROWDING`
  - `DEFENSE`

### 2.6 Strategy Sleeves
第一版建议只做 3 个：
- Trend Following
- Crowding Reversal（先留接口，第二阶段再开发）
- Defense / De-risk

### 2.7 Meta Allocator
职责：
- 从多个 sleeve 的候选动作中选最优动作。
- 允许 “NO_TRADE” 作为候选结果。

### 2.8 Risk Kernel
职责：
- 做 veto。
- 计算目标 notional / leverage。
- 限制 gross exposure、cluster risk、symbol tier 上限。

### 2.9 Execution Router
职责：
- 下单前调用 Validator。
- 根据 order type 自动路由到普通单或 Algo 单。
- 处理幂等、重试、拒单、撤单。

### 2.10 Position Guardian
职责：
- 开仓成交后立即确保灾难止损存在。
- 长时间无心跳、用户流异常、连续 reject 时收缩风险。

### 2.11 Journal / Replay
职责：
- 记录每个决策输入、批准结果、下单参数、成交与 PnL。
- 供 replay 与调参使用。

## 3. 数据流

```text
NOFX Snapshot ----┐
                  ├--> Feature Engine --> Regime --> Strategy --> Risk --> Execution
Binance Market ---┤
                  └--> Journal / Replay
Binance User  -------------------------------------> State / Journal / Guardian
```

## 4. 决策流

```text
1. Universe Builder 选出候选 symbol
2. Feature Engine 构建特征
3. Regime Engine 判断市场阶段
4. Strategy Sleeve 对候选 symbol 打分
5. Meta Allocator 选出候选交易
6. Risk Kernel 审批或拒绝
7. Execution Router 下单
8. Guardian 确保止损与保险丝
9. Journal 全链路记录
```

## 5. 状态真相定义

### 最终真相
- 订单状态：以 Binance 用户流 + 订单查询对账为准。
- 持仓状态：以用户流 + position risk 周期校正为准。
- 资金状态：以账户查询和 `ACCOUNT_UPDATE` 为准。

### 非最终真相
- NOFX 排名与聚合指标：用于 alpha，不可替代交易所真实状态。
- 本地策略缓存：只能作为运行时缓存。

## 6. 模块间接口建议

### EventBus Topic 建议
- `nofx.raw.snapshot`
- `nofx.normalized.coin`
- `binance.market.public`
- `binance.market.mark`
- `binance.user.event`
- `feature.vector`
- `signal.candidate`
- `risk.decision`
- `execution.command`
- `execution.event`
- `journal.trade`

## 7. 生产环境建议演进路径

Python v1：
- 全部模块可先运行在 1 台机器上
- 通过 asyncio + 内存事件总线先打通

Python/Go v2：
- WebSocket Gateway 与 Execution 独立进程
- EventBus 切换到 Redis Streams / NATS / Kafka
- 状态存储分层：Redis + ClickHouse + PostgreSQL

## 8. 第一版不做什么
- 不做 RL 端到端直接下单
- 不做自动改风险上限
- 不做全市场任意 symbol 开放
- 不做复杂自适应仓位网格
- 不做多交易所真实同时下单

## 9. 关键工程要求

1. 任何 connector 失败必须可重连。
2. 任何状态切换必须可审计。
3. 任何风控拒绝必须写日志。
4. 任何开仓动作必须能追踪到对应止损。
5. 任何线上参数都必须来自配置，而不是硬编码在策略里。

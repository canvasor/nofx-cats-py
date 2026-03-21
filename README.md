# NOFX CATS Python v2

> CATS = **Constitutional Autonomous Trading System**
> 
> 面向 **NOFX 数据驱动 + Binance USDⓈ-M Futures 执行** 的 Python v2 交易系统蓝图与代码骨架。

## 1. 这版相比 v1 的主要升级

v2 不是“直接实盘版”，但已经把几处最关键的工程缺口补到了 **live_micro 前的可验证形态**：

- 决策层从“遇到第一个信号就返回”升级为 **候选动作收集 → MetaAllocator 排序 → Risk Kernel 审批 → NO_TRADE 回退**。
- 新增 **Crowding Reversal** 策略，与原有 **Trend Following** 并行竞争。
- 风控从“按 gross soft 上限直接估算”升级为 **按剩余 gross headroom** 计算可用名义价值。
- Algo 条件单路由改为使用 **`clientAlgoId`**；普通单仍用 **`newClientOrderId`**。
- 校验器补上 **`closePosition=true` 不能再和 `reduceOnly` 同发**、`MARKET_LOT_SIZE`、`PERCENT_PRICE`、symbol `TRADING` 状态等规则。
- 新增 **灾难止损构造器**，可直接生成 `STOP_MARKET + closePosition=true` 的保命单请求。
- 新增 **UserStreamSession**，自动维护 listenKey keepalive。
- 数据快照从“只写 payload”升级为 **带 source / endpoint / params / fetched_at 的 snapshot envelope**。

## 2. 项目定位

这个仓库不是“一个大模型直接下单”的黑箱，而是一个 **可审计、可回放、可控制、可持续演进** 的自动化交易系统骨架。

### 目标
- 在 **Binance 期货市场** 上执行交易。
- 使用 **NOFX 实时量化数据** 作为 alpha / signal 输入。
- 支持 **趋势、拥挤反转、防守去风险** 等多 regime 策略。
- 以 **先活下来、再稳、最后才是赚** 为设计原则。
- 从一开始就具备 **日志、回放、风控宪法、执行保险丝**。

### 非目标
- 不承诺“每笔都是绝对最优”。
- 不允许模型任意改动风险上限。
- 不做“上线即全自动高杠杆”。
- 不把大模型作为直接下单器。

## 3. 核心设计原则

1. **数据真相分离**
   - NOFX 是 alpha 数据源。
   - Binance 用户流和账户查询才是订单 / 持仓 / 余额的最终真相。

2. **风险内核最高权限**
   - 模型只能提议，风险内核负责批准或拒绝。
   - 任何服务都不能绕过 Risk Kernel 直接下单。

3. **普通单 / 条件单双路由**
   - 普通开平仓：普通 REST 下单。
   - 止损 / 止盈 / 跟踪止损：Algo Order 通道。

4. **无交易也是决策**
   - 数据 stale、连接异常、拥挤极端、回撤超限时，最佳动作常常是空仓。

5. **所有原始数据必须可回放**
   - 从第一天开始落盘 NOFX 原始快照和 Binance 关键事件。
   - 回测、复盘、自学习都基于真实历史事件，而不是事后拼接。

## 4. v2 的开仓主逻辑

### Trend Following
- AI500 / AI300 门控通过
- 15m / 1h / 4h 方向同向
- 机构期货流同向
- Binance + Bybit OI 扩张确认
- funding 未过度拥挤

### Crowding Reversal
- funding 极端
- Query Rank 过热
- Heatmap delta 反向
- 15m 动量衰竭或反转

### MetaAllocator
- 收集所有策略候选动作
- 用统一分数函数排名
- 把 **NO_TRADE** 当成基线动作
- 只把最高分、且经 Risk Kernel 批准的动作往下传递

## 5. 代码结构

```text
nofx-cats-py/
├── README.md
├── pyproject.toml
├── .env.example
├── Makefile
├── docker-compose.dev.yml
├── configs/
├── docs/
├── src/
│   └── cats_py/
│       ├── app/
│       ├── apps/
│       ├── config/
│       ├── connectors/
│       ├── domain/
│       ├── execution/
│       ├── features/
│       ├── infra/
│       ├── journal/
│       ├── regime/
│       ├── risk/
│       ├── services/
│       └── strategies/
└── tests/
```

## 6. 快速开始

### 6.1 安装
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

### 6.2 配置
```bash
cp .env.example .env
cp configs/app.example.yaml configs/app.yaml
cp configs/risk.example.yaml configs/risk.yaml
cp configs/symbols.example.yaml configs/symbols.yaml
```

### 6.3 运行
```bash
python -m cats_py.apps.run_nofx_collector
python -m cats_py.apps.run_decision_engine
python -m cats_py.apps.run_websocket_gateways
python -m cats_py.apps.run_execution_daemon
```

## 7. 当前成熟度

这版适合：
- 架构评审
- 团队分工开发
- shadow / paper
- live_micro 前联调

这版暂不等于：
- 可直接全自动实盘
- 可绕开人工 review 的高风险版本
- 已完成对账、回放、状态机、风控审计的全部生产能力

## 8. 推荐下一步

- 补 Binance 用户流对账状态机
- 补成交后自动挂保命止损的执行编排
- 接入 ClickHouse / PostgreSQL
- 做 replay / walk-forward / shadow vs live 对比
- 只在 BTC / ETH / SOL 上先跑 live_micro

# 开发指导手册

## 1. 开发目标

这个项目的第一版不是“收益最大化版本”，而是 **工程可运行 + 风控可执行 + 数据可回放** 的版本。

## 2. 研发节奏建议

### Sprint 1：连接与配置
交付：
- `settings.py`
- NOFX / Binance REST Client
- Binance WebSocket 三路连接器
- `.env` 与 yaml 配置
- 原始快照落盘

验收标准：
- 可成功拉取 NOFX 核心端点
- 可连接 Binance `/public` `/market` `/private`
- 用户流可自动 keepalive

### Sprint 2：执行与风控基础
交付：
- exchangeInfo 解析
- leverageBracket 解析
- PreTradeValidator
- OrderRouter
- countdown cancel heartbeat
- PositionGuardian

验收标准：
- 普通单与 Algo 单路由正确
- 价格和数量可按 tick/step 对齐
- 无效单会在本地被拒绝
- 每个 symbol 可维护 auto-cancel 心跳

### Sprint 3：特征与决策
交付：
- FeatureEngine
- RegimeEngine
- TrendFollowing sleeve
- RiskKernel
- Decision Journal

验收标准：
- 候选交易可生成
- 拒绝原因清晰
- 审批通过时可给出目标仓位与杠杆建议

### Sprint 4：回放与影子运行
交付：
- Replay Loader
- Shadow 模式
- 绩效统计
- 故障注入测试

验收标准：
- 可回放历史决策
- 可在 live 数据下只记账不下单
- 故障场景可触发 guardian / kill switch

## 3. 代码规范

### 强制要求
- Python 3.12
- 全量 type hints
- 新增代码必须有 pytest
- 不允许在生产路径使用 `print`
- 所有异常必须具备上下文日志

### 推荐工具
- `ruff`：lint + format
- `mypy`：静态类型检查
- `pytest` + `pytest-asyncio`
- `pre-commit`

## 4. 分层约束

### connector 层
- 不知道策略，不做判断。
- 只负责把外部协议转成内部数据结构。

### strategy 层
- 不直接调用交易所下单。
- 只返回候选动作。

### risk 层
- 唯一有权 veto 的地方。
- 不负责网络调用。

### execution 层
- 不自行计算策略信号。
- 只执行审批通过的动作。

## 5. 分支策略

建议：
- `main`：受保护
- `develop`
- `feature/<module-name>`
- `hotfix/<issue>`

提交规范示例：
- `feat: add binance algo order router`
- `fix: normalize nofx funding rate to ratio`
- `test: cover leverage bracket validator`

## 6. 测试策略

### 单元测试
覆盖：
- NOFX 字段标准化
- tick / step 对齐
- 风控 veto 逻辑
- order router 路由

### 集成测试
覆盖：
- REST client 签名
- WS 重连
- 预检器 + 路由器 + mock exchange

### 仿真测试
覆盖：
- 缺失 user stream
- stale 数据
- 大幅滑点
- 连续 reject
- countdown auto cancel

## 7. 运行模式

### `shadow`
- 读实时数据
- 生成决策
- 不发真实订单

### `paper`
- 模拟成交与 PnL
- 仍不碰真钱

### `live_micro`
- 只开极小仓位
- 只允许 Core 池

### `live`
- 通过风控审批后，逐步放量

## 8. 配置管理

### 绝对禁止
- 把 API key 写入代码
- 把 symbol 白名单写死在策略文件
- 把风险上限散落在多个模块

### 必须集中管理
- `.env`：密钥、host、开关
- `configs/app.yaml`
- `configs/risk.yaml`
- `configs/symbols.yaml`

## 9. 监控与告警

第一版至少需要：
- Connector 连接状态
- listenKey 剩余时间
- user stream 最后事件时间
- feature staleness
- 下单 reject 数
- Guardian 告警
- Kill switch 状态

## 10. 上线前检查清单

- [ ] 普通单和 Algo 单路由测试通过
- [ ] 风险上限从配置读入
- [ ] 所有开仓路径都能自动挂灾难止损
- [ ] 可在 120 秒内自动撤掉挂单
- [ ] 数据 stale 能阻止新开仓
- [ ] 用户流掉线会触发保护
- [ ] 具备 shadow / paper / live_micro 三种模式

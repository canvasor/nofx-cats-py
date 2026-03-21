# NOFX CATS 分阶段项目清单（开发 / 联调 / Testnet / Live Micro）

> 适用范围：NOFX 数据驱动、Binance USDⓈ-M Futures 执行的 Python 版自治交易系统  
> 建议定位：先达成 **live_micro 可控上线**，不要直接 full-auto full-size。  
> 使用方式：把这份文件直接放进项目仓库，作为 milestone、周会跟踪、上线审批和复盘模板。

---

## 0. 使用规则

- 每一项都要有负责人、目标日期、状态。
- 任一阶段未满足“阶段退出门槛”，不得进入下一阶段。
- 遇到一票否决项，默认回退到上一阶段处理。
- 这份清单同时服务于开发、测试、风控、运维四类角色。

### 状态建议

- [ ] 未开始
- [~] 进行中
- [x] 已完成
- [!] 阻塞

### 字段模板

复制使用：

```md
- [ ] 任务名称
  - Owner:
  - Due:
  - Status:
  - Notes:
```

---

## 1. 阶段一：开发

### 1.1 目标

完成核心代码骨架，确保数据、风控、执行、日志、测试都具备可联调能力。

### 1.2 清单

#### A. 项目基础设施

- [ ] 建立统一项目结构：`connectors / services / strategies / risk / execution / infra / apps / tests`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 完成配置分层：`base / dev / testnet / prod`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 接入 secrets 管理方案，不在仓库中存放真实密钥
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 建立日志规范：结构化日志、trace id、decision id、order id
  - Owner:
  - Due:
  - Status:
  - Notes:

#### B. NOFX 数据侧

- [ ] 完成 NOFX 连接器，支持 query `auth` 和 Bearer 鉴权
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 实现限流、重试、指数退避、熔断
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 建立字段标准化字典
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 统一处理字段量纲：`price_delta / price_change` 作为 ratio，`oi_delta_percent / funding_rate` 作为已乘 100 的百分数
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 建立统一 symbol 映射：`BTC`、`BTCUSDT`、NOFX `pair`、Binance `symbol`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 原始快照落盘：`source / endpoint / params / fetched_at / latency / status_code / payload / schema_version`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 归一化结果与原始快照分层存储
  - Owner:
  - Due:
  - Status:
  - Notes:

#### C. Binance 执行基础

- [ ] 完成 REST client：签名、时间同步、重试、错误分类
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 完成 WebSocket 拆分：`/public`、`/market`、`/private`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 完成 listenKey 生命周期管理
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 完成普通单与 Algo 条件单双路由
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 保证 Algo 单使用 `clientAlgoId`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 完成 `countdownCancelAll` 保险丝封装
  - Owner:
  - Due:
  - Status:
  - Notes:

#### D. 预检与风控

- [ ] 完成 Pre-Trade Validator
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 校验 `tickSize / stepSize / LOT_SIZE / MARKET_LOT_SIZE / MIN_NOTIONAL / PERCENT_PRICE / marketTakeBound / triggerProtect`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 接入 `leverageBracket` 校验
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 接入 `apiTradingStatus` 检查
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 完成风险宪法配置：单笔风险、日周熔断、gross exposure、cluster cap、max positions
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 完成 `NO_TRADE` 候选动作
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 已有持仓时按 `remaining gross headroom` 计算新增风险预算
  - Owner:
  - Due:
  - Status:
  - Notes:

#### E. 决策与策略

- [ ] 完成候选池构建：AI500、AI300、其他白名单来源
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] Regime Engine 输出至少：`TREND / RANGE / CROWDING / DEFENSE / UNKNOWN`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] Decision Engine 从“顺序执行”改为“候选动作打分排序”
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 每笔决策都生成 journal：why this symbol / why now / why this size / why not trade
  - Owner:
  - Due:
  - Status:
  - Notes:

#### F. 测试与质量

- [ ] 单元测试覆盖：normalizer、validator、risk kernel、order router、decision engine
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 关键路径异常测试：空字段、stale、精度对齐失败、签名失败、拒单
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] lint / format / type check / pytest 进入 CI
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] README、架构文档、开发指导、运行说明齐全
  - Owner:
  - Due:
  - Status:
  - Notes:

### 1.3 阶段退出门槛

- [ ] 本地开发环境一键启动成功
- [ ] 单元测试通过
- [ ] 所有核心服务可启动
- [ ] 决策链路能在 mock 数据下完整跑通
- [ ] 下单前校验、风险审批、订单路由、日志落盘全链条打通

### 1.4 一票否决项

- [ ] 没有统一 symbol 映射
- [ ] 没有原始快照
- [ ] 普通单和 Algo 条件单仍混用
- [ ] 风险硬上限可被模型直接修改

---

## 2. 阶段二：联调

### 2.1 目标

把各模块拼起来，确认真实接口、真实状态机、真实告警都能协同工作。

### 2.2 清单

#### A. 数据链路联调

- [ ] NOFX 采集器稳定运行，快照连续写入
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 归一化特征能被决策引擎实时读取
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] stale 检测能够触发风控 veto
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] replay 能根据历史快照还原某笔决策输入
  - Owner:
  - Due:
  - Status:
  - Notes:

#### B. 账户与状态机联调

- [ ] `/private` 用户流事件能驱动本地订单和持仓状态机
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] `ORDER_TRADE_UPDATE / ACCOUNT_UPDATE / ALGO_UPDATE` 全量落盘
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 用户流增量与 `positionRisk` 定时全量对账一致
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 断线重连后可自动重建：挂单、条件单、持仓、余额
  - Owner:
  - Due:
  - Status:
  - Notes:

#### C. 执行与保护单联调

- [ ] 开仓成交后自动挂保命止损
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] `closePosition=true` 相关参数限制全部生效
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] `ALGO_UPDATE` 拒单、取消、触发事件可正确处理
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] `countdownCancelAll` 心跳正常续期，失联时能自动撤挂单
  - Owner:
  - Due:
  - Status:
  - Notes:

#### D. 监控与告警联调

- [ ] WebSocket 断开、listenKey 续期失败、NOFX stale、用户流 stale、保护单缺失都有告警
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 告警能触达到人：IM / 邮件 / 短信至少一条链路
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 严重告警能触发禁止新开仓或安全模式
  - Owner:
  - Due:
  - Status:
  - Notes:

### 2.3 阶段退出门槛

- [ ] 所有服务在联调环境稳定运行
- [ ] 用户流和本地状态机对账通过
- [ ] 成交后保护单自动挂出通过
- [ ] 快照、日志、告警三条线均正常
- [ ] 至少完成一次断线恢复演练

### 2.4 一票否决项

- [ ] 订单成交后不能稳定挂出保命止损
- [ ] 用户流丢事件后无法自动恢复
- [ ] `ALGO_UPDATE` 未接入或处理不完整
- [ ] 风险 veto 触发后系统仍继续下单

---

## 3. 阶段三：Testnet

### 3.1 目标

在测试环境验证完整交易生命周期和异常场景处理，不花真钱先把执行问题跑出来。

### 3.2 清单

#### A. 全链路演练

- [ ] 用 testnet 跑通：采集 → 特征 → 决策 → 风控 → 下单 → 成交 → 保护单 → 对账 → 复盘
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 只开放小范围 symbol，先验证核心路径
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 成交日志、保护单日志、风控日志三者一致
  - Owner:
  - Due:
  - Status:
  - Notes:

#### B. 异常场景演练

- [ ] WebSocket 断线重连演练
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] listenKey 失效演练
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] NOFX stale 演练
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 连续 reject 演练
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 保护单挂单失败演练
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 手动 kill switch 演练
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] `countdownCancelAll` 失联撤单演练
  - Owner:
  - Due:
  - Status:
  - Notes:

#### C. 执行质量验证

- [ ] 记录预估滑点与实际滑点
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 记录成交延迟、撤单延迟、保护单建立延迟
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 记录不同波动阶段的失败率和异常率
  - Owner:
  - Due:
  - Status:
  - Notes:

#### D. Go/No-Go 评审准备

- [ ] 输出 testnet 阶段报告
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 整理所有 blocker 与已知限制
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 给出 live_micro 初始参数建议：symbol 白名单、单笔风险、杠杆上限、max positions
  - Owner:
  - Due:
  - Status:
  - Notes:

### 3.3 阶段退出门槛

- [ ] testnet 全链路通过
- [ ] 关键异常演练通过
- [ ] kill switch 生效
- [ ] 保护单与对账链路稳定
- [ ] 输出正式测试报告并通过评审

### 3.4 一票否决项

- [ ] 未做断线 / stale / reject / kill switch 演练
- [ ] testnet 上保护单流程仍不稳定
- [ ] 无法解释对账差异
- [ ] 无法给出 live_micro 的保守参数

---

## 4. 阶段四：Live Micro

### 4.1 目标

用真钱极小仓位验证生产环境的真实滑点、真实状态、真实告警和真实运维能力。

### 4.2 清单

#### A. 上线范围控制

- [ ] 只开放 `BTC / ETH / SOL`
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 只开放 1 到 2 个策略
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 只允许低杠杆和极小仓位
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 单笔风险、gross exposure、max positions 采用最保守档位
  - Owner:
  - Due:
  - Status:
  - Notes:

#### B. 生产运行保障

- [ ] on-call 值班安排落地
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 生产监控、告警、日志看板齐全
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 上线窗口避开重大宏观事件与极端波动窗口
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 回滚流程和责任人明确
  - Owner:
  - Due:
  - Status:
  - Notes:

#### C. 观察期要求

- [ ] 每日复盘：信号、成交、滑点、保护单、告警、对账差异
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 每周复盘：策略表现、拒单率、stale 次数、断线次数、风险 veto 命中率
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 任何严重告警后必须做 incident review
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 观察期内禁止频繁手改参数
  - Owner:
  - Due:
  - Status:
  - Notes:

#### D. 放量前条件

- [ ] 至少完成一段稳定观察期
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 高波动窗口表现可接受
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 保护单、对账、kill switch 全部经生产验证
  - Owner:
  - Due:
  - Status:
  - Notes:
- [ ] 风控委员会或上线审批人签字通过
  - Owner:
  - Due:
  - Status:
  - Notes:

### 4.3 阶段退出门槛

- [ ] live_micro 期间无关键状态错乱
- [ ] 无未解释的仓位差异
- [ ] 无保护单缺失
- [ ] 无无法恢复的断线事故
- [ ] 具备继续小幅放量的充分证据

### 4.4 一票否决项

- [ ] 生产上出现保护单缺失
- [ ] 生产上出现未解释的持仓差异
- [ ] 用户流长时间 stale 未被系统阻断
- [ ] 发生严重事故后没有复盘与修复闭环

---

## 5. 上线审批模板

### 5.1 参与角色

- [ ] 数据负责人
- [ ] 执行负责人
- [ ] 风控负责人
- [ ] 策略负责人
- [ ] 运维 / SRE 负责人
- [ ] 最终审批人

### 5.2 审批结论

- [ ] 允许进入下一阶段
- [ ] 有条件进入下一阶段
- [ ] 不允许进入下一阶段

### 5.3 审批备注

```md
日期：
结论：
阻塞项：
风险备注：
下一次复审时间：
```

---

## 6. 建议的最小上线标准

### 允许进入 live_micro 的最低标准

- [ ] testnet 全链路通过
- [ ] 用户流守护与 `positionRisk` 对账通过
- [ ] 开仓后能稳定挂出交易所侧保命止损
- [ ] NOFX 快照可回放
- [ ] `countdownCancelAll` 保险丝正常
- [ ] kill switch 已演练
- [ ] 只开放核心币、低杠杆、小仓位

### 仍然不建议放量的情形

- [ ] 只做过 happy path
- [ ] 没做高波动窗口观察
- [ ] 没做断线 / stale / reject 演练
- [ ] 观察期太短
- [ ] 生产 incident 还未闭环

---

## 7. 总结

真正长期能活的自动交易系统，优先级永远是：

**执行内核 > 保护单 > 对账与真相源 > 快照与回放 > 风控宪法 > 策略收益**

先把系统做成：

- 能连上
- 不乱下
- 出错能停
- 出事能还原
- 长期可运维

再去追求更高收益和更复杂的自治能力。

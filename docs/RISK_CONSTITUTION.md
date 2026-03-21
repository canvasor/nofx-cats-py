# 风控宪法

> 风控宪法的原则：**模型只能申请风险，不能创造风险边界。**

## 1. 宪法层级

### L0：全局硬限制（不可由模型修改）
- 最大单笔风险
- 最大日内回撤
- 最大周回撤
- 最大 gross exposure
- 最大同簇暴露
- 最大 symbol notional
- 最小强平缓冲
- kill switch 条件

### L1：策略层参数（可配置，不允许在线自改）
- 不同 regime 的风险预算
- 不同 symbol tier 的杠杆上限
- 最大持仓时长
- time stop

### L2：模型层参数（允许校准）
- 因子权重
- 阈值
- sleeve 分配比例
- 置信度映射

## 2. 第一版建议值

```yaml
trade_risk_bps_default: 35
trade_risk_bps_max: 75
daily_drawdown_soft_pct: -1.5
daily_drawdown_hard_pct: -3.0
weekly_drawdown_hard_pct: -6.0
gross_exposure_soft: 1.25
gross_exposure_hard: 3.0
max_open_positions: 4
min_liq_buffer_pct: 18
```

## 3. Symbol Tier 建议

### Core
- BTC
- ETH
- SOL

约束：
- 最大杠杆 3x
- 单 symbol notional 占权益不超过 25%

### Liquid Alt
- 流动性稳定、盘口较厚的主流币

约束：
- 最大杠杆 2x
- 单 symbol notional 占权益不超过 12%

### Experimental
- 默认禁用
- 仅 shadow / paper 模式观察

## 4. 开仓 veto 条件

任一满足即拒绝：
- NOFX 数据 stale
- user stream 失联
- 账户模式与预期不一致
- 超过最大持仓数
- 日内或周回撤超限
- symbol tier 未授权
- stop distance 不可用
- 预估滑点超预算
- leverage bracket 不通过
- 强平缓冲不足
- 订单 reject 异常增多

## 5. 仓位计算原则

```text
target_notional =
min(
  equity * gross_budget,
  equity * trade_risk_budget / stop_distance_pct,
  symbol_tier_cap,
  leverage_bracket_cap * 0.8
)
```

## 6. 灾难保护原则
- 所有新开仓必须在成交后尽快存在保护性退出。
- 执行系统异常时，不应继续新增风险。
- 挂单失联时，应通过交易所倒计时撤单机制清掉悬挂风险。

## 7. Kill Switch 触发建议
- 用户流 stale 超过阈值
- 两轮以上 NOFX stale
- 连续 reject 异常
- 订单状态机不一致
- 组合回撤触发硬阈值
- 关键配置校验失败

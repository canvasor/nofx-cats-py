# 数据契约与标准化

## 1. 内部统一量纲

内部统一使用以下标准：

- 百分比 / 涨跌幅 / funding / OI 百分比：**ratio**
  - 例：5% => `0.05`
- 金额：USDT
- 时间：UTC `datetime`
- 价格与数量：`Decimal`

## 2. NOFX 字段标准化规则

### 已经是 decimal ratio 的字段
这些字段可以直接视为内部 ratio：
- `price_delta`
- `price_change.{duration}`

### 已经是 ×100 百分数字面值的字段
这些字段需要 `/ 100` 才能转成内部 ratio：
- `oi_delta_percent`
- `price_delta_percent`
- `funding_rate`

### 纯金额字段
- `future_flow`
- `spot_flow`
- `amount`
- `oi_delta_value`

### 时间字段
- `start_time`：秒时间戳
- `next_funding_time`：通常是毫秒时间戳
- `timestamp`：通常是毫秒时间戳

标准化时必须自动识别秒 / 毫秒。

## 3. Binance 规则缓存

### `exchangeInfo`
内部提取：
- `PRICE_FILTER.tickSize`
- `LOT_SIZE.stepSize`
- `LOT_SIZE.minQty`
- `MIN_NOTIONAL.notional`
- `PERCENT_PRICE`
- `marketTakeBound`
- `triggerProtect`

### `leverageBracket`
内部提取：
- `initialLeverage`
- `notionalCap`
- `notionalFloor`
- `maintMarginRatio`

## 4. 内部 FeatureVector 字段建议

```python
FeatureVector(
    symbol="BTCUSDT",
    ts=datetime,
    ai500_score=74.1,
    ai300_level_score=0.8,
    price_change_15m=0.006,
    price_change_1h=0.013,
    price_change_4h=0.031,
    inst_future_flow_15m=125000.0,
    inst_future_flow_1h=442000.0,
    inst_future_flow_4h=1800000.0,
    retail_future_flow_1h=-12000.0,
    oi_binance_1h=0.021,
    oi_bybit_1h=0.018,
    funding_rate=0.0009,
    heatmap_delta=23000000.0,
    crowd_query_rank=5,
    stale_seconds=3.2,
)
```

## 5. 数据质量评分建议

第一版建议输出：
- `staleness_score`
- `completeness_score`
- `freshness_ok`
- `execution_safe`

## 6. Symbol 规范化

内部统一采用：
- 交易执行 symbol：`BTCUSDT`
- 可选展示 symbol：`BTC`
- 若 NOFX 返回 `BTC` / `BTCUSDT` / `pair`，统一映射到执行 symbol。

必须维护：
- `symbol -> venue symbol`
- `venue symbol -> canonical symbol`

## 7. 事件存储最小字段集

### 原始 NOFX 快照
- source endpoint
- request params
- fetched_at
- raw payload

### 原始 Binance 用户事件
- event type
- received_at
- raw payload
- connection id
- listenKey

### 决策日志
- decision_id
- symbol
- regime
- side
- rationale
- risk approval
- order request
- order result

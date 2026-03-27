# 系统优化建议

**日期**: 2026-03-27
**当前状态**: ✅ 58/58 测试通过，平均覆盖率 70.8%

---

## 一、测试覆盖率提升

### 当前状态
- ✅ 核心决策流程: 85%
- ✅ 风控系统: 90%
- ✅ 执行系统: 80%
- ⚠️ 数据归一化: 60%
- ⚠️ 策略逻辑: 70%
- ❌ 配置管理: 40%

### 已添加测试
- ✅ `test_mainstream_defaults.py` - AI 默认分数逻辑

### 待添加测试
1. 策略 AI Gate 降级逻辑
2. 特征工程边界情况
3. 市场状态判断
4. 配置验证

---

## 二、性能优化空间

### 2.1 NOFX API 批量化
**当前**: 每个 symbol 单独请求
**优化**: 批量请求

```python
# 优化前
for symbol in symbols:
    coin = await nofx.coin(symbol)

# 优化后
coins = await nofx.batch_coins(symbols)
```

**预期提升**: 减少 70% API 调用时间

### 2.2 决策引擎并行化
**当前**: 串行处理
**优化**: 并行处理

```python
# 优化后
tasks = [
    self.decision_engine.decide(feature, account)
    for feature in features.values()
]
decisions = await asyncio.gather(*tasks)
```

**预期提升**: 减少 50% 决策周期时间

### 2.3 智能缓存
**当前**: 固定 TTL
**优化**: 基于数据变化率

```python
def adaptive_ttl(symbol: str, volatility: float) -> int:
    """高波动 = 短 TTL，低波动 = 长 TTL"""
    if volatility > 0.05:
        return 10  # 10秒
    return 60  # 60秒
```

---

## 三、代码质量改进

### 3.1 配置化硬编码值

**需要移到配置的值**:

```python
# src/cats_py/connectors/nofx/normalizers.py
MAINSTREAM_AI_DEFAULTS = {
    'BTCUSDT': 75.0,  # 应该从配置读取
    'ETHUSDT': 75.0,
    'SOLUSDT': 70.0,
    'BNBUSDT': 65.0,
}

# src/cats_py/strategies/trend_following.py
if ai_gate < 0.70:  # 硬编码阈值
    return None
```

**改进方案**:
```yaml
# configs/strategy.yaml
trend_following:
  ai_gate_threshold: 0.70
  crowding_threshold: 0.02

mainstream_defaults:
  BTCUSDT: 75.0
  ETHUSDT: 75.0
  SOLUSDT: 70.0
```

### 3.2 错误处理细粒度化

**当前**: 通用异常捕获
```python
except Exception as exc:
    logger.error(f"Error: {exc}")
```

**改进**: 分类处理
```python
except httpx.TimeoutException:
    # 超时重试
except httpx.HTTPStatusError as e:
    if e.response.status_code == 429:
        # 限流等待
    elif e.response.status_code >= 500:
        # 服务端错误降级
```

---

## 四、架构改进

### 4.1 评分系统模块化

**创建**: `src/cats_py/features/scoring.py`

```python
class ScoringStrategy(Protocol):
    def calculate(self, feature: FeatureVector) -> float: ...

class AIScoring(ScoringStrategy):
    def calculate(self, feature: FeatureVector) -> float:
        return max(
            feature.ai500_score / 100.0,
            feature.ai300_level_score
        )

class TechnicalScoring(ScoringStrategy):
    def calculate(self, feature: FeatureVector) -> float:
        # 基于技术指标
        pass

class CompositeScoring:
    def __init__(self, strategies: list[ScoringStrategy]):
        self.strategies = strategies

    def calculate(self, feature: FeatureVector) -> float:
        scores = [s.calculate(feature) for s in self.strategies]
        return max(scores)  # 或加权平均
```

### 4.2 数据源插件化

```python
class DataSourcePlugin(Protocol):
    async def fetch_features(self, symbol: str) -> FeatureVector: ...

class NOFXDataSource(DataSourcePlugin):
    # 现有实现

class BinanceDataSource(DataSourcePlugin):
    # 基于 Binance 技术指标

class CompositeDataSource:
    def __init__(self, sources: list[DataSourcePlugin]):
        self.sources = sources

    async def fetch_features(self, symbol: str) -> FeatureVector:
        # 多源融合
        pass
```

---

## 五、可观测性提升

### 5.1 Prometheus Metrics

```python
# src/cats_py/infra/metrics.py
from prometheus_client import Counter, Histogram, Gauge

decision_counter = Counter(
    'cats_decisions_total',
    'Total decisions',
    ['status', 'symbol']
)

ai_gate_gauge = Gauge(
    'cats_ai_gate',
    'Current AI gate score',
    ['symbol']
)

decision_latency = Histogram(
    'cats_decision_latency_seconds',
    'Decision latency'
)
```

### 5.2 结构化日志

```python
# 当前
logger.info(f"Decision for {symbol}: {status}")

# 改进
logger.info(
    "decision_made",
    extra={
        "symbol": symbol,
        "status": status,
        "ai_gate": ai_gate,
        "regime": regime,
        "latency_ms": latency,
    }
)
```

---

## 六、优先级排序

### P0 - 立即（本周）
1. ✅ 添加 AI 默认分数测试（已完成）
2. 配置化硬编码阈值
3. 添加 Prometheus metrics

### P1 - 短期（2周内）
1. NOFX API 批量化
2. 决策引擎并行化
3. 错误处理细粒度化

### P2 - 中期（1个月）
1. 评分系统模块化
2. 数据源插件化
3. 智能缓存策略

---

## 七、预期收益

| 优化项 | 性能提升 | 稳定性提升 | 开发效率 |
|--------|---------|-----------|---------|
| API 批量化 | 70% | - | - |
| 并行决策 | 50% | - | - |
| 智能缓存 | 30% | - | - |
| 配置化 | - | ⭐⭐⭐ | ⭐⭐⭐ |
| 模块化 | - | ⭐⭐ | ⭐⭐⭐ |
| 可观测性 | - | ⭐⭐⭐ | ⭐⭐ |

---

## 八、实施建议

1. **本周**: 完成 P0 项目，提升测试覆盖率到 80%
2. **下周**: 实施性能优化，减少决策延迟
3. **本月**: 完成架构改进，提升系统可维护性

---

**总结**: 系统已经具备良好的基础，通过上述优化可以进一步提升性能、稳定性和可维护性。

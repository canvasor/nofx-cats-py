# NOFX CATS 交易系统诊断报告

**生成时间**: 2026-03-27
**分析周期**: 过去 2 天运行数据
**总决策数**: 57,540 次
**实际交易数**: 0 次

---

## 执行摘要

系统运行两天未下单的**根本原因**已确认：

**核心问题：BTC、ETH、SOL 等所有核心交易标的的 AI500 和 AI300 分数均为 0，导致所有策略的 AI Gate 检查失败。**

---

## 一、问题定位

### 1.1 症状分析

通过分析 57,540 条决策日志，发现：

- **100% 的决策**都是 `NO_TRADE`
- **100% 的市场状态**被判定为 `RANGE`（震荡市）
- **100% 的决策**被以下原因拒绝：
  - `trend_following: ai gate below threshold`
  - `range_reversion: ai gate below threshold`
  - `crowding_reversal: symbol is not hot enough`

### 1.2 根因确认

通过实时查询 NOFX API，发现：

```
BTCUSDT:
  AI500 原始分数: 0.00
  AI300 Level 分数: 0.00
  AI Gate (实际值): 0.0000

ETHUSDT:
  AI500 原始分数: 0.00
  AI300 Level 分数: 0.00
  AI Gate (实际值): 0.0000

SOLUSDT:
  AI500 原始分数: 0.00
  AI300 Level 分数: 0.00
  AI Gate (实际值): 0.0000
```

**所有核心币种的 AI 分数都是 0！**

---

## 二、技术分析

### 2.1 策略阈值设计

系统中三个策略的 AI Gate 阈值：

| 策略 | AI Gate 阈值 | 当前实际值 | 结果 |
|------|-------------|-----------|------|
| Trend Following | 0.70 | 0.00 | ✗ 失败 |
| Range Reversion | 0.55 | 0.00 | ✗ 失败 |
| Crowding Reversal | 无明确阈值 | 0.00 | ✗ 失败 |

### 2.2 AI Gate 计算逻辑

代码位置：`src/cats_py/strategies/trend_following.py:12-13`

```python
ai_gate = max(feature.ai500_score / 100.0, feature.ai300_level_score)
if ai_gate < 0.70:
    return None
```

**计算公式**：
```
AI Gate = max(AI500分数 / 100, AI300 Level分数)
```

**当前情况**：
```
AI Gate = max(0.00 / 100, 0.00) = 0.00
```

由于 `0.00 < 0.70` 和 `0.00 < 0.55`，所有策略都在第一道门禁就被拒绝。

### 2.3 数据流分析

```
NOFX API
  ↓
normalize_coin_snapshot()
  ↓ ai500_score = 0.0
  ↓ ai300_level_score = 0.0
  ↓
FeatureVector
  ↓
Strategy.generate()
  ↓ ai_gate = 0.0
  ↓ if ai_gate < threshold: return None
  ↓
NO_TRADE
```

---

## 三、问题根源分析

### 3.1 可能的原因

1. **NOFX 数据源问题**（最可能）
   - BTC/ETH/SOL 不在 AI500 榜单中
   - BTC/ETH/SOL 不在 AI300 榜单中
   - NOFX API 返回的数据结构变化
   - API 权限或订阅问题

2. **配置问题**
   - Symbol 映射错误（如 `BTC` vs `BTCUSDT`）
   - API Key 权限不足

3. **代码逻辑问题**
   - AI 分数解析逻辑错误
   - 数据归一化问题

### 3.2 验证发现

从 AI300 返回数据看，系统**能够**获取到其他币种的分数：
```
RIVERUSDT    : 1.00
BLUAIUSDT    : 1.00
TRXUSDT      : 1.00
PEPEUSDT     : 1.00
```

但 BTC、ETH、SOL 这些**核心主流币**不在榜单中，分数为 0。

**关键发现**：NOFX 的 AI500/AI300 榜单可能**不包含**或**不优先推荐** BTC/ETH/SOL 等主流币种。

---

## 四、架构设计问题

### 4.1 设计缺陷

当前架构存在**致命缺陷**：

```
系统设计假设：
  "所有交易标的都会有 AI500/AI300 分数"

实际情况：
  "BTC/ETH/SOL 等主流币不在 NOFX AI 榜单中"
```

### 4.2 配置与数据源不匹配

**配置文件**（`configs/symbols.example.yaml`）定义：
```yaml
core:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT
```

**NOFX 数据源**实际推荐：
- RIVERUSDT
- BLUAIUSDT
- TRXUSDT
- PEPEUSDT
- FARTCOINUSDT

**矛盾**：系统配置要交易主流币，但数据源只给山寨币打分。

---

## 五、解决方案

### 5.1 短期方案（立即可行）

#### 方案 A：降低 AI Gate 阈值（不推荐）

```python
# 修改 src/cats_py/strategies/trend_following.py
ai_gate = max(feature.ai500_score / 100.0, feature.ai300_level_score)
if ai_gate < 0.10:  # 从 0.70 降低到 0.10
    return None
```

**优点**：快速
**缺点**：违背设计初衷，可能导致低质量信号

#### 方案 B：为主流币设置默认分数（推荐）

```python
# 修改 src/cats_py/connectors/nofx/normalizers.py
def get_default_ai_score(symbol: str) -> float:
    """为主流币种设置默认 AI 分数"""
    mainstream = {
        'BTCUSDT': 0.75,
        'ETHUSDT': 0.75,
        'SOLUSDT': 0.70,
    }
    return mainstream.get(symbol, 0.0)

# 在 normalize_coin_snapshot 中使用
ai500_score = float(ai500.get("score", 0.0) or 0.0)
if ai500_score == 0.0:
    ai500_score = get_default_ai_score(symbol) * 100.0
```

**优点**：保持策略逻辑不变，为主流币提供合理默认值
**缺点**：需要手动维护主流币列表

#### 方案 C：使用 NOFX 推荐的币种（最符合设计）

修改 `configs/symbols.yaml`：
```yaml
core:
  - RIVERUSDT
  - BLUAIUSDT
  - TRXUSDT

liquid_alt:
  - PEPEUSDT
  - FARTCOINUSDT
```

**优点**：完全符合 NOFX 数据源设计
**缺点**：交易山寨币风险更高

### 5.2 中期方案（1-2周）

#### 方案 D：多数据源融合

```python
# 添加备用评分机制
def calculate_composite_score(feature: FeatureVector) -> float:
    """综合评分：AI分数 + 技术指标"""
    ai_score = max(feature.ai500_score / 100.0, feature.ai300_level_score)
    
    # 如果 AI 分数为 0，使用技术指标替代
    if ai_score == 0.0:
        # 基于趋势强度、流动性、波动率的评分
        trend_strength = abs(feature.trend_score)
        flow_strength = abs(feature.flow_score) / 1000000.0  # 归一化
        composite = min(0.8, trend_strength * 10 + flow_strength)
        return composite
    
    return ai_score
```

**优点**：不依赖单一数据源，更稳健
**缺点**：需要调参和回测

### 5.3 长期方案（1个月+）

#### 方案 E：重新设计 Universe 选择逻辑

```
当前逻辑：
  配置文件定义 → 固定交易池

改进逻辑：
  NOFX AI榜单 → 动态筛选 → 流动性过滤 → 交易池
```

**实现**：
1. 从 AI500/AI300 中选择分数 > 0.6 的币种
2. 过滤掉流动性不足的币种
3. 限制最大持仓数量
4. 动态调整交易池

---

## 六、推荐行动方案

### 立即执行（今天）

**选择方案 B + 方案 C 的混合方案**：

1. **修改代码**：为 BTC/ETH/SOL 设置默认 AI 分数 0.75
2. **修改配置**：添加 NOFX 推荐的高分币种到 liquid_alt
3. **重启系统**：验证是否能产生交易信号

### 本周完成

1. **回测验证**：使用历史数据验证方案 B 的有效性
2. **监控告警**：添加 AI 分数为 0 的告警
3. **文档更新**：在 docs/ 中说明 AI Gate 的设计逻辑

### 下月规划

1. **实现方案 D**：多数据源融合评分
2. **实现方案 E**：动态 Universe 选择
3. **优化策略**：基于实际交易数据调整阈值

---

## 七、架构改进建议

### 7.1 数据层改进

```
当前问题：
  - 单一数据源依赖
  - 缺少数据质量检查
  - 没有降级策略

改进方向：
  - 多数据源融合（NOFX + Binance + 技术指标）
  - 数据质量评分机制
  - 降级策略（AI分数缺失时的备用方案）
```

### 7.2 策略层改进

```
当前问题：
  - AI Gate 是硬性门槛（0分直接拒绝）
  - 策略之间没有互补性

改进方向：
  - 软性评分机制（低分降低仓位，而非完全拒绝）
  - 策略分层（AI驱动策略 + 技术指标策略）
```

### 7.3 配置层改进

```
当前问题：
  - 配置与数据源不匹配
  - 缺少配置验证

改进方向：
  - 启动时验证配置的币种是否有数据
  - 提供配置生成工具（基于 NOFX 实时榜单）
```

---

## 八、风险评估

### 8.1 当前风险

| 风险 | 严重程度 | 影响 |
|------|---------|------|
| 数据源单点依赖 | 高 | NOFX 数据异常导致系统完全停止交易 |
| 配置与数据不匹配 | 高 | 系统配置的币种无法交易 |
| 缺少降级策略 | 中 | 数据缺失时无备用方案 |
| 缺少监控告警 | 中 | 问题发生后无法及时发现 |

### 8.2 方案风险

| 方案 | 风险 | 缓解措施 |
|------|------|---------|
| 方案 B（默认分数） | 主观性强，可能不准确 | 保守设置默认值，定期回测调整 |
| 方案 C（山寨币） | 流动性风险、波动风险 | 严格控制仓位，设置更严格止损 |
| 方案 D（多源融合） | 复杂度增加 | 充分测试，逐步上线 |

---

## 九、总结

### 核心发现

1. **系统运行正常**，决策引擎、风控、数据采集都在工作
2. **数据源问题**：BTC/ETH/SOL 的 AI 分数为 0
3. **设计缺陷**：系统假设所有币种都有 AI 分数，但实际不是

### 关键指标

- 总决策数：57,540
- 交易数：0
- NO_TRADE 率：100%
- 主要拒绝原因：AI Gate 未通过（100%）

### 下一步

**立即行动**：
1. 实施方案 B（为主流币设置默认分数）
2. 添加 NOFX 高分币种到配置
3. 重启系统验证

**预期结果**：
- 系统开始产生交易信号
- 能够在 BTC/ETH/SOL 或 NOFX 推荐币种上开仓

---

**报告生成时间**: 2026-03-27  
**诊断工具**: `diagnose_no_trades.py`, `check_ai_scores.py`  
**数据来源**: `data/paper_decision_log.jsonl` (57,540 条记录)

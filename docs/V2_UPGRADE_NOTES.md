# NOFX CATS Python v2 Upgrade Notes

## 本次升级清单

- DecisionEngine 改为 candidate ranking + NO_TRADE
- 新增 MetaAllocator
- 新增 CrowdingReversalStrategy
- RiskKernel 改用 remaining gross headroom
- OrderRouter 对 Algo Order 使用 clientAlgoId
- Validator 增加 closePosition/reduceOnly、MARKET_LOT_SIZE、PERCENT_PRICE、status 校验
- PositionGuardian 新增灾难止损构造与提交通道
- 新增 UserStreamSession keepalive
- JsonlStorage 新增 snapshot envelope
- NOFX collector 落原始快照 + ai300/query_rank 融合

## 仍然未完成的部分

- 用户流与 positionRisk 的生产级对账循环
- 开仓成交后自动落保护单的完整状态机
- ClickHouse / PostgreSQL 正式表结构
- 回放引擎 / walk-forward / champion-challenger
- 组合层相关性约束与 cluster cap
- 更细粒度的执行滑点模型

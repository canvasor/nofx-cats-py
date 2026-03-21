# 官方参考

以下文档是本项目骨架设计时依赖的关键官方约束。

## NOFX
- NOFX Data API  
  https://nofxos.ai/api-docs

重点使用：
- 鉴权方式
- 30 req/s 限流
- `ai500/*`
- `ai300/*`
- `coin/{symbol}`
- `funding-rate/*`
- `heatmap/*`
- `query-rank/list`

## Binance USDⓈ-M Futures
- Important WebSocket Change Notice  
  https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Important-WebSocket-Change-Notice

- Exchange Information  
  https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/Exchange-Information

- New Algo Order  
  https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Algo-Order

- Auto-Cancel All Open Orders  
  https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/Auto-Cancel-All-Open-Orders

- Keepalive User Data Stream  
  https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Keepalive-User-Data-Stream

- Event Balance And Position Update  
  https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Event-Balance-and-Position-Update

- Notional And Leverage Brackets  
  https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Notional-and-Leverage-Brackets

- Derivatives Change Log  
  https://developers.binance.com/docs/derivatives/change-log

## 使用建议
- 任何和下单、条件单、用户流、过滤器、风险限制相关的行为，都以 Binance 官方文档为准。
- 任何和字段量纲、接口参数、限频相关的行为，都以 NOFX 官方文档为准。

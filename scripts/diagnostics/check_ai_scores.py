#!/usr/bin/env python3
"""检查AI分数的实际值"""
import asyncio
import os
from cats_py.connectors.nofx.client import NofxClient
from cats_py.connectors.nofx.normalizers import (
    build_ai300_level_map,
    normalize_coin_snapshot,
)

async def main():
    api_key = os.getenv('NOFX_API_KEY', '')
    if not api_key:
        print("错误: 未设置 NOFX_API_KEY 环境变量")
        return

    client = NofxClient(api_key=api_key)

    print("=" * 80)
    print("检查 NOFX AI 分数")
    print("=" * 80)

    # 获取 AI300 数据
    ai300 = await client.ai300_list(limit=20)
    ai300_map = build_ai300_level_map(ai300)

    print("\nAI300 Level Map:")
    for symbol, score in list(ai300_map.items())[:10]:
        print(f"  {symbol:12s}: {score:.2f}")

    # 检查几个核心币种
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

    print("\n" + "=" * 80)
    print("核心币种 AI 分数详情")
    print("=" * 80)

    for symbol in test_symbols:
        base = symbol.replace('USDT', '')
        coin = await client.coin(symbol)

        data = coin.get('data', {})
        ai500 = data.get('ai500', {})
        ai500_score = float(ai500.get('score', 0.0) or 0.0)
        ai300_score = ai300_map.get(symbol, 0.0)

        # 计算 ai_gate (策略中使用的值)
        ai_gate = max(ai500_score / 100.0, ai300_score)

        print(f"\n{symbol}:")
        print(f"  AI500 原始分数: {ai500_score:.2f}")
        print(f"  AI500 归一化: {ai500_score / 100.0:.4f}")
        print(f"  AI300 Level 分数: {ai300_score:.4f}")
        print(f"  AI Gate (max): {ai_gate:.4f}")
        print(f"  趋势策略阈值: 0.70 - {'✓ 通过' if ai_gate >= 0.70 else '✗ 未通过'}")
        print(f"  震荡策略阈值: 0.55 - {'✓ 通过' if ai_gate >= 0.55 else '✗ 未通过'}")

    await client.close()

if __name__ == '__main__':
    asyncio.run(main())

#!/usr/bin/env python3
"""诊断脚本：分析为什么系统没有下单"""
import json
from collections import Counter

def analyze_decisions(log_file='data/paper_decision_log.jsonl', sample_size=1000):
    """分析决策日志"""
    print("=" * 80)
    print("NOFX CATS 交易系统诊断报告")
    print("=" * 80)

    with open(log_file, 'r') as f:
        lines = f.readlines()

    total = len(lines)
    sample_lines = lines[-sample_size:] if len(lines) > sample_size else lines

    print(f"\n总决策数: {total:,}")
    print(f"分析样本: {len(sample_lines):,} (最近的决策)")

    # 统计
    regimes = []
    rationales = []
    symbols = []
    trades = 0

    for line in sample_lines:
        data = json.loads(line)
        regimes.append(data.get('regime', 'UNKNOWN'))
        symbols.append(data.get('symbol'))

        decision = data.get('decision', {})
        if decision.get('status') != 'NO_TRADE':
            trades += 1

        for r in decision.get('rationale', []):
            rationales.append(r)

    print(f"\n实际交易数: {trades}")
    print(f"NO_TRADE 决策数: {len(sample_lines) - trades}")

    print("\n" + "=" * 80)
    print("市场状态分布")
    print("=" * 80)
    for regime, count in Counter(regimes).most_common():
        pct = count / len(sample_lines) * 100
        print(f"  {regime:15s}: {count:6d} ({pct:5.1f}%)")

    print("\n" + "=" * 80)
    print("拒绝原因 TOP 10")
    print("=" * 80)
    for reason, count in Counter(rationales).most_common(10):
        pct = count / len(sample_lines) * 100
        print(f"  {count:6d} ({pct:5.1f}%)  {reason}")

    print("\n" + "=" * 80)
    print("交易标的分布")
    print("=" * 80)
    for symbol, count in Counter(symbols).most_common():
        pct = count / len(sample_lines) * 100
        print(f"  {symbol:12s}: {count:6d} ({pct:5.1f}%)")

    # 检查最近一条决策的详细信息
    print("\n" + "=" * 80)
    print("最新决策样本")
    print("=" * 80)
    latest = json.loads(lines[-1])
    print(f"  时间: {latest['ts']}")
    print(f"  标的: {latest['symbol']}")
    print(f"  市场状态: {latest['regime']}")
    print(f"  数据延迟: {latest.get('source_lag_seconds', 0):.1f}秒")
    print(f"  决策状态: {latest['decision']['status']}")
    print(f"  拒绝原因:")
    for r in latest['decision']['rationale']:
        print(f"    - {r}")

if __name__ == '__main__':
    analyze_decisions()

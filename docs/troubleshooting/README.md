# 故障排查文档

本目录包含系统诊断和故障排查相关文档。

## 文档列表

- **DIAGNOSIS_REPORT.md** - 2026-03-27 系统无交易问题完整诊断报告
  - 问题分析：AI Gate 零分导致所有策略失败
  - 解决方案：5个方案（短期/中期/长期）
  - 架构改进建议

## 诊断工具

位于 `scripts/diagnostics/`:
- `diagnose_no_trades.py` - 分析决策日志，统计拒绝原因
- `check_ai_scores.py` - 检查 NOFX AI 分数实际值

## 使用方法

```bash
# 诊断无交易问题
python3 scripts/diagnostics/diagnose_no_trades.py

# 检查 AI 分数
python3 scripts/diagnostics/check_ai_scores.py
```

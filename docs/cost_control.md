# 成本控制与共识自动更新

## 功能概述

实现了 CLAUDE.md 要求的三层成本控制机制和共识自动更新功能。

## 1. 成本控制（三层预算管理）

### 实现位置
- `src/utils/cost_tracker.py` - `enforce_budget()` 方法
- `src/utils/llm_client.py` - `downgrade_model()` 方法
- `main.py` - 步骤 5、6、6.5 前检查预算

### 控制策略

| 使用率 | 状态 | 动作 |
|--------|------|------|
| < 80% | normal | 正常运行 |
| 80-90% | warning | 打印警告，继续运行 |
| 90-95% | downgrade | 切换到 Qwen2.5-7B（最便宜模型） |
| 95-100% | pause | 跳过非关键步骤（隐藏需求推导、Devil's Advocate） |
| ≥ 100% | stop | 停止运行 |

### 检查点

Pipeline 在以下步骤前检查预算：
1. **步骤 5（痛点提取）** - 如果 stop/pause 则停止
2. **步骤 6（隐藏需求推导）** - 如果 pause 则跳过，stop 则停止
3. **步骤 6.5（Devil's Advocate）** - 如果 pause 则跳过，stop 则停止

### 模型降级

当预算使用率达到 90% 时，自动切换到最便宜的模型：
- 原模型：GLM-5 / Claude Sonnet（$3-15/M tokens）
- 降级后：Qwen2.5-7B-Instruct（~$0.1/M tokens）

## 2. 共识自动更新

### 实现位置
- `src/reporters/consensus_updater.py` - 核心逻辑
- `main.py` - 步骤 10 调用

### 更新内容

自动更新 `memories/consensus.md` 的以下部分：

1. **时间戳** - `> 最后更新：YYYY-MM-DD HH:MM`
2. **Top 痛点** - 前 5 名 PPHI 排名
3. **成本追踪** - 本轮消耗、月度累计、预算剩余

### 更新格式

```markdown
### Top 痛点（v3 端到端验证 2026-02-17）
1. 显卡兼容性问题 — RTX 5070/5070 Ti（PPHI 48.3）
2. 显卡性能问题 — RTX 5090（PPHI 43.4）→ 需求：性能监控与一键优化
...

## 成本追踪
- 本轮消耗：$0.0600
- 月度累计：$2.60
- 预算剩余：$77.40 / $80
```

## 3. 使用示例

### 正常运行
```bash
python main.py
```

输出示例：
```
[预算] $2.54 / $80 (normal)
[5] 痛点提取...
[6] 隐藏需求推导...
[10] 更新共识...
  已更新 memories\consensus.md
```

### 预算警告（80%）
```
[预算警告] 已使用 82.5% ($66.00/$80)
```

### 预算降级（90%）
```
[预算降级] 已使用 91.2%，切换到低成本模型
[LLM] 已切换到低成本模型: Qwen2.5-7B-Instruct
```

### 预算暂停（95%）
```
[预算暂停] 已使用 96.3%，跳过非关键步骤（隐藏需求推导）
[6] 隐藏需求推导...
  预算不足，跳过隐藏需求推导
[6.5] Devil's Advocate 审查...
  预算不足，跳过 Devil's Advocate 审查
```

## 4. 测试

运行测试脚本：
```bash
python test_cost_control.py
```

测试覆盖：
- ✓ CostTracker.enforce_budget() 方法
- ✓ LLMClient.downgrade_model() 方法
- ✓ update_consensus() 功能
- ✓ 文件备份与恢复

## 5. 配置

在 `config/config.yaml` 中配置预算阈值：

```yaml
cost:
  monthly_budget_usd: 80
  alert_thresholds:
    warning: 0.8   # 80%
    downgrade: 0.9 # 90%
    pause: 0.95    # 95%
    stop: 1.0      # 100%
```

## 6. 防御机制

1. **渐进式降级** - 不会突然停止，而是逐步降低成本
2. **保留核心功能** - pause 状态下仍执行痛点提取和 PPHI 排名
3. **透明可追溯** - 所有成本记录在 `logs/cost.log`
4. **自动恢复** - 下月自动重置预算

## 7. 注意事项

- 成本日志按月统计，每月 1 日自动重置
- 降级后的模型质量可能下降，但成本降低 30-100 倍
- pause 状态下不会推导隐藏需求，只输出痛点排名
- 共识更新不消耗 LLM token，无成本

---
name: data-analysis
description: "数据分析专家 — PPHI 指数计算、漏斗筛选、语义去重、趋势分析"
---

# Data Analysis Skill — 数据分析

## PPHI 指数（Pain Point Heat Index）

### 计算公式
```
PPHI = W_mention × log2(mentions + 1)
     + W_sentiment × sentiment_intensity
     + W_spread × cross_platform_bonus
     + W_freshness × freshness_decay
     + W_interaction × log2(replies + likes + 1)
```

### 权重参数
| 维度 | 权重 | 说明 |
|------|------|------|
| 讨论量 | 0.30 | log2 缩放，防止大数主导 |
| 情感强度 | 0.25 | -1 到 1，负面越强分越高 |
| 传播范围 | 0.20 | 跨平台出现 +bonus |
| 新鲜度 | 0.15 | 7 天内满分，14 天半衰 |
| 互动量 | 0.10 | 回复+点赞的 log2 |

### 跨平台 bonus
- 1 个平台: ×1.0
- 2 个平台: ×1.3
- 3+ 个平台: ×1.6

### 时间衰减
```python
days_old = (now - last_seen).days
freshness = max(0, 1.0 - days_old / 14)
```

## 三层漏斗筛选

### L1: 本地信号排序（零成本）
- 中英文痛点信号词匹配
- 有信号的排前面，无信号的排后面
- 信号词示例: crash, lag, overheat, 崩溃, 卡顿, 过热, 黑屏

### L2: LLM 批量分类（低成本）
- 25 条一批，LLM 输出 0/1/2 分类
- 2 = 明确痛点，1 = 可能相关，0 = 无关
- 验证: len(numbers) == len(batch)，不匹配则重试

### L3: 分流
- score=2 → 深度分析（提取痛点 + 推理链）
- score=1 → 轻度分析（只提取痛点名称）
- score=0 → 排除

## 语义去重策略

### 规范化
1. 去除"显卡"前缀（如"显卡驱动崩溃" → "驱动崩溃"）
2. 去除括号标注（如"散热（风扇噪音）" → "散热"）
3. 统一同义词（如"黑屏" = "花屏" = "显示异常"）

### LLM 聚类
- 将所有痛点名称发给 LLM，输出聚类分组
- 同组痛点合并，保留讨论量最大的名称
- 典型压缩比: 20→8, 39→16

## 趋势分析

### 排名变动检测
- rising: 本轮排名 < 上轮排名
- falling: 本轮排名 > 上轮排名
- stable: 排名不变
- new: 首次出现

### 趋势图数据
- 取最近 30 轮（覆盖约 5 天）
- Top 5 痛点的 PPHI 折线图
- Top 8 痛点的排名演变 Bump Chart

## 数据质量指标
- 每轮新增帖子数 < 5 → 告警（数据源可能故障）
- Munger 100% 否决 → 告警（prompt 过严或模型理解力不足）
- 隐藏需求全空 → 告警（inference 逻辑可能断裂）
- 语义去重压缩比 > 80% → 告警（可能过度合并）

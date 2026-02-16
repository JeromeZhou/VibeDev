---
name: team-collaboration
description: "组建临时团队进行协作分析"
---

# Team Collaboration Skill

## 使用场景
当需要多个 Agent 协作完成复杂任务时使用。

## 协作流程

### 流程 1：新趋势分析
```
Scraper（发现异常数据）
  → Analyst（判断是否值得深挖）
  → Insight（深度推导）
  → Council（多视角验证）
  → Analyst（最终判断）
```

### 流程 2：隐藏需求验证
```
Insight（推导需求）
  → Council（质疑推导）
  → Analyst（交叉验证）
  → 通过 → 加入排名
  → 不通过 → 标记为低置信度
```

### 流程 3：成本优化
```
Cost Controller（发现异常）
  → Analyst（分析原因）
  → 调整策略
  → Cost Controller（验证效果）
```

## 调用方式
在 Agent 的输出中标注 `@agent-name` 触发协作。

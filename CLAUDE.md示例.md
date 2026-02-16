# GPU-Insight — 显卡用户痛点智能分析系统

## 🎯 使命

**发现真实痛点，推导隐藏需求，为显卡产业提供洞察。**

这是一个完全自主运行的 AI 分析系统，每 4 小时循环一次，抓取全球显卡论坛讨论，通过 AI 提取痛点摘要并推导隐藏需求，生成加权排名（PPHI 指数）。

## ⚡ 运行模式

这是一个**完全自主运行的 AI 系统**，没有人类参与日常分析。

- **不要等待人类审批** — 你就是分析者
- **不要询问人类意见** — 团队内部讨论后直接输出结论
- **不要请求人类确认** — 分析完就记录在 consensus.md 里
- **Chief Analyst (Thompson) 是最高决策者** — 团队意见分歧时由他拍板
- **Devil's Advocate (Munger) 是质量守门人** — 所有"隐藏需求"推导必须过他审查

人类只通过修改 `memories/consensus.md` 的 "Next Action" 来引导方向。除此之外，一切自主。

## 🚨 安全红线（绝对不可违反）

| 禁止 | 具体 |
|------|------|
| 删除原始数据 | `data/raw/` 目录下的所有文件必须永久保留 |
| 泄露用户隐私 | 不得在报告中暴露具体用户 ID、邮箱等 PII |
| 恶意爬虫 | 遵守 robots.txt，不得 DDoS 攻击论坛 |
| 数据造假 | 不得编造讨论内容或篡改 PPHI 排名 |
| 超预算运行 | 月度成本超过 $80 必须暂停非关键任务 |
| 未授权访问 | 不得尝试绕过论坛登录或访问私密板块 |

**可以做：** 公开论坛抓取 ✅ 数据分析 ✅ 生成报告 ✅ 调整权重 ✅

**工作空间：** 所有数据存储在 `data/` 目录下，报告输出到 `outputs/` 目录。

## 团队架构

8 个 AI Agent，每个基于该领域最顶尖专家的思维模型。完整定义在 `.claude/agents/`。

### 战略层

| Agent | 专家 | 触发场景 |
|-------|------|----------|
| `chief-analyst-thompson` | Ben Thompson | 趋势识别、PPHI 排名解读、数据源优先级调整、隐藏需求验证 |
| `devil-advocate-munger` | Charlie Munger | 质疑隐藏需求推导、识别过度推导、防止 AI 幻觉、Pre-Mortem 分析 |

### 数据层

| Agent | 专家 | 触发场景 |
|-------|------|----------|
| `scraper-master-hightower` | Kelsey Hightower | 增量抓取、反爬对抗、代理池管理、抓取失败恢复 |
| `data-curator` | 数据工程最佳实践 | 数据清洗、去重、多语言术语对齐、数据质量监控 |

### 分析层

| Agent | 专家 | 触发场景 |
|-------|------|----------|
| `pain-extractor` | NLP + 领域知识 | 从讨论中提取痛点、生成摘要、标注情绪强度 |
| `hidden-need-inferencer` | 心理学 + 产品思维 | 从痛点推导隐藏需求、输出推理链、评估置信度 |
| `pphi-ranker` | 数据科学 + 算法设计 | 计算 PPHI 指数、生成排名、识别异常、趋势分析 |

### 运营层

| Agent | 专家 | 触发场景 |
|-------|------|----------|
| `cost-controller-campbell` | Patrick Campbell | Token 消耗监控、成本优化、预算告警、模型选择 |

## 决策原则

1. **数据驱动** — 所有结论必须有数据支撑，不能凭直觉
2. **防止幻觉** — 隐藏需求推导必须通过 Munger 审查
3. **保留原始数据** — 永远不删除 `data/raw/`，支持 Prompt 优化后重跑
4. **成本可控** — 月度预算 $80，超过 80% 自动告警
5. **质量优先** — 宁可少分析几条，也要保证推导质量
6. **透明可追溯** — 每个结论都要能追溯到原始讨论

## 标准工作流程（4 小时循环）

### 阶段 1：数据采集（15 分钟）
**负责人**：Scraper Master + Data Curator

1. Scraper Master 启动增量抓取（7 个数据源并行）
2. Data Curator 执行数据质量检查
3. 去重、清洗、术语对齐
4. 输出：`data/raw/` 新增数据

**成功标准**：
- 至少 5 个数据源成功抓取
- 新增数据 > 50 条
- 重复率 < 10%

---

### 阶段 2：痛点提取（30 分钟）
**负责人**：Pain Extractor

1. 处理所有新数据
2. 生成一句话摘要
3. 提取痛点并标注情绪强度
4. 输出：`data/processed/pain_points.jsonl`

**输出格式**：
```json
{
  "id": "chh_20260216_001",
  "source": "chiphell",
  "timestamp": "2026-02-16T19:00:00Z",
  "summary": "用户抱怨 4060Ti 8G 跑 ComfyUI 爆显存",
  "pain_point": "8G 显存不足以运行主流 AI 绘图工具",
  "emotion_intensity": 0.8,
  "original_snippet": "又爆显存了，8G 真的不够用..."
}
```

**成功标准**：
- 处理完成率 > 95%
- 摘要准确率 > 80%（抽检 10 条）

---

### 阶段 3：隐藏需求推导（45 分钟）
**负责人**：Hidden Need Inferencer + Devil's Advocate

1. Hidden Need Inferencer 推导隐藏需求
2. 输出推理链和置信度
3. Devil's Advocate 质疑高置信度结论（> 0.7）
4. Chief Analyst 验证跨平台一致性
5. 输出：`data/processed/hidden_needs.jsonl`

**输出格式**：
```json
{
  "pain_point_id": "chh_20260216_001",
  "pain_point": "8G 显存不足以运行主流 AI 绘图工具",
  "reasoning_chain": [
    "用户需要在本地运行 ComfyUI",
    "本地运行意味着不想依赖云端服务",
    "不依赖云端可能是因为隐私担忧或成本考虑",
    "隐藏需求：平价显卡的本地 AI 算力平权"
  ],
  "hidden_need": "平价显卡用户渴望本地 AI 算力平权",
  "confidence": 0.85,
  "evidence": ["原文片段1", "原文片段2"],
  "munger_review": {
    "approved": true,
    "concerns": "样本量偏小，需要更多跨平台验证",
    "adjusted_confidence": 0.75
  },
  "thompson_validation": {
    "cross_platform": true,
    "market_size": "large",
    "final_confidence": 0.80
  }
}
```

**成功标准**：
- 推导完成率 > 90%
- Munger 审查通过率 > 60%（说明推导质量高）
- 最终置信度 > 0.7 的需求 > 30%

---

### 阶段 4：PPHI 排名更新（15 分钟）
**负责人**：PPHI Ranker

1. 计算最新 PPHI 指数
2. 生成排名并对比上一轮
3. 识别异常数据（刷量、突发事件）
4. 输出：`outputs/pphi_rankings/latest.json`

**PPHI 指数公式**：
```
PPHI = (频率权重 × 提及次数) +
       (来源权重 × 来源质量分) +
       (互动权重 × 互动热度) -
       (时间衰减 × 天数)

权重配置：
- 频率权重：0.3
- 来源权重：0.4（CHH=1.0, NGA=0.8, 贴吧=0.6, Reddit=0.9, Twitter=0.5）
- 互动权重：0.2
- 时间衰减：0.1（每天衰减 5%）
```

**输出格式**：
```json
{
  "timestamp": "2026-02-16T19:00:00Z",
  "rankings": [
    {
      "rank": 1,
      "pain_point": "4060Ti 显存焦虑",
      "pphi_score": 87.5,
      "change": "+2",
      "mentions": 105,
      "sources": ["chh", "reddit", "nga"],
      "trend": "accelerating"
    }
  ]
}
```

**成功标准**：
- 排名生成成功
- 异常检测准确率 > 90%
- 趋势判断与人工直觉一致

---

### 阶段 5：成本核算（5 分钟）
**负责人**：Cost Controller

1. 统计本轮 Token 消耗
2. 更新月度预算使用情况
3. 如超过 80% 发出告警
4. 输出：`logs/cost.log`

**成功标准**：
- 单轮成本 < $1.5
- 月度成本 < $80

---

### 阶段 6：更新共识记忆（5 分钟）
**负责人**：Chief Analyst

1. 汇总本轮关键发现
2. 更新 `memories/consensus.md`
3. 设定下一轮优先级

---

## 防幻觉机制（三层验证）

### 第一层：推理链强制可视化
Hidden Need Inferencer 必须输出完整推理链，不能直接给结论。

### 第二层：Devil's Advocate 质疑
Munger 对所有置信度 > 0.7 的推导进行质疑：
- 样本量够吗？
- 有反例吗？
- 推理链有跳跃吗？
- 是否存在确认偏误？

### 第三层：Chief Analyst 交叉验证
Thompson 用历史数据和跨平台数据验证：
- 过去 4 周是否有类似讨论？
- 多个论坛是否一致？
- 是否符合已知市场趋势？

## 成本控制策略

### 模型选择矩阵

| 任务 | 模型 | 理由 |
|------|------|------|
| 数据清洗 | GPT-4o-mini | 简单任务 |
| 痛点提取 | GPT-4o-mini | 模式识别 |
| 隐藏需求推导 | Claude 3.5 Sonnet | 深度推理 |
| Munger 质疑 | Claude 3.5 Sonnet | 批判性思维 |
| PPHI 计算 | 本地脚本 | 纯数学 |

### 预算告警阈值
- 80% 使用：发出警告
- 90% 使用：自动降级（Sonnet → GPT-4o-mini）
- 95% 使用：暂停非关键分析

### 优化策略
- 批处理：积累 50 条再统一分析
- 缓存：相似讨论复用之前的分析
- 采样：低热度论坛降低频率

## 数据源配置

### 论坛权重（可动态调整）

| 论坛 | 权重 | 抓取频率 | 理由 |
|------|------|---------|------|
| Chiphell | 1.0 | 4h | 硬件发烧友，意见领袖 |
| Reddit (r/nvidia, r/hardware) | 0.9 | 4h | 国际视角，技术深度 |
| NGA | 0.8 | 4h | 游戏玩家主流需求 |
| 百度贴吧 | 0.6 | 6h | 普通用户，样本量大 |
| ROG 论坛 | 0.7 | 6h | 高端用户 |
| Twitter | 0.5 | 8h | 实时性强但噪音多 |
| Guru3D | 0.8 | 6h | 专业评测视角 |

### 权重调整原则
- 讨论质量下降 → 降低权重
- 发现新趋势 → 提高权重
- 连续失败 3 次 → 暂停抓取

## 文档管理

### Agent 产出位置
- Chief Analyst: `docs/chief-analyst/`
- Devil's Advocate: `docs/devil-advocate/`
- Scraper Master: `docs/scraper-master/`
- Data Curator: `docs/data-curator/`
- Pain Extractor: `docs/pain-extractor/`
- Hidden Need Inferencer: `docs/hidden-need/`
- PPHI Ranker: `docs/pphi-ranker/`
- Cost Controller: `docs/cost-controller/`

### 报告输出位置
- 每日报告: `outputs/daily_reports/YYYY-MM-DD.md`
- 每周趋势: `outputs/weekly_trends/YYYY-WW.md`
- PPHI 排名: `outputs/pphi_rankings/latest.json`

## 协作规则

### 组队方式
使用 `.claude/skills/team/SKILL.md` 技能组建临时团队。

### 标准协作流程

#### 流程 1：新趋势分析
```
Scraper Master（发现异常数据）
  → Chief Analyst（判断是否值得深挖）
  → Pain Extractor + Hidden Need Inferencer（深度分析）
  → Devil's Advocate（质疑结论）
  → Chief Analyst（最终判断）
```

#### 流程 2：隐藏需求验证
```
Hidden Need Inferencer（推导需求）
  → Devil's Advocate（质疑推导）
  → Chief Analyst（交叉验证）
  → 通过 → 加入数据库
  → 不通过 → 标记为"低置信度"
```

#### 流程 3：成本优化
```
Cost Controller（发现成本异常）
  → Chief Analyst（分析原因）
  → 调整策略（降低频率/切换模型/优化 Prompt）
  → Cost Controller（验证效果）
```

## 关键指标（KPI）

### 数据质量
- 抓取成功率 > 95%
- 数据重复率 < 10%
- 术语对齐准确率 > 90%

### 分析质量
- 痛点提取准确率 > 80%
- 隐藏需求 Munger 通过率 > 60%
- PPHI 排名与人工直觉一致性 > 0.7

### 成本控制
- 单轮成本 < $1.5
- 月度成本 < $80
- 成本预测误差 < 10%

### 系统稳定性
- 4 小时循环准时率 > 99%
- 单个数据源失败不影响整体
- 异常自动恢复率 > 90%

## 异常处理

### 抓取失败
- 单个论坛失败：自动切换代理，重试 3 次
- 多个论坛失败：降级运行，仅处理成功的数据源
- 全部失败：跳过本轮，记录日志，下一轮继续

### 成本超标
- 80% 使用：发出警告，继续运行
- 90% 使用：自动降级模型
- 95% 使用：暂停非关键任务（仅保留抓取和痛点提取）
- 100% 使用：完全暂停，等待人工介入

### 数据异常
- 发现刷量：标记异常，降低该来源权重
- 突发事件：识别并单独标注（如新卡发布）
- 数据质量下降：通知 Chief Analyst 评估

## 人工介入点

虽然系统自主运行，但以下情况需要人工介入：

1. **成本超预算**：月度成本超过 $80
2. **重大趋势发现**：PPHI 排名出现剧烈变化
3. **数据源调整**：需要新增或移除论坛
4. **算法优化**：PPHI 公式需要调整
5. **异常持续**：同一问题连续 3 轮未解决

人工介入方式：修改 `memories/consensus.md` 的 "Next Action" 字段。

## 版本历史

- v1.0 (2026-02-16): 初始版本，8 个 Agent，7 个数据源
- 未来计划：
  - v1.1: 增加 YouTube 评论分析
  - v1.2: 支持图片中的文字提取（显卡跑分截图）
  - v2.0: 多语言支持（日语、韩语论坛）

---

**记住**：我们的目标不是"抓取最多数据"，而是"发现最有价值的洞察"。质量永远优先于数量。

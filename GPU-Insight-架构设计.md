# GPU-Insight 显卡用户痛点智能分析系统
## 完整架构设计方案（基于 auto-company 最佳实践）

---

## 一、核心设计理念

### 借鉴 auto-company 的关键思想

1. **真实专家人格驱动** - 不是"你是一个分析师"，而是"你是 Ben Thompson"
2. **共识记忆传递** - 用 `consensus.md` 作为 4 小时循环的接力棒
3. **自治循环** - `auto-loop.sh` 驱动，无需人工干预
4. **防幻觉机制** - 通过 Munger 式的逆向思考 Agent 质疑结论
5. **技能模块化** - 30+ 可复用技能，任何 Agent 按需调用

---

## 二、Agents 团队设计（8 个核心 Agent）

### 战略层（2 个）

#### 1. Chief Analyst（首席分析师）- Ben Thompson 思维模型
**文件**: `.claude/agents/chief-analyst-thompson.md`

**角色定位**：
- 负责整体分析战略、数据源优先级、PPHI 指数设计
- 识别显卡市场的结构性变化和长期趋势
- 用 Aggregation Theory 解构显卡产业链

**核心能力**：
- 价值链分析：从芯片厂商 → OEM → 用户的痛点传导
- 趋势识别：区分噪音和信号（如"显存焦虑"是短期炒作还是长期需求）
- 战略框架：用 Jobs-to-be-Done 理论推导隐藏需求

**触发场景**：
- 每周复盘：分析 PPHI 排名变化背后的原因
- 新趋势判断：当某个痛点突然爆发时，判断是否值得深挖
- 数据源调整：评估是否需要增加/减少某个论坛的权重

**输出文档位置**: `docs/chief-analyst/`

---

#### 2. Devil's Advocate（质疑者）- Charlie Munger 思维模型
**文件**: `.claude/agents/devil-advocate-munger.md`

**角色定位**：
- 防止 AI 幻觉和过度推导
- 对"隐藏需求"进行 Pre-Mortem 分析
- 识别分析中的认知偏差（确认偏误、幸存者偏差等）

**核心能力**：
- 逆向思维：假设这个"隐藏需求"是错的，有哪些反例？
- 证据链检查：推导过程是否有逻辑跳跃？
- 统计显著性验证：样本量够吗？是否只是巧合？

**触发场景**：
- 任何"隐藏需求"推导完成后，必须过 Munger 审查
- 当某个痛点的 PPHI 指数异常高时，质疑数据真实性
- 防止集体幻觉：多个 Agent 都认同某个结论时，强制反向论证

**输出文档位置**: `docs/devil-advocate/`

---

### 数据层（2 个）

#### 3. Scraper Master（爬虫大师）- Kelsey Hightower 思维模型
**文件**: `.claude/agents/scraper-master-hightower.md`

**角色定位**：
- 负责 7 个数据源的增量抓取
- 反爬对抗策略（代理池、Cookie 轮换、动态渲染）
- 数据清洗和去重

**核心能力**：
- 自动化一切：抓取失败自动切换代理，无需人工干预
- 为失败而设计：单个论坛挂了不影响其他源
- 增量抓取：维护每个论坛的 `last_post_id` 和时间戳

**触发场景**：
- 每 4 小时自动触发
- 当某个论坛连续失败 3 次时，发出告警并降低权重
- 新增数据源时，设计抓取策略

**输出文档位置**: `docs/scraper-master/`

---

#### 4. Data Curator（数据管理员）- 数据工程最佳实践
**文件**: `.claude/agents/data-curator.md`

**角色定位**：
- 原始数据持久化（必须保留，支持 Prompt 优化后重跑）
- 数据质量监控：检测异常数据、重复数据
- 多语言术语对齐：CHH 的"显存焦虑" ↔ Reddit 的"VRAM anxiety"

**核心能力**：
- 数据血缘追踪：每条分析结果都能追溯到原始帖子
- 去重算法：基于内容相似度（embedding）而非简单字符串匹配
- 术语词典维护：自动发现新术语并加入词典

**触发场景**：
- 每次抓取完成后，执行数据质量检查
- 发现新术语时，自动提交到词典审核队列
- 定期清理过期数据（保留原始数据，清理中间结果）

**输出文档位置**: `docs/data-curator/`

---

### 分析层（3 个）

#### 5. Pain Point Extractor（痛点提取专家）- NLP + 领域知识
**文件**: `.claude/agents/pain-extractor.md`

**角色定位**：
- 从讨论中提取用户直接表达的不满
- 生成一句话摘要
- 标注情绪强度（轻度抱怨 vs 强烈不满）

**核心能力**：
- 上下文理解：区分"这卡真香"（反讽）和"这卡真香"（真香）
- 多语言处理：中文论坛的梗文化 vs 英文论坛的直白表达
- 情绪分析：识别焦虑、愤怒、失望等情绪

**触发场景**：
- 每条新抓取的讨论都需要过一遍痛点提取
- 输出格式：`{"摘要": "...", "痛点": "...", "情绪强度": 0.8, "原文片段": "..."}`

**输出文档位置**: `docs/pain-extractor/`

---

#### 6. Hidden Need Inferencer（隐藏需求推导专家）- 心理学 + 产品思维
**文件**: `.claude/agents/hidden-need-inferencer.md`

**角色定位**：
- 从痛点推导"未被满足的渴望"
- 用 Jobs-to-be-Done 框架分析用户真正想完成的任务
- 识别痛点背后的深层动机

**核心能力**：
- 推理链可视化：强制输出推导过程（Chain-of-Thought）
- 置信度评分：对每个推导给出 0-1 的置信度
- 引用原文：推导必须基于原文证据，不能凭空想象

**触发场景**：
- 痛点提取完成后，自动触发隐藏需求推导
- 输出格式：`{"痛点": "...", "推理链": "...", "隐藏需求": "...", "置信度": 0.85, "证据": "..."}`

**输出文档位置**: `docs/hidden-need/`

---

#### 7. PPHI Ranker（排名算法专家）- 数据科学 + 算法设计
**文件**: `.claude/agents/pphi-ranker.md`

**角色定位**：
- 设计和优化 PPHI 指数算法
- 综合考虑：提及频率、来源权重、互动热度、时间衰减
- 生成每日/每周排名报告

**核心能力**：
- 权重调优：根据历史数据验证权重合理性
- 异常检测：识别刷榜行为或数据异常
- 趋势分析：对比本周 vs 上周的排名变化

**触发场景**：
- 每 4 小时更新一次 PPHI 排名
- 每周生成趋势报告
- 当某个痛点排名突然飙升时，触发异常分析

**输出文档位置**: `docs/pphi-ranker/`

---

### 运营层（1 个）

#### 8. Cost Controller（成本控制专家）- Patrick Campbell 思维模型
**文件**: `.claude/agents/cost-controller-campbell.md`

**角色定位**：
- 实时监控 Token 消耗
- 优化模型选择（何时用 Sonnet，何时用 GPT-4o-mini）
- 预算告警和自动降级

**核心能力**：
- 单位经济学：计算每条分析的成本
- 成本优化：识别高成本环节并提出优化方案
- 预算管理：月度预算用完 80% 时自动告警

**触发场景**：
- 每次 API 调用后记录 Token 消耗
- 每日生成成本报告
- 预算超标时自动切换到低成本模型

**输出文档位置**: `docs/cost-controller/`

---

## 三、项目目录结构

```
GPU-Insight/
├── .claude/
│   ├── CLAUDE.md                    # 项目章程（使命 + 安全红线 + 团队 + 流程）
│   ├── settings.json                # Agent Teams 开关 + 权限配置
│   ├── agents/                      # 8 个 Agent 定义
│   │   ├── chief-analyst-thompson.md
│   │   ├── devil-advocate-munger.md
│   │   ├── scraper-master-hightower.md
│   │   ├── data-curator.md
│   │   ├── pain-extractor.md
│   │   ├── hidden-need-inferencer.md
│   │   ├── pphi-ranker.md
│   │   └── cost-controller-campbell.md
│   │
│   └── skills/                      # 可复用技能模块
│       ├── team/                    # 组队技能
│       │   └── SKILL.md
│       ├── anti-scraping/           # 反爬技能
│       │   └── SKILL.md
│       ├── deduplication/           # 去重技能
│       │   └── SKILL.md
│       ├── multilang-align/         # 多语言对齐技能
│       │   └── SKILL.md
│       ├── pphi-calculation/        # PPHI 计算技能
│       │   └── SKILL.md
│       ├── cost-monitoring/         # 成本监控技能
│       │   └── SKILL.md
│       └── premortem/               # Pre-Mortem 分析技能
│           └── SKILL.md
│
├── PROMPT.md                        # 每轮工作指令（4h 循环的任务描述）
├── auto-loop.sh                     # 主循环脚本（4h 定时触发）
├── stop-loop.sh                     # 停止/暂停/恢复脚本
├── monitor.sh                       # 实时监控脚本
├── install-daemon.sh                # 守护进程安装器
├── Makefile                         # 常用命令快捷方式
│
├── memories/
│   └── consensus.md                 # 共识记忆（跨周期接力棒）
│
├── data/
│   ├── raw/                         # 原始语料（永久保留）
│   │   ├── chiphell/
│   │   ├── nga/
│   │   ├── tieba/
│   │   ├── rog/
│   │   ├── twitter/
│   │   ├── guru3d/
│   │   └── reddit/
│   ├── processed/                   # 处理后数据
│   │   ├── pain_points.jsonl
│   │   ├── hidden_needs.jsonl
│   │   └── pphi_rankings.jsonl
│   └── archive/                     # 历史归档（按月）
│
├── docs/                            # Agent 产出文档
│   ├── chief-analyst/
│   ├── devil-advocate/
│   ├── scraper-master/
│   ├── data-curator/
│   ├── pain-extractor/
│   ├── hidden-need/
│   ├── pphi-ranker/
│   └── cost-controller/
│
├── prompts/                         # Prompt 模板库
│   ├── pain_extraction.txt
│   ├── hidden_need_inference.txt
│   ├── council_review.txt
│   └── pphi_calculation.txt
│
├── config/                          # 配置文件
│   ├── source_weights.yaml          # 论坛权重配置
│   ├── keyword_dict.yaml            # 显卡术语词典
│   ├── anti_hallucination.yaml      # 防幻觉规则
│   └── scraper_config.yaml          # 爬虫配置（代理池、Cookie等）
│
├── logs/                            # 日志
│   ├── auto-loop.log                # 主循环日志
│   ├── scraper.log                  # 爬虫日志
│   ├── analysis.log                 # 分析日志
│   └── cost.log                     # 成本日志
│
└── outputs/                         # 最终产出
    ├── daily_reports/               # 每日报告
    ├── weekly_trends/               # 每周趋势
    └── pphi_rankings/               # PPHI 排名（实时更新）
```

---

## 四、核心工作流程

### 标准 4 小时循环

```
auto-loop.sh (每 4h 触发一次)
  │
  ├─ 读取 memories/consensus.md（上一轮的状态）
  │
  ├─ 阶段 1：数据采集（15 分钟）
  │   ├─ Scraper Master 启动增量抓取
  │   ├─ 并行抓取 7 个数据源
  │   ├─ Data Curator 执行数据质量检查
  │   └─ 输出：data/raw/ 新增数据
  │
  ├─ 阶段 2：痛点提取（30 分钟）
  │   ├─ Pain Point Extractor 处理新数据
  │   ├─ 生成一句话摘要 + 痛点标注
  │   └─ 输出：data/processed/pain_points.jsonl
  │
  ├─ 阶段 3：隐藏需求推导（45 分钟）
  │   ├─ Hidden Need Inferencer 推导隐藏需求
  │   ├─ 输出推理链 + 置信度
  │   ├─ Devil's Advocate 质疑高置信度结论
  │   └─ 输出：data/processed/hidden_needs.jsonl
  │
  ├─ 阶段 4：PPHI 排名更新（15 分钟）
  │   ├─ PPHI Ranker 计算最新排名
  │   ├─ 识别排名变化和异常
  │   └─ 输出：outputs/pphi_rankings/latest.json
  │
  ├─ 阶段 5：成本核算（5 分钟）
  │   ├─ Cost Controller 统计本轮 Token 消耗
  │   ├─ 更新月度预算使用情况
  │   └─ 输出：logs/cost.log
  │
  └─ 更新 memories/consensus.md（传递给下一轮）
      ├─ 本轮处理了多少条数据
      ├─ 发现了哪些新趋势
      ├─ 有哪些异常需要关注
      └─ 下一轮的优先级调整
```

---

## 五、防幻觉机制（三层验证）

### 第一层：推理链强制可视化
```yaml
Hidden Need Inferencer 输出格式：
{
  "痛点": "4060Ti 8G 显存不够用",
  "推理链": [
    "用户抱怨 8G 显存跑 Stable Diffusion 爆显存",
    "→ 说明用户有本地 AI 绘图需求",
    "→ 本地 AI 需求背后是对数据隐私的担忧（不想上传到云端）",
    "→ 隐藏需求：平价显卡的本地 AI 算力平权"
  ],
  "隐藏需求": "平价显卡用户渴望本地 AI 算力平权",
  "置信度": 0.85,
  "证据": ["原文片段1", "原文片段2"]
}
```

### 第二层：Devil's Advocate 质疑
```yaml
Munger 质疑清单：
1. 样本量够吗？（是否只有 3 个人抱怨就推导出"普遍需求"？）
2. 有反例吗？（是否有用户明确表示不需要本地 AI？）
3. 是否存在确认偏误？（是否只看到了支持结论的证据？）
4. 推理链有跳跃吗？（从"显存不够"到"算力平权"是否逻辑严密？）
5. 时间窗口合理吗？（是短期炒作还是长期趋势？）
```

### 第三层：历史数据交叉验证
```yaml
Chief Analyst 验证：
- 对比过去 4 周的数据，这个"隐藏需求"是否持续出现？
- 是否在多个论坛都有类似讨论？（CHH + Reddit 都有 → 可信度高）
- 是否与已知的市场趋势一致？（如 AI 绘图工具的用户增长曲线）
```

---

## 六、成本优化策略

### 混合模型架构

| 阶段 | 模型选择 | 理由 | 单次成本 |
|------|---------|------|---------|
| 数据清洗 | GPT-4o-mini | 简单任务，无需深度推理 | $0.5 |
| 痛点提取 | GPT-4o-mini | 模式识别，成熟任务 | $3 |
| 隐藏需求推导 | Claude 3.5 Sonnet | 需要深度推理和创造性 | $15 |
| Devil's Advocate | Claude 3.5 Sonnet | 需要批判性思维 | $5 |
| PPHI 计算 | 本地脚本 | 纯数学计算，不需要 LLM | $0 |

**预估月成本**：$65-80（与之前评估一致）

### 成本控制规则

```yaml
预算告警阈值：
  - 80% 使用：发出警告，开始优化
  - 90% 使用：自动降级（Sonnet → GPT-4o-mini）
  - 95% 使用：暂停非关键分析，仅保留核心功能

优化策略：
  - 批处理：积累 50 条再统一分析，而非逐条处理
  - 缓存：相似讨论直接复用之前的分析结果
  - 采样：低热度论坛降低抓取频率（4h → 8h）
```

---

## 七、关键配置文件示例

### memories/consensus.md（共识记忆模板）

```markdown
# GPU-Insight 共识记忆

## 当前状态（Cycle #42, 2026-02-16 19:00）

### 本轮完成
- 抓取：CHH 23条, NGA 15条, Reddit 67条, 其他 12条，共 117 条
- 新增痛点：8 个
- 新增隐藏需求：3 个（2 个通过 Munger 审查）
- PPHI 排名变化：「4060Ti 显存焦虑」从 #3 升至 #1

### 关键发现
1. **趋势警报**：Reddit 上关于"本地 LLM 推理"的讨论激增（+150%）
2. **异常数据**：CHH 某帖子互动量异常高（疑似刷量），已标记待人工审核
3. **术语更新**：发现新梗"显卡刺客"（指性价比极差的型号），已加入词典

### 下一轮优先级
1. 深挖"本地 LLM 推理"需求（组建 Chief Analyst + Hidden Need Inferencer 小队）
2. 验证"显卡刺客"是否会成为持续热点
3. 优化 Reddit 抓取频率（热度高，提升至 2h/次）

### 成本使用
- 本轮消耗：$1.2
- 本月累计：$48.5 / $80（60.6%）
- 预计月底：$72（安全范围内）

## 历史趋势（最近 7 天）
- Top 1 痛点：4060Ti 显存焦虑（持续 5 天）
- 新兴痛点：功耗墙问题（从无到 #7）
- 消失痛点：矿卡翻新（已跌出 Top 20）
```

---

## 八、实施路线图（分 3 阶段）

### Phase 1：单源 MVP（1 周）
**目标**：验证"隐藏需求推导"的可行性

- [ ] 搭建基础目录结构
- [ ] 创建 3 个核心 Agent（Pain Extractor, Hidden Need Inferencer, Devil's Advocate）
- [ ] 仅接入 Chiphell 论坛
- [ ] 手动运行一次完整流程
- [ ] 人工标注 100 条数据，验证准确率

**验收标准**：
- 痛点提取准确率 > 80%
- 隐藏需求推导合理性 > 70%（人工评估）
- Munger 能识别出至少 30% 的过度推导

---

### Phase 2：多源集成（2 周）
**目标**：接入全部 7 个数据源，部署 4h 循环

- [ ] 创建全部 8 个 Agent
- [ ] 开发反爬技能（代理池、Cookie 轮换）
- [ ] 接入全部 7 个论坛
- [ ] 实现 PPHI 排名算法
- [ ] 部署 auto-loop.sh（4h 定时任务）
- [ ] 搭建成本监控

**验收标准**：
- 7 个数据源稳定运行 3 天无中断
- PPHI 排名符合直觉（与人工排序相关性 > 0.7）
- 单周期成本 < $1.5

---

### Phase 3：优化与监控（1 周）
**目标**：成本优化、异常检测、报告生成

- [ ] 实测 Token 消耗，调整模型混合比例
- [ ] 实现异常检测（刷量、数据突变）
- [ ] 生成每日/每周报告
- [ ] 上线预算告警
- [ ] 文档完善

**验收标准**：
- 月成本控制在 $80 以内
- 异常检测准确率 > 90%
- 报告自动生成无需人工干预

---

## 九、风险与应对

| 风险 | 影响 | 应对策略 |
|------|------|---------|
| **法律风险**：论坛 ToS 禁止爬虫 | 高 | 优先使用官方 API（Reddit API），CHH 等论坛降低频率 + 使用代理 |
| **数据偏差**：中英文社区用户画像差异 | 中 | 分层分析，中文论坛和英文论坛分别计算 PPHI，最后加权合并 |
| **成本失控**：长篇技术贴 Token 超预期 | 中 | 设置单条输入上限（2000 tokens），超长贴仅提取关键段落 |
| **AI 幻觉**：过度推导隐藏需求 | 高 | 三层验证机制 + Munger 强制质疑 + 人工抽检 10% |
| **反爬封禁**：IP 被封 | 中 | 代理池 + 降低频率 + 失败自动切换数据源 |

---

## 十、与 auto-company 的关键差异

| 维度 | auto-company | GPU-Insight |
|------|--------------|-------------|
| **目标** | 赚钱（构建产品） | 分析（生成洞察） |
| **Agent 数量** | 14 个（全栈团队） | 8 个（专注分析） |
| **循环触发** | 30 秒（快速迭代） | 4 小时（数据采集周期） |
| **核心输出** | 代码 + 部署 | 报告 + 排名 |
| **防幻觉** | Munger 质疑决策 | Munger 质疑推导 + 历史数据验证 |
| **成本控制** | 按需使用 | 严格预算（$80/月） |

---

## 总结

这个架构设计完全基于 auto-company 的成功经验：

1. ✅ **真实专家人格**：Ben Thompson, Charlie Munger, Kelsey Hightower
2. ✅ **自治循环**：4h 自动运行，无需人工干预
3. ✅ **共识记忆**：consensus.md 作为跨周期接力棒
4. ✅ **防幻觉机制**：三层验证 + Munger 质疑
5. ✅ **成本可控**：混合模型 + 预算告警
6. ✅ **技能模块化**：反爬、去重、PPHI 计算等可复用

**下一步建议**：先用 Phase 1 的单源 MVP 验证核心假设（隐藏需求推导是否靠谱），确认可行后再投入完整开发。

你觉得这个方案如何？需要调整哪些部分？

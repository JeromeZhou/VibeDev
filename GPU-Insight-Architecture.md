# GPU-Insight 项目架构设计文档

> 基于 nicepkg/auto-company 和 affaan-m/everything-claude-code 的最佳实践
>
> 设计日期：2026-02-16

---

## 目录

1. [项目概述](#1-项目概述)
2. [两套 Agents 团队设计](#2-两套-agents-团队设计)
3. [详细 Token 消耗评估](#3-详细-token-消耗评估)
4. [项目目录结构](#4-项目目录结构)
5. [开发阶段 Agents 配置](#5-开发阶段-agents-配置)
6. [生产阶段 Agents 配置](#6-生产阶段-agents-配置)
7. [自动循环机制](#7-自动循环机制)
8. [成本优化策略](#8-成本优化策略)

---

## 1. 项目概述

### 1.1 核心需求

**显卡用户痛点智能分析系统（GPU-Insight）**

- **数据源**：Chiphell, NGA, 百度贴吧, ROG论坛, X(Twitter), Guru3D, Reddit
- **运行频率**：每 4 小时一次完整循环
- **核心功能**：
  1. 自动抓取论坛讨论（增量抓取）
  2. AI 深度分析（摘要 + 痛点提取 + 隐藏需求推导）
  3. PPHI 指数排名（加权算法）
  4. 防 AI 幻觉机制（多智能体交叉验证）
  5. 生成可视化报告

### 1.2 两阶段设计理念

| 阶段 | 目标 | Agents 团队 | 运行模式 |
|------|------|-------------|----------|
| **开发阶段** | 构建系统本身 | 软件开发专家团队 | 人工触发/按需运行 |
| **生产阶段** | 执行数据分析 | 数据分析专家团队 | 每4小时自动循环 |

---

## 2. 两套 Agents 团队设计

### 2.1 开发阶段团队（Development Agents）

**目标**：开发 GPU-Insight 系统的代码、数据库、爬虫、分析引擎

| Agent | 专家原型 | 职责 | 触发场景 |
|-------|----------|------|----------|
| **架构师** | Werner Vogels | 系统架构设计、技术选型、数据库设计 | 设计爬虫架构、选择存储方案 |
| **全栈开发** | DHH | 编写爬虫代码、API开发、前端界面 | 实现具体功能模块 |
| **数据工程师** | 自定义 | 数据清洗管道、ETL流程、去重算法 | 设计数据处理流程 |
| **QA测试** | James Bach | 测试爬虫稳定性、数据质量验证 | 发布前质量检查 |
| **DevOps** | Kelsey Hightower | 部署定时任务、监控告警、日志管理 | 配置4小时循环、部署到服务器 |
| **产品经理** | Don Norman | 定义报告格式、用户界面设计 | 设计输出报告的结构 |

### 2.2 生产阶段团队（Production Agents）

**目标**：系统上线后，执行实际的论坛数据分析任务

| Agent | 角色定位 | 核心能力 | Token 消耗 |
|-------|----------|----------|-----------|
| **Orchestrator** | 总指挥官 | 任务调度、状态监控、成本控制 | 低（仅调度逻辑） |
| **Scraper** | 数据猎手 | 多源并行抓取、反爬对抗、增量识别 | 极低（不用LLM） |
| **Cleaner** | 数据清洁工 | 去重、多语言标准化、噪声过滤 | 低（简单LLM调用） |
| **Analyst** | 痛点分析师 | 摘要生成、痛点识别、情感分析 | **高**（主要消耗） |
| **Insight** | 需求推导师 | 隐藏需求推导、因果推理 | **高**（主要消耗） |
| **Council** | 专家评审团 | 多视角验证、投票机制、防幻觉 | 中（仅10%数据触发） |
| **Ranker** | 排名计算器 | PPHI算法、趋势分析 | 极低（纯计算） |
| **Reporter** | 报告生成器 | 自然语言报告、数据可视化 | 低（模板化生成） |

---

## 3. 详细 Token 消耗评估

### 3.1 单周期（4小时）Token 消耗明细

**假设场景**：单次循环从7个平台共获取 **500条有效讨论**

#### Phase 1: Orchestrator（总指挥）

```
输入：系统状态检查 + 任务分配决策
- 读取 consensus.md（约 2,000 tokens）
- 生成任务分配计划（约 500 tokens）

Token 消耗：2,500 tokens/周期
```

#### Phase 2: Scraper（数据采集）

```
不使用 LLM，纯代码执行
- Playwright/Selenium 爬虫
- 代理池切换
- Cookie 管理

Token 消耗：0 tokens
```

#### Phase 3: Cleaner（数据清洗）

```
使用轻量级 LLM 处理边缘情况

场景1：语言识别（500条）
- 输入：标题+前100字（平均 50 tokens/条）
- 输出：语言标签（5 tokens/条）
- 小计：500 × 55 = 27,500 tokens

场景2：去重判断（仅相似度>0.8的，约50条）
- 输入：两篇文章对比（200 tokens/对）
- 输出：是否重复（10 tokens/对）
- 小计：50 × 210 = 10,500 tokens

Phase 3 总计：38,000 tokens
推荐模型：GPT-4o-mini（成本低）
```

#### Phase 4: Analyst（痛点分析）- **主要消耗**

```
对每条讨论进行深度分析

单条处理：
输入：
- 原文内容（平均 200 tokens）
- Prompt 模板（300 tokens，可缓存）
- 上下文指令（100 tokens）
总输入：600 tokens/条

输出：
- 一句话摘要（30 tokens）
- 痛点列表（50 tokens）
- 情感分析（20 tokens）
总输出：100 tokens/条

单条总计：700 tokens
500条总计：350,000 tokens

推荐模型：Claude 3.5 Sonnet（质量优先）
优化：Prompt 缓存可减少 50% 输入成本
实际消耗：约 200,000 tokens
```

#### Phase 5: Insight（隐藏需求推导）- **主要消耗**

```
基于痛点推导深层需求

单条处理：
输入：
- 原文 + Analyst 输出（300 tokens）
- 推理 Prompt（400 tokens，可缓存）
- 历史需求库检索（200 tokens）
总输入：900 tokens/条

输出：
- 隐藏需求描述（80 tokens）
- 推理过程（100 tokens）
- 置信度评分（20 tokens）
总输出：200 tokens/条

单条总计：1,100 tokens
500条总计：550,000 tokens

推荐模型：Claude 3.5 Sonnet
优化：Prompt 缓存 + 批处理
实际消耗：约 300,000 tokens
```

#### Phase 6: Council（专家评审）

```
仅对高权重数据（10%）进行多视角验证

触发条件：
- 置信度 < 0.7
- 或 PPHI 预估 > 8.0（高热度）
触发量：50条

三个 Persona 并行分析：
输入（每个Persona）：
- 完整上下文（500 tokens）
- Persona Prompt（300 tokens，可缓存）
总输入：800 tokens × 3 = 2,400 tokens/条

输出（每个Persona）：
- 评审意见（150 tokens）
总输出：150 tokens × 3 = 450 tokens/条

单条总计：2,850 tokens
50条总计：142,500 tokens

推荐模型：Claude 3.5 Sonnet
实际消耗：约 100,000 tokens（缓存优化）
```

#### Phase 7: Ranker（排名计算）

```
纯算法计算，不使用 LLM

- PPHI 指数计算
- 趋势分析
- 排序

Token 消耗：0 tokens
```

#### Phase 8: Reporter（报告生成）

```
模板化生成报告

输入：
- 排名数据（5,000 tokens）
- 报告模板（1,000 tokens，可缓存）
总输入：6,000 tokens

输出：
- Markdown 报告（3,000 tokens）

Phase 8 总计：9,000 tokens
推荐模型：GPT-4o-mini（成本低）
```

---

### 3.2 单周期 Token 总计

| Phase | Agent | 输入 Token | 输出 Token | 总计 | 模型 |
|-------|-------|-----------|-----------|------|------|
| 1 | Orchestrator | 2,000 | 500 | 2,500 | Sonnet |
| 2 | Scraper | 0 | 0 | 0 | - |
| 3 | Cleaner | 30,000 | 8,000 | 38,000 | 4o-mini |
| 4 | Analyst | 150,000 | 50,000 | 200,000 | Sonnet |
| 5 | Insight | 225,000 | 75,000 | 300,000 | Sonnet |
| 6 | Council | 80,000 | 20,000 | 100,000 | Sonnet |
| 7 | Ranker | 0 | 0 | 0 | - |
| 8 | Reporter | 6,000 | 3,000 | 9,000 | 4o-mini |

**单周期总计：649,500 tokens**

**优化后（Prompt缓存 + 批处理）：约 450,000 tokens**

---

### 3.3 月度成本估算

#### 基础数据

- 每天循环次数：24h ÷ 4h = **6次**
- 每月循环次数：6 × 30 = **180次**
- 月度总 Token：450,000 × 180 = **81,000,000 tokens**

#### 模型分配

| 模型 | 用途 | 月度Token | 输入价格 | 输出价格 | 月度成本 |
|------|------|-----------|---------|---------|---------|
| **Claude 3.5 Sonnet** | Analyst + Insight + Council | 60M (输入) + 15M (输出) | $3/1M | $15/1M | $180 + $225 = **$405** |
| **GPT-4o-mini** | Cleaner + Reporter | 5M (输入) + 1M (输出) | $0.15/1M | $0.6/1M | $0.75 + $0.6 = **$1.35** |

**月度总成本：约 $406**

---

### 3.4 成本优化方案

#### 方案 A：混合模型策略（推荐）

```
Phase 4 (Analyst)：
- 初步分析用 GPT-4o-mini（$20/月）
- 仅置信度<0.6的用 Sonnet 复审（$50/月）

Phase 5 (Insight)：
- 简单痛点用 DeepSeek-V3（$30/月）
- 复杂推理用 Sonnet（$80/月）

Phase 6 (Council)：
- 仅 PPHI>8.0 的触发（减少50%）

优化后月成本：约 $180
```

#### 方案 B：降低频率

```
改为每 6 小时一次（每天4次）
月度成本：$406 × (4/6) = $270
```

#### 方案 C：减少数据量

```
每次仅处理 300 条（而非 500 条）
月度成本：$406 × 0.6 = $244
```

#### 方案 D：Prompt 缓存激进优化

```
使用 Claude 的 Prompt Caching 功能：
- 缓存 Analyst/Insight 的 Prompt 模板
- 缓存历史需求库
- 缓存 Persona 定义

预计减少 60% 输入成本
优化后月成本：约 $200
```

---

### 3.5 推荐配置

**预算 $100/月**：
- 频率：每 6 小时
- 数据量：300 条/次
- 模型：混合策略（4o-mini + Sonnet）
- Prompt 缓存：开启

**预算 $200/月**：
- 频率：每 4 小时
- 数据量：500 条/次
- 模型：混合策略
- Prompt 缓存：开启

**预算 $400/月**：
- 频率：每 4 小时
- 数据量：500 条/次
- 模型：全 Sonnet（质量最优）
- Prompt 缓存：开启

---

## 4. 项目目录结构

参考 auto-company 和 everything-claude-code：

```
GPU-Insight/
├── .claude/
│   ├── CLAUDE.md                    # 项目章程（使命 + 安全红线）
│   ├── settings.json                # 全局配置
│   │
│   ├── agents/                      # Agents 定义
│   │   ├── dev/                     # 开发阶段 Agents
│   │   │   ├── architect-vogels.md
│   │   │   ├── fullstack-dhh.md
│   │   │   ├── data-engineer.md
│   │   │   ├── qa-bach.md
│   │   │   └── devops-hightower.md
│   │   │
│   │   └── prod/                    # 生产阶段 Agents
│   │       ├── orchestrator.md
│   │       ├── scraper.md
│   │       ├── cleaner.md
│   │       ├── analyst.md
│   │       ├── insight.md
│   │       ├── council-hardware.md
│   │       ├── council-product.md
│   │       ├── council-data.md
│   │       ├── ranker.md
│   │       └── reporter.md
│   │
│   ├── skills/                      # 可复用技能
│   │   ├── team/                    # 团队协作
│   │   │   └── SKILL.md
│   │   ├── scraping/                # 爬虫技能
│   │   │   ├── SKILL.md
│   │   │   └── anti-scraping.md
│   │   ├── deduplication/           # 去重算法
│   │   │   └── SKILL.md
│   │   ├── pain-extraction/         # 痛点提取
│   │   │   └── SKILL.md
│   │   ├── hidden-need-inference/   # 隐藏需求推导
│   │   │   └── SKILL.md
│   │   ├── pphi-ranking/            # PPHI 排名
│   │   │   └── SKILL.md
│   │   └── cost-monitor/            # 成本监控
│   │       └── SKILL.md
│   │
│   ├── hooks/                       # 自动化钩子
│   │   ├── pre-scrape.sh            # 抓取前检查
│   │   ├── post-analysis.py         # 分析后验证
│   │   └── alert-trigger.py         # 异常告警
│   │
│   ├── rules/                       # 业务规则
│   │   ├── source-weights.yaml      # 论坛权重配置
│   │   ├── keyword-dict.yaml        # 显卡术语词典
│   │   └── anti-hallucination.yaml  # 防幻觉规则
│   │
│   └── mcp/                         # MCP 服务器配置
│       ├── database-mcp.json
│       ├── proxy-pool-mcp.json
│       └── cache-mcp.json
│
├── memories/
│   ├── consensus.md                 # 共识记忆（跨周期状态）
│   └── scraper-state.json           # 爬虫状态（last_id）
│
├── prompts/                         # Prompt 模板库
│   ├── analyst-prompt.txt
│   ├── insight-prompt.txt
│   ├── council-hardware-persona.txt
│   ├── council-product-persona.txt
│   └── council-data-persona.txt
│
├── data/
│   ├── raw/                         # 原始语料（必须保留）
│   │   ├── 2026-02-16/
│   │   └── 2026-02-17/
│   ├── processed/                   # 处理后数据
│   └── archive/                     # 历史归档
│
├── outputs/
│   ├── reports/                     # 生成的分析报告
│   │   ├── daily/
│   │   └── weekly/
│   └── rankings/                    # PPHI 排名结果
│
├── logs/
│   ├── auto-loop.log                # 循环日志
│   ├── scraper.log                  # 爬虫日志
│   └── analysis.log                 # 分析日志
│
├── scripts/
│   ├── auto-loop.sh                 # 4小时自动循环脚本
│   ├── stop-loop.sh                 # 停止脚本
│   ├── monitor.sh                   # 监控脚本
│   └── install-daemon.sh            # 守护进程安装
│
├── src/                             # 源代码
│   ├── scrapers/                    # 爬虫实现
│   │   ├── chiphell.py
│   │   ├── nga.py
│   │   ├── tieba.py
│   │   ├── rog.py
│   │   ├── twitter.py
│   │   ├── guru3d.py
│   │   └── reddit.py
│   ├── cleaners/                    # 清洗模块
│   ├── analyzers/                   # 分析模块
│   ├── rankers/                     # 排名模块
│   └── utils/                       # 工具函数
│
├── config/
│   ├── development.yaml             # 开发环境配置
│   ├── production.yaml              # 生产环境配置
│   └── budget.yaml                  # 成本预算配置
│
├── docs/                            # Agents 产出文档
│   ├── architect/
│   ├── fullstack/
│   ├── data-engineer/
│   └── reports/
│
├── PROMPT.md                        # 每轮工作指令
├── Makefile                         # 常用命令
└── README.md                        # 项目说明
```


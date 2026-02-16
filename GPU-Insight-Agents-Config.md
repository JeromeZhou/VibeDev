# GPU-Insight Agents 配置详解（第二部分）

## 5. 开发阶段 Agents 配置

### 5.1 开发团队概览

| Agent | 专家原型 | 主要职责 | 文件位置 |
|-------|----------|----------|----------|
| Architect | Werner Vogels | 系统架构、技术选型 | `.claude/agents/dev/architect-vogels.md` |
| Fullstack | DHH | 编写代码、实现功能 | `.claude/agents/dev/fullstack-dhh.md` |
| Data Engineer | 自定义 | 数据管道、ETL | `.claude/agents/dev/data-engineer.md` |
| QA | James Bach | 测试、质量保证 | `.claude/agents/dev/qa-bach.md` |
| DevOps | Kelsey Hightower | 部署、监控 | `.claude/agents/dev/devops-hightower.md` |

---

## 6. 生产阶段 Agents 配置

### 6.1 生产团队概览

| Agent | 角色 | Token消耗/周期 | 模型选择 |
|-------|------|----------------|----------|
| Orchestrator | 总指挥 | 2,500 | Sonnet |
| Scraper | 数据采集 | 0 | - |
| Cleaner | 数据清洗 | 38,000 | 4o-mini |
| Analyst | 痛点分析 | 200,000 | Sonnet |
| Insight | 需求推导 | 300,000 | Sonnet |
| Council | 专家评审 | 100,000 | Sonnet |
| Ranker | 排名计算 | 0 | - |
| Reporter | 报告生成 | 9,000 | 4o-mini |

---

## 7. 自动循环机制

### 7.1 循环脚本设计

参考 auto-company 的 `auto-loop.sh`：

```bash
#!/bin/bash
# GPU-Insight 4小时自动循环脚本

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONSENSUS_FILE="$PROJECT_DIR/memories/consensus.md"
LOG_DIR="$PROJECT_DIR/logs"

# 配置
LOOP_INTERVAL=14400  # 4小时 = 14400秒
MODEL="sonnet"
CYCLE_TIMEOUT=3600   # 单周期超时1小时

# 循环计数
CYCLE_NUM=0

while true; do
    CYCLE_NUM=$((CYCLE_NUM + 1))
    echo "[$(date)] 开始第 $CYCLE_NUM 轮循环"

    # 1. 检查预算
    if ! check_budget; then
        echo "预算超支，暂停运行"
        send_alert "GPU-Insight 预算超支"
        sleep 86400  # 等待24小时
        continue
    fi

    # 2. 读取共识记忆
    CONSENSUS=$(cat "$CONSENSUS_FILE")

    # 3. 启动 Claude Code Agent Teams
    timeout $CYCLE_TIMEOUT claude -p \
        --model $MODEL \
        --prompt "你是 GPU-Insight 的 Orchestrator Agent。

当前周期：#$CYCLE_NUM
上轮共识：
$CONSENSUS

任务：
1. 组建生产团队（Scraper × 7 + Cleaner + Analyst + Insight + Council + Ranker + Reporter）
2. 执行完整的数据采集和分析流程
3. 更新 memories/consensus.md，记录本轮成果
4. 生成周报到 outputs/reports/

开始执行。" \
        > "$LOG_DIR/cycle-$CYCLE_NUM.log" 2>&1

    EXIT_CODE=$?

    # 4. 处理结果
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] 第 $CYCLE_NUM 轮成功完成"
    else
        echo "[$(date)] 第 $CYCLE_NUM 轮失败，退出码：$EXIT_CODE"
        send_alert "GPU-Insight 循环失败"
    fi

    # 5. 等待下一轮
    echo "[$(date)] 等待 $LOOP_INTERVAL 秒..."
    sleep $LOOP_INTERVAL
done
```

### 7.2 共识记忆结构

**文件位置**：`memories/consensus.md`

```markdown
# GPU-Insight 共识记忆

## 当前状态

**最后更新**：2026-02-16 15:30:00
**当前周期**：#42
**系统状态**：正常运行

---

## 本轮成果（Cycle #42）

### 数据采集
- Chiphell：87 条新帖
- NGA：124 条
- Reddit：156 条
- 百度贴吧：93 条
- ROG论坛：45 条
- Twitter：67 条
- Guru3D：28 条
- **总计**：600 条

### 分析结果
- 有效痛点：52 个
- 隐藏需求：12 个（高置信度 ≥ 0.8）
- Top 3 痛点：
  1. 显存容量焦虑（PPHI: 8.9）
  2. 功耗墙困境（PPHI: 7.5）
  3. 驱动稳定性问题（PPHI: 6.8）

### Token 消耗
- Analyst：185,000 tokens
- Insight：290,000 tokens
- Council：95,000 tokens
- 其他：15,000 tokens
- **总计**：585,000 tokens
- **成本**：$21.3

### 异常记录
- Reddit API 限流 2 次（已自动重试）
- NGA 去重率 82%（正常范围）

---

## 累计统计（本月）

- 总周期数：42 轮
- 总数据量：21,340 条
- 总成本：$387.5 / $400（预算使用率 96.9%）
- 平均单轮成本：$9.2

---

## 下一轮计划（Cycle #43）

### 优先级
1. 继续监控"显存容量焦虑"趋势
2. 深入分析"AI帧生成"新兴话题
3. 优化 Insight Agent 的 Prompt（降低 Token 消耗）

### 调整策略
- 无需调整，保持当前配置

---

## 爬虫状态

| 论坛 | Last Post ID | Last Timestamp | 状态 |
|------|--------------|----------------|------|
| Chiphell | 12847563 | 2026-02-16 15:20 | ✅ 正常 |
| NGA | 98234567 | 2026-02-16 15:18 | ✅ 正常 |
| Reddit | t3_abc123 | 2026-02-16 15:25 | ⚠️ 限流中 |
| 百度贴吧 | 7823456789 | 2026-02-16 15:15 | ✅ 正常 |
| ROG论坛 | 456789 | 2026-02-16 15:10 | ✅ 正常 |
| Twitter | 1234567890 | 2026-02-16 15:22 | ✅ 正常 |
| Guru3D | 987654 | 2026-02-16 15:12 | ✅ 正常 |
```

---

## 8. 成本优化策略

### 8.1 Prompt 缓存优化

**Claude 的 Prompt Caching 功能**：

```python
# Analyst Agent 的 Prompt 结构
system_prompt = """
你是一个显卡用户心理分析专家...
[完整的系统指令，约 300 tokens]
"""  # 标记为可缓存

# 每条分析
for post in posts:
    response = claude.messages.create(
        model="claude-3-5-sonnet-20241022",
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"}  # 缓存
            }
        ],
        messages=[
            {"role": "user", "content": f"原文：{post.content}"}
        ]
    )
```

**节省效果**：
- 首次调用：300 tokens（写入缓存）
- 后续调用：0 tokens（命中缓存）
- 500 条分析：节省 300 × 499 = 149,700 tokens
- **成本降低**：约 50%

---

### 8.2 批处理优化

**问题**：逐条调用 LLM 效率低

**方案**：批量处理

```python
# 原方案（逐条）
for post in posts:
    result = llm_analyze(post)  # 500次API调用

# 优化方案（批处理）
batch_size = 10
for i in range(0, len(posts), batch_size):
    batch = posts[i:i+batch_size]

    # 一次调用处理10条
    prompt = "请分析以下10条讨论：\n\n"
    for j, post in enumerate(batch):
        prompt += f"### 讨论 {j+1}\n{post.content}\n\n"

    results = llm_analyze_batch(prompt)  # 50次API调用
```

**节省效果**：
- API 调用次数：500 → 50（减少 90%）
- 网络开销：大幅降低
- 但 Token 消耗不变

---

### 8.3 模型降级策略

**动态降级**：

```python
def analyze_with_fallback(post):
    # 1. 先用便宜模型
    result = gpt4o_mini_analyze(post)

    # 2. 检查置信度
    if result["confidence"] < 0.6:
        # 置信度低，用高级模型重新分析
        result = claude_sonnet_analyze(post)

    return result
```

**成本对比**：

| 策略 | 高级模型使用率 | 月度成本 |
|------|----------------|----------|
| 全用 Sonnet | 100% | $405 |
| 全用 4o-mini | 100% | $25 |
| 动态降级（30%触发） | 30% | $140 |

---

### 8.4 数据采样策略

**问题**：每次处理 500 条是否必要？

**方案**：智能采样

```python
def smart_sampling(posts, target=300):
    # 1. 按热度排序
    posts_sorted = sorted(posts, key=lambda p: p.views + p.replies * 10, reverse=True)

    # 2. 取 Top 70%
    high_priority = posts_sorted[:int(len(posts) * 0.7)]

    # 3. 随机采样剩余 30%
    low_priority = random.sample(posts_sorted[int(len(posts) * 0.7):],
                                  target - len(high_priority))

    return high_priority + low_priority
```

**节省效果**：
- 数据量：500 → 300（减少 40%）
- 成本：$405 → $243

---

### 8.5 增量分析优化

**问题**：重复分析相似内容

**方案**：语义去重

```python
def semantic_dedup(posts):
    embeddings = get_embeddings([p.content for p in posts])

    unique_posts = []
    seen_embeddings = []

    for post, emb in zip(posts, embeddings):
        # 检查是否与已处理内容相似
        if not any(cosine_similarity(emb, seen) > 0.9 for seen in seen_embeddings):
            unique_posts.append(post)
            seen_embeddings.append(emb)

    return unique_posts
```

**节省效果**：
- 去重率：约 15%
- 成本：$405 → $344

---

### 8.6 综合优化方案

**推荐配置**（预算 $200/月）：

```yaml
优化策略组合：
  - Prompt 缓存：开启（-50% 输入成本）
  - 模型降级：30% 触发 Sonnet（-35% 总成本）
  - 智能采样：300条/次（-40% 数据量）
  - 语义去重：开启（-15% 重复内容）
  - 循环频率：每 6 小时（-33% 频率）

预期效果：
  原成本：$405/月
  优化后：$180/月
  质量损失：< 10%
```

---

## 9. 实施路线图

### Phase 1：MVP 验证（1周）

**目标**：验证核心流程可行性

**任务**：
1. 搭建基础项目结构
2. 实现单个论坛爬虫（Chiphell）
3. 配置 Analyst + Insight Agents
4. 手动运行一次完整流程
5. 人工评估 100 条输出质量

**成功标准**：
- 痛点提取准确率 > 80%
- 隐藏需求合理性 > 70%
- 单次成本 < $5

---

### Phase 2：多源集成（2周）

**目标**：接入全部 7 个数据源

**任务**：
1. 实现剩余 6 个爬虫
2. 配置反爬策略（代理池、UA轮换）
3. 部署 4 小时定时任务
4. 配置 Council 评审机制
5. 实现 PPHI 排名算法

**成功标准**：
- 7 个论坛稳定抓取
- 单周期成功率 > 95%
- PPHI 排名符合直觉

---

### Phase 3：成本优化（1周）

**目标**：降低月度成本到预算内

**任务**：
1. 实现 Prompt 缓存
2. 配置模型降级策略
3. 实现智能采样
4. 优化批处理逻辑
5. 部署成本监控告警

**成功标准**：
- 月度成本 < $200
- 质量损失 < 10%

---

### Phase 4：生产部署（1周）

**目标**：稳定运行，自动生成报告

**任务**：
1. 配置守护进程（systemd/launchd）
2. 部署监控告警（Sentry）
3. 实现周报自动生成
4. 配置数据备份
5. 编写运维文档

**成功标准**：
- 连续运行 7 天无故障
- 自动生成��报
- 异常自动告警

---

## 10. 关键文件清单

### 10.1 必须创建的文件

```
GPU-Insight/
├── .claude/
│   ├── CLAUDE.md                    # 项目章程
│   ├── settings.json                # 全局配置
│   ├── agents/dev/                  # 5个开发 Agents
│   ├── agents/prod/                 # 8个生产 Agents
│   ├── skills/                      # 7个技能模块
│   └── rules/                       # 3个规则配置
│
├── memories/
│   └── consensus.md                 # 共识记忆
│
├── prompts/
│   ├── analyst-prompt.txt           # 痛点分析 Prompt
│   ├── insight-prompt.txt           # 需求推导 Prompt
│   └── council-*.txt                # 3个评审 Persona
│
├── scripts/
│   ├── auto-loop.sh                 # 自动循环脚本
│   ├── check-budget.sh              # 预算检查
│   └── send-alert.sh                # 告警脚本
│
└── config/
    ├── production.yaml              # 生产配置
    └── budget.yaml                  # 预算配置
```

---

## 11. 总结

### 11.1 核心设计亮点

1. **两套 Agents 分离**：开发团队 vs 生产团队，职责清晰
2. **详细成本评估**：单周期 450K tokens，月度 $180-$400
3. **多层优化策略**：Prompt缓存 + 模型降级 + 智能采样
4. **防幻觉机制**：Expert Council 三视角交叉验证
5. **自动循环**：参考 auto-company，4小时自主运行

### 11.2 预算建议

| 预算 | 配置 | 适用场景 |
|------|------|----------|
| $100/月 | 6h频率 + 300条 + 混合模型 | 个人研究 |
| $200/月 | 4h频率 + 500条 + 混合模型 | 小团队 |
| $400/月 | 4h频率 + 500条 + 全Sonnet | 商业项目 |

### 11.3 下一步行动

1. 阅读完整架构文档
2. 确认预算和配置
3. 开始 Phase 1 MVP 开发
4. 验证单次流程质量
5. 逐步扩展到全量运行

---

**文档完成时间**：2026-02-16
**作者**：Kiro AI
**版本**：v1.0

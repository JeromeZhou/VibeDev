# GPU-Insight 共识记忆

> 最后更新：2026-02-18 08:41
> 更新者：开发团队 v7 数据累积修复 + 新数据源
> 轮次：#7（GPU标签累积 + 互动数据透传 + 新数据源 + UI增长感）

## 当前共识

### v7 团队共识（本轮新增）

#### 1. GPU 标签跨轮次动态累积
- 修复：ranker 从 pphi_history（累积数据）加载替代 pain_points（原始数据）
- 效果：GPU 标签随每次 pipeline 运行持续增长，不再丢失历史标签
- _hist_mentions 保留历史 mentions 数避免重置

#### 2. 互动数据全链路透传
- pphi_history 新增 total_replies/total_likes 列
- save_rankings 保存互动数据，ranker 输出完整互动信息
- PPHI interaction 分数真正生效

#### 3. 新数据源扩展（3→7 个活跃源）
- 新增：Bilibili（~100帖/轮）、V2EX（~20帖/轮）、MyDrivers（~23帖/轮）、TechPowerUp（~51帖/轮）
- Tieba 改为白天时段自动启用（8:00-22:00）
- 总计 ~259 帖/轮，成本 ~$0.18/轮

#### 4. Dashboard 增长感展示
- 统计卡片：当前痛点 / 累计帖子 / 分析轮次 / 数据源
- 本轮变化指示器：+N 新痛点 / +N 新型号
- GPU 标签展示扩展到 6 个 + 溢出计数

#### 5. 痛点详情页 PPHI 趋势图
- Chart.js 双 Y 轴：PPHI 分数 + Mentions 数
- 模糊匹配历史数据，最近 12 轮

#### 6. 历史详情页 Accordion 展开
- 点击展开显示：AI 推理需求、GPU 型号、厂商、来源链接

### v6 团队共识

#### 1. 语义去重（P0-1）
- 本地规范化：去掉"显卡"前缀 + 括号分类标签，统一聚合 key
- 效果：26 个重复痛点 → 16-17 个独立痛点
- 零 token 成本

#### 2. PPHI 公式重设计（P0-2）
- 新权重：frequency 30% + source_quality 20% + interaction 15% + cross_platform 15% + freshness 20%
- 对数缩放：log2(mentions+1) * 20，避免封顶过低
- 跨平台加成：多论坛出现的痛点优先级更高
- freshness 提升到 20% 防止老数据长期霸榜

#### 3. 防幻觉机制（P0-3）
- Devil's Advocate (Munger) 审查：对 confidence > 0.6 的隐藏需求反向论证
- 推理链展示：details.html 展示完整推理过程
- 被否决需求标记 munger_rejected，confidence 降为 0.2

#### 4. 成本控制三级降级（P0-4）
- 80%: 警告 | 90%: 自动降级模型(Qwen2.5-7B) | 95%: 暂停非关键任务
- pipeline 步骤 5/6/6.5 前各检查一次预算

#### 5. 累积排名 + 历史浏览（v5）
- ranker 从 DB 加载历史痛点 + 当轮合并，统一计算 PPHI
- 新增 /history 和 /history/{run_date} 页面
- 导航栏统一：仪表盘 / 趋势 / 历史

#### 6. 共识自动更新（P1-5）
- pipeline 步骤 10 自动更新 consensus.md 的 Top 痛点和成本
- src/reporters/consensus_updater.py

### v4 团队共识

#### 1. Web UI 全面改版（Linear/Vercel 设计系统）
- 设计参考：Linear、Vercel Dashboard、Grafana 暗色主题
- CSS 变量系统：7 层背景色 + 3 层边框 + 3 层文字 + 7 个强调色
- 字体：Inter + Noto Sans SC + JetBrains Mono（数据用等宽）
- 克制原则：无 backdrop-filter blur、无 translateY hover、无 glow 效果
- 排名列表展示全部痛点（不再截断 10 条），>10 条折叠展开
- API 链接替换为"关于"弹窗，解释 PPHI 算法
- 三页统一设计 token，视觉一致性 100%

#### 2. 召回率优化
- 新增 24 个信号词（12 英文 + 12 中文）：throttle, downclock, 降频, 温度墙, 翻车, 掉驱动 等
- L3 阈值放宽：max_deep 30→50, max_light 20→50
- L2 prompt 优化：class=2 覆盖技术问题、性能调优、驱动兼容
- Reddit SSL 容错：httpx.ReadError 自动 verify=False 重试

### v2 团队共识

#### 1. GPU 产品标签方案
- L0 本地词典正则（零 token）：`config/gpu_products.yaml` + `src/utils/gpu_tagger.py`
- 覆盖：NVIDIA/AMD/Intel 全系列 + 15 家板卡厂商 + 中文别名
- L3 LLM 补充：深度分析 prompt 中增加 gpu_products 字段
- 测试：5/5 组测试通过（基础型号、灵活格式、中文别名、帖子打标、空内容）

#### 2. URL 全链路追溯
- 爬虫阶段：每条帖子必须有 `url` 字段（Reddit 已有 permalink）
- 漏斗阶段：dict 透传，url 不丢失
- 痛点提取：LLM 输出 `related_post_indices`，代码层反查 URL 写入 `source_urls`
- Schema：PainPoint 增加 `source_urls: list[str]` 和 `source_post_ids: list[str]`

#### 3. 痛点 + 推理需求合并结构
- 新增 `PainInsight` 复合类型（schema.py）
- 实现 `merge_pain_insights()` 函数合并两步输出
- 只对 L2 class=2 的痛点做推理需求推导（控制成本）
- class=1 的 `inferred_need` 为 null，后续升级再补

### Top 痛点（v3 端到端验证 2026-02-17）
1. 显卡性能问题 — RTX 3090, RTX 3090 Ti, RTX 5070, RTX 5070 Ti, RTX 5090, RX 6750 XT, RX 9070, RX 9070 XT（PPHI 81.6）→ 需求：追求极致的流畅度与算力利用率，希望硬件能持续满血输出
2. 显卡散热问题 — RTX 3060, RTX 3060 Ti, RTX 3080, RTX 3080 Ti, RTX 4090, RTX 5070, RTX 5070 Ti, RTX 5080, RTX 5090（PPHI 70.2）→ 需求：提升显卡性能稳定性和使用寿命
3. 显卡驱动问题 — Arc A770, GTX 1660, GTX 1660 Super, GTX 1660 Ti, RTX 3080, RTX 3080 Ti（PPHI 63.2）→ 需求：智能化的驱动自动适配与零维护体验
4. 显卡驱动更新后性能提升，但内存成本增加导致价格上涨 — 通用（PPHI 60.1）→ 需求：寻求性价比更高的显卡解决方案，以平衡性能提升和成本增加的需求
5. 游戏帧数低，画面模糊，崩溃闪退 — 通用（PPHI 58.8）→ 需求：对游戏性能和稳定性的更高要求，以获得更流畅和稳定的游戏体验。

### 已验证的隐藏需求
- 性能监控与一键优化功能以实现帧率稳定（RTX 5090）
- 高性价比显卡推荐或最佳购买时机指导（RTX 5090）
- 低功耗高性能平衡方案（RX 7700 XT）
- 高负载低噪音散热解决方案（RX 7700 XT）

### 已否决的推导
_本轮无否决_

## 三层漏斗共识（v1 轮次）
- L1 本地信号排序（0 token）：排除模式降分 + 痛点信号词加分，不丢弃任何帖子
- L2 LLM 批量分类（极低 token）：50 条标题一次调用，输出 0/1/2
- L3 深度分析（定向 token）：class=2 深度分析 + class=1 轻度分析
- 验证结果：91 帖 → 30 有信号 → 9 明确痛点 → 7 个独立痛点，成本 ~$0.003

## 数据质量评估
- 抓取成功率：Reddit 90%+（SSL 容错），NGA 100%，Bilibili 100%，V2EX 100%，MyDrivers 100%，TechPowerUp 100%，Chiphell 0%，Tieba 白天可用
- 数据重复率：0%（去重机制有效）
- GPU 标签识别率：测试 17/17 用例通过
- 评论区覆盖：Reddit Top5 评论 + NGA Top5 回复
- 每轮数据量：~259 帖（7 个活跃源）

## 成本追踪
- 本轮消耗：$0.0006
- 月度累计：$3.76
- 预算剩余：$76.24 / $80

## 开发进度
- [x] 项目骨架搭建（40 文件，2065 行）
- [x] 14 个 Agent 定义
- [x] 核心 Python 模块（scrapers, cleaners, analyzers, rankers, reporters）
- [x] LLM 客户端（Anthropic + OpenAI + 智谱/硅基流动）
- [x] Reddit 爬虫 v2（三端点 + 信号分数 + GPU 标签）
- [x] GLM-5 pipeline 验证通过
- [x] 三层漏斗（funnel.py）验证通过
- [x] 18 个 pytest 单元测试全部通过
- [x] GPU 产品标签识别器（gpu_tagger.py + gpu_products.yaml）
- [x] URL 全链路追溯（schema + analyzers 改造）
- [x] PainInsight 合并结构（schema + merge_pain_insights）
- [x] Web 界面 3 个页面（Dashboard, Trends, Details）
- [x] 统一错误处理 + 数据 Schema
- [x] 完整 main.py pipeline 端到端运行（含新结构）✅ 2026-02-17
- [x] 修复 cleaner 双重去重 bug（爬虫层已去重，cleaner 不再重复过滤）
- [x] Web UI v4 改版（Linear/Vercel 设计系统，3 页全部重写）✅ 2026-02-17
- [x] 召回率优化（24 信号词 + L3 阈值 + L2 prompt）✅ 2026-02-17
- [x] Reddit SSL 容错（verify=False fallback）✅ 2026-02-17
- [x] 累积排名（历史+当轮合并 PPHI）✅ 2026-02-17
- [x] 历史浏览页（/history + /history/{run_date}）✅ 2026-02-17
- [x] 语义去重（本地规范化，26→16 痛点）✅ 2026-02-17
- [x] PPHI 公式重设计（对数缩放+跨平台+新鲜度）✅ 2026-02-17
- [x] 防幻觉 Devil's Advocate Munger 审查 ✅ 2026-02-17
- [x] 成本控制三级降级（80%警告/90%降级/95%暂停）✅ 2026-02-17
- [x] 共识自动更新（pipeline 步骤 10）✅ 2026-02-17
- [x] 推理链 + Munger 审查结果 UI 展示 ✅ 2026-02-17
- [x] 新数据源：Bilibili + V2EX + MyDrivers + TechPowerUp ✅ 2026-02-17
- [x] GPU 标签跨轮次动态累积（pphi_history 替代 pain_points）✅ 2026-02-17
- [x] 互动数据全链路透传（pphi_history 新增 total_replies/likes）✅ 2026-02-17
- [x] Dashboard 增长感展示（本轮变化指示器 + 统计卡片优化）✅ 2026-02-17
- [x] 痛点详情页 PPHI 趋势图（Chart.js 双 Y 轴）✅ 2026-02-17
- [x] PPHI freshness 权重调优（15%→20%）✅ 2026-02-17
- [x] Munger 三级评分制（strong/moderate/weak 替代通过/否决）✅ 2026-02-17
- [x] 痛点细化 prompt（要求具体描述而非笼统）✅ 2026-02-17
- [x] 评论区抓取：Reddit Top5 评论 + NGA Top5 回复 ✅ 2026-02-17
- [x] auto-loop.bat 纯 ASCII 定时循环 ✅ 2026-02-17
- [x] start-web.bat 一键启动脚本（port 9000）✅ 2026-02-17
- [x] 历史详情页 Accordion 展开 ✅ 2026-02-17
- [x] 隐藏需求闭环同步（DB+JSON+Web UI 完整推理链+Munger审查）✅ 2026-02-17
- [x] 报告页 /report（打印友好，浏览器 PDF 导出）✅ 2026-02-17
- [x] CSV 导出 /api/export/csv ✅ 2026-02-17
- [x] 趋势页 Bump Chart 排名演变视图 ✅ 2026-02-17
- [x] 全站导航统一（报告入口）✅ 2026-02-17
- [ ] Chiphell 爬虫修复（需登录 Cookie 或 Playwright）

## Next Action
- [x] 累积排名 + 历史浏览页 ✅ 2026-02-17
- [x] 语义去重 + PPHI 公式重设计 ✅ 2026-02-17
- [x] 防幻觉 Munger 审查 + 推理链展示 ✅ 2026-02-17
- [x] 成本控制三级降级 + 共识自动更新 ✅ 2026-02-17
- [x] 部署 Web 界面本地预览（port 9000）✅ 2026-02-17
- [x] GPU 标签动态累积 + 互动数据透传 ✅ 2026-02-17
- [x] Munger 三级评分 + 痛点细化 + 评论区抓取 ✅ 2026-02-17
- [x] auto-loop.bat Windows 定时循环 ✅ 2026-02-17
- [x] 运行 pipeline 验证评论区抓取 + Munger 三级评分效果 ✅ 2026-02-18
- [x] 反爬基础设施统一（UA池+safe_request+限流处理）✅ 2026-02-18
- [x] Reddit 403 修复（真实UA+old.reddit降级）✅ 2026-02-18
- [x] 历史页痛点演变视图（Bump Chart 已实现）✅ 2026-02-17
- [ ] 大数据量压力测试（>200 帖漏斗表现）
- [ ] 修复 Chiphell 爬虫（Playwright + Cookie）
- [x] Bilibili 412 限流优化（11→6关键词+早停）✅ 2026-02-18
- [x] MyDrivers URL 更新（首页替代404频道）✅ 2026-02-18
- [x] V2EX 节点清理（只保留 hardware+apple）✅ 2026-02-18
- [x] Tieba 完全禁用（百度403反爬）✅ 2026-02-18
- [x] Reddit v4 重构（统一safe_request+搜索关键词7→4）✅ 2026-02-18
- [x] 语义去重改进（"显卡性能问题"与"性能"应合并，去掉"问题"后缀）✅ 2026-02-18
- [ ] git push 到 GitHub

## 历史趋势
| 日期 | 数据量 | 痛点数 | 成本 |
|------|--------|--------|------|
| 2026-02-16 | 45 条（Reddit） | 5 个 | $0.33 |
| 2026-02-17 | 12 条（Reddit+NGA） | 5 个 | $0.06 |
| 2026-02-17 | 3 条（NGA） | 1 个 | $0.003 |

## 人工备注
- 使用硅基流动 SiliconFlow 的 GLM-5 作为 LLM
- 后期可考虑混合模型策略（简单任务用 Qwen3-8B 降成本）

## Git 提交记录
- `90cb91f` feat: v6 P0全修复 — 防幻觉Munger审查 + 成本控制三级降级 + 共识自动更新 + 推理链UI展示
- `17dbbc8` fix: P0-1 语义去重(本地规范化合并) + P0-2 PPHI公式重设计(对数缩放+跨平台+新鲜度)
- `1a1c888` feat: v5 累积排名(历史+当轮合并PPHI) + 历史浏览页 + 导航栏统一
- `bab83be` docs: 更新共识记忆至v4（UI改版+召回率优化）
- `b4a6db6` feat: v4 UI全面改版(Linear/Vercel设计系统) + 召回率优化(信号词+L3阈值+L2 prompt)
- `c883fdf` feat: v3 端到端验证通过 + UI改版 + cleaner去重修复 + Reddit SSL容错
- `12a94de` feat: 三层漏斗 + Reddit v2 + Tieba 爬虫
- `9c0d355` feat: 开发团队协同推进 — 6 Agent 产出
- `80c35e8` feat: 完成真实 LLM pipeline 验证
- `d9ed010` feat: GPU-Insight Phase 1 MVP 骨架实施
- `819e059` feat: GPU-Insight 完整架构设计

# GPU-Insight 共识记忆

> 最后更新：2026-02-17 13:25
> 更新者：开发团队 v3 端到端验证
> 轮次：#3（完整 pipeline 端到端通过 + cleaner 去重修复）

## 当前共识

### v2 团队共识（本轮新增）

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
1. 显卡兼容性问题 — RTX 5070/5070 Ti（PPHI 48.3）
2. 显卡性能问题 — RTX 5090（PPHI 43.4）→ 需求：性能监控与一键优化
3. 显卡价格问题 — RTX 5090（PPHI 38.6）→ 需求：高性价比推荐/最佳购买时机
4. 显卡功耗问题 — RX 7700 XT（PPHI 35.7）→ 需求：低功耗高性能平衡
5. 显卡散热问题 — RX 7700 XT（PPHI 35.7）→ 需求：高负载低噪音散热方案

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
- 抓取成功率：Reddit 部分成功（r/amd SSL 偶发失败），NGA 100%，Chiphell 0%，Tieba 0%
- 数据重复率：0%（去重机制有效，已修复 cleaner 双重去重 bug）
- GPU 标签识别率：测试 17/17 用例通过

## 成本追踪
- 本轮消耗：$0.06（完整 pipeline 端到端）
- 月度累计：$2.54
- 预算剩余：$77.46 / $80

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
- [ ] Chiphell 爬虫修复（需登录 Cookie）
- [ ] auto-loop.sh 实际部署测试

## Next Action
- [x] 用真实数据跑完整 pipeline（含 GPU 标签 + URL 追溯 + PainInsight）✅ 2026-02-17
- [ ] 部署 Web 界面本地预览（port 8080）
- [ ] 修复 Chiphell 爬虫（Cookie 或 Playwright 方案）
- [ ] Reddit r/amd SSL 错误排查
- [ ] 召回率测试（QA 建议）
- [ ] auto-loop.sh 定时循环部署测试

## 历史趋势
| 日期 | 数据量 | 痛点数 | 成本 |
|------|--------|--------|------|
| 2026-02-16 | 45 条（Reddit） | 5 个 | $0.33 |
| 2026-02-17 | 12 条（Reddit+NGA） | 5 个 | $0.06 |

## 人工备注
- 使用硅基流动 SiliconFlow 的 GLM-5 作为 LLM
- 后期可考虑混合模型策略（简单任务用 Qwen3-8B 降成本）

## Git 提交记录
- `待提交` feat: GPU 产品标签 + URL 追溯 + PainInsight 合并结构
- `12a94de` feat: 三层漏斗 + Reddit v2 + Tieba 爬虫
- `9c0d355` feat: 开发团队协同推进 — 6 Agent 产出
- `80c35e8` feat: 完成真实 LLM pipeline 验证
- `d9ed010` feat: GPU-Insight Phase 1 MVP 骨架实施
- `819e059` feat: GPU-Insight 完整架构设计

# v9 计划：分层 AI 过滤 + 漏斗整合（团队审批版）

## 背景
当前 pipeline 存在两个问题：
1. NGA fid=436 等杂板块抓到大量手机/路由器帖子，虽然漏斗能过滤，但 DB 存了噪音
2. L1 无信号词的帖子直接跳过 L2，可能漏掉隐含痛点（标题没信号但内容有痛点）

## 团队审查结论（Architect Vogels + QA Bach）
1. Cleaner AI 过滤和 Funnel L2 功能重叠 → 合并为独立模块
2. Cleaner 在 GPU Tagger 之前运行 → _gpu_tags 快速通道无效 → 移到 Tagger 之后
3. Shadow Mode 先行 → 标记但不删除，验证准确率后再硬过滤
4. 无信号帖子不再直接标 class=0 → 全部送 L2 判断

## 最终架构

### Pipeline 顺序
```
Scrape → Clean(去重+规范化) → GPU Tag → AI 相关性过滤(新) → 三层漏斗 → 痛点提取 → ...
```

### AI 相关性过滤（src/filters/__init__.py）
- 位置：GPU Tagger 之后、漏斗之前
- 快速通道：专业源(videocardz/techpowerup/guru3d/chiphell) + 已打标(_gpu_tags) → 直接保留
- Layer 1：标题批量分类（30条/批，~1,300 token）→ 2=相关 / 1=不确定 / 0=不相关
- Layer 2：内容+评论深度判断（仅对"不确定"的，10条/批，~5,000 token）
- Shadow Mode：初期只标记 `_relevance_shadow_drop`，不实际删除

### 漏斗改进（src/analyzers/funnel.py）
- L1：信号排序不变
- L2：所有帖子都送 LLM 分类（无信号帖子不再直接标 class=0）
- L3：不变

### 预估消耗（日常 55 条新帖/轮）
- AI 过滤 Layer 1：~1,300 token，2 批，~10s
- AI 过滤 Layer 2：~5,000 token，1-2 批，~15s
- 合计：~6,300 token/轮，~25s，$0（免费模型 glm-4-9b-chat）

### DB 变更
- posts 表新增 `relevance_class INTEGER DEFAULT -1`（-1=未判断, 0=不相关, 1=不确定, 2=相关）
- posts 表新增 `relevance_reason TEXT`（判断理由，方便调试）

### Admin 页面
- 新增 AI 过滤统计卡片：已判断数、保留数、排除数、保留率
- 新增最近被排除的帖子列表（方便人工复查是否误杀）
- 版本号更新为 v9

## 热词机制保持不变
- 热词发现来源：痛点名称 + 隐藏需求（AI 分析输出），不是 cleaner 过滤阶段
- 热词更新时机：pipeline 步骤 10.5（discover_hot_words + discover_from_db）
- AI 过滤不影响热词发现流程

## 不做的事
- 不改爬虫层（关键词搜索保留，论坛按板块抓取保留）
- 不做历史回填（后续单独处理）
- 不改 PPHI 排名逻辑
- 不改热词发现机制

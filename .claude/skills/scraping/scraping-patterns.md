---
name: scraping-patterns
description: "数据采集模式 — 各论坛 API/HTML 解析策略和数据结构"
---

# Scraping Patterns Skill — 数据采集模式

## 统一数据结构

每条帖子必须包含以下字段：
```python
{
    "id": "source_uniqueId",      # 全局唯一 ID
    "source": "reddit",            # 数据源名称
    "_source": "reddit",           # 冗余标记（pipeline 用）
    "title": "帖子标题",
    "content": "标题+正文内容",     # 最长 2000 字符
    "url": "https://...",          # 原始链接
    "author_hash": "sha256[:16]",  # 隐私保护
    "replies": 42,                 # 回复/评论数
    "likes": 128,                  # 点赞/投票数
    "language": "zh-CN",           # zh-CN 或 en
    "timestamp": "ISO8601",        # 发布时间
    "comments": "热门评论文本",     # 可选，热帖评论
    "gpu_tags": {},                # GPU tagger 填充
}
```

## 各源采集策略

### Reddit（httpx + JSON API）
- 端点: `https://www.reddit.com/r/{sub}/new.json?limit=50`
- 认证: 无需（公开 API）
- 评论: `https://www.reddit.com/comments/{id}.json?limit=10&sort=top`
- 注意: SSL EOF 常见，需要 verify=False 降级
- 频率: 3 个 subreddit × 50 条 = ~150 条/轮

### NGA（httpx + JSONP）
- 端点: `https://bbs.nga.cn/thread.php?fid={fid}&page=1&__output=11`
- 正文: `https://bbs.nga.cn/read.php?tid={tid}&page=1&__output=11`
- JSONP 清理: `window.script_muti_get_var_store = {...}` → 去前缀
- `__T` 字段: 可能是 dict 或 list，必须 isinstance() 检查
- 频率: 2 个版块 × ~70 条 = ~140 条/轮

### Bilibili（httpx + 搜索 API）
- 搜索: `https://api.bilibili.com/x/web-interface/search/type?search_type=video&keyword={kw}`
- 视频信息: `https://api.bilibili.com/x/web-interface/view?bvid={bvid}`
- 评论: `https://api.bilibili.com/x/v2/reply/main?type=1&oid={aid}&mode=3`
- 必需 Cookie: buvid3, b_nut, CURRENT_FNVAL
- 必需 Header: Origin, X-Requested-With, Sec-Fetch-*
- 412 限流: 立即停止，不重试
- 频率: 5 关键词 × 20 条 = ~100 条/轮

### V2EX（httpx + 官方 API）
- 列表: `https://www.v2ex.com/api/v2/nodes/{node}/topics?p=1`
- 回复: `https://www.v2ex.com/api/v2/topics/{id}/replies?p=1`
- 认证: Bearer Token（config.yaml）
- 频率: 2 节点 × ~10 条 = ~20 条/轮

### TechPowerUp（httpx + HTML 解析）
- 端点: `https://www.techpowerup.com/gpu-news/`
- 解析: `<a class="articleTitle" href="...">标题</a>`
- 频率: ~50 条/轮

### MyDrivers/快科技（httpx + HTML 解析）
- 端点: `https://news.mydrivers.com/blog/20250218.htm`（按日期）
- 解析: 新闻列表 HTML
- 频率: ~30 条/轮

### VideoCardz（需要 Playwright）
- 状态: Cloudflare + JS 渲染，httpx 无法获取内容
- 降级: 当前静默跳过
- 修复: 需要安装 Playwright + chromium

## 增量抓取机制
- 每个源维护 `.last_id` 文件
- DB 层 `filter_new_posts()` 通过 content_hash 去重
- 原始数据永久保存到 `data/raw/{source}/{date}.jsonl`

## 评论抓取策略
- 只抓热帖（replies > 5 或 likes > 10）
- 每帖最多 10-15 条评论
- 按热度排序，取 Top N
- 评论文本拼接到 post.comments 字段（最长 2000 字符）

## 热词发现
- 从抓取内容中提取高频词
- 中文分词 + 英文 tokenize
- 衰减机制: 14 天半衰期
- 自动补充到搜索关键词池

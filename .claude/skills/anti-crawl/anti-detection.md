---
name: anti-detection
description: "反爬对抗专家 — 绕过网站反爬机制的策略和实现"
---

# Anti-Detection Skill — 反爬对抗

## 核心知识

### 浏览器指纹模拟
- User-Agent 必须与 Accept/Accept-Language/Accept-Encoding 一致（Chrome UA 配 Chrome 的 Accept 头）
- Sec-Fetch-* 头族：`Sec-Fetch-Dest: document`, `Sec-Fetch-Mode: navigate`, `Sec-Fetch-Site: none`
- API 请求用 XHR 指纹：`Sec-Fetch-Dest: empty`, `Sec-Fetch-Mode: cors`, `Sec-Fetch-Site: same-site`
- 不要混用移动端 UA 和桌面端 Accept 头

### 请求节奏
- 人类浏览间隔：3-15 秒（非均匀分布，用 log-normal 或 beta 分布）
- 关键词搜索间递增延迟：第 1 个 4s，第 2 个 5s，第 3 个 7s...
- 同一 session 内请求不超过 30 次/分钟
- 每个 session 持续 5-15 分钟后换 session
- ±20% 抖动（jitter）避免固定间隔被检测

### Cookie/Session 策略
- Bilibili: 必须 buvid3 + buvid4 + b_nut + SESSDATA（匿名可不要 SESSDATA）
- Reddit: 不需要 cookie，但需要 SSL 降级容错
- NGA: 需要 __ngtmp cookie，否则返回空数据
- Cloudflare 站点: 需要 cf_clearance cookie（只能通过浏览器获取）

### 常见反爬响应
| 状态码 | 含义 | 策略 |
|--------|------|------|
| 412 | 风控拦截（Bilibili） | 换 session cookie，增加延迟 |
| 429 | 限流 | 指数退避：30s → 60s → 120s |
| 403 | 禁止访问 | SSL 降级重试，换 UA，检查 Referer |
| 503 | Cloudflare 验证 | 需要 Playwright 或 cf_clearance |
| 200 + 空内容 | JS 渲染页面 | 需要 Playwright |

### 指数退避公式
```python
wait = min(base_wait * (2 ** attempt), max_wait) + random.uniform(0, base_wait * 0.3)
```

### Playwright 降级策略
当 httpx 无法获取内容时（JS 渲染站点如 VideoCardz）：
1. 首选 httpx（零依赖，快速）
2. 降级到 Playwright headless（需要安装 chromium）
3. 最终降级到 Google Cache 或 RSS 源

## 项目特定规则
- 遵守 robots.txt，不做 DDoS
- 单源失败不影响其他源
- 每个源独立的限流状态追踪
- 所有请求通过 BaseScraper.safe_request() 统一管理

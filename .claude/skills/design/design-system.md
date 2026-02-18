---
name: ui-design-system
description: "UI 设计系统 — Vercel/Linear 风格的深色/浅色双主题设计规范"
---

# UI Design System Skill — 设计系统

## 设计哲学
- **克制即高级** — 不用 glow、blur、translateY hover
- **信息密度优先** — 每个像素都有意义
- **双主题原生** — 深色/浅色通过 CSS 变量切换，零 JS 开销

## 色彩系统

### 深色主题（默认）
```css
--bg-base: #000000;        /* 纯黑背景 — Vercel 风格 */
--bg-surface: #0a0a0a;     /* 卡片背景 */
--bg-elevated: #111111;    /* 弹出层 */
--bg-hover: #1a1a1a;       /* 悬停态 */
--text-primary: #ededed;   /* 主文字 */
--text-secondary: #888888; /* 次要文字 */
--text-tertiary: #666666;  /* 辅助文字 */
--border-default: #333333; /* 边框 */
--border-subtle: #222222;  /* 细微边框 */
--accent-blue: #0070f3;    /* 主强调色 — Vercel 蓝 */
--accent-green: #50e3c2;   /* 成功/上升 */
--accent-red: #ee0000;     /* 错误/下降 */
--accent-amber: #f5a623;   /* 警告/金牌 */
--accent-purple: #7928ca;  /* 图表辅助色 */
```

### 浅色主题
```css
--bg-base: #ffffff;
--bg-surface: #fafafa;
--bg-elevated: #f5f5f5;
--text-primary: #171717;
--text-secondary: #525252;
--accent-blue: #0070f3;    /* 蓝色保持不变 */
```

## 排版
- 标题: Inter 600 / Noto Sans SC 600
- 正文: Inter 400 / Noto Sans SC 400
- 数据: JetBrains Mono 400/600
- 字重只用 400/500/600 三档
- 行高: 1.5（正文）, 1.2（标题）

## 间距系统（8px 网格）
- xs: 4px | sm: 8px | md: 16px | lg: 24px | xl: 32px

## 组件规范

### 卡片
- border-radius: 12px
- border: 1px solid var(--border-default)
- 无 box-shadow（深色主题）/ 轻微 shadow（浅色主题）
- padding: 20-24px

### 导航栏
- position: sticky; top: 0; z-index: 40
- 背景: var(--bg-surface) + border-bottom
- 高度: 48px
- 品牌 logo 左对齐，主题切换右对齐

### 排名列表
- 三栏布局: 排名 | 内容 | 分数
- Top 3 加大 padding 和字号
- border-bottom 分隔（非卡片边框）
- 悬停: background 变化，无 transform

### 标签（Tag）
- 低饱和度背景 + 同色系文字
- border-radius: 4px
- padding: 1px 6px
- font-size: 11px

### 奖牌
- 金: #f5a623 背景
- 银: #94a3b8 背景
- 铜: #cd7f32 背景
- 圆形 24x24px，居中数字

## Chart.js 主题适配
```javascript
function css(v) {
    return getComputedStyle(document.documentElement).getPropertyValue(v).trim();
}
// 运行时读取 CSS 变量，主题切换后图表自动适配
```

## 响应式断点
- mobile: < 768px → grid-1
- tablet: 768-1024px → grid-2
- desktop: > 1024px → grid-4

## 可访问性
- 对比度: 文字/背景 ≥ 4.5:1
- 焦点指示器: 2px solid var(--accent-blue)
- 语义化 HTML: nav, main, footer, section
- aria-label 用于图标按钮

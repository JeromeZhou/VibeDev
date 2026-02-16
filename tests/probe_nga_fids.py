"""探测 NGA 硬件相关板块 fid"""
import sys, os, json, re, time
sys.stdout.reconfigure(encoding='utf-8')
import functools
print = functools.partial(print, flush=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
import httpx

# 加载 cookies
cookie_file = Path("cookies/nga.json")
cookie_list = json.load(open(cookie_file, "r", encoding="utf-8"))
cookies = {c["name"]: c["value"] for c in cookie_list if ".nga.cn" in c.get("domain", "")}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://bbs.nga.cn/",
    "Accept": "application/json, text/plain, */*",
}

# NGA 已知硬件相关板块候选
# 通过搜索 NGA 板块列表，常见硬件区 fid:
# 7: 硬件区(PC Hardware)  — 老版
# 8: 显卡  — 老版
# 256: PC硬件
# 334: 电脑硬件
# 340: DIY装机
# 353: 硬件外设
# 432: 电脑装机
# 485: 硬件
# 489: 显卡
# -7: 硬件区(负数fid也是NGA特色)
# -489: 显卡

candidates = [
    # 常见硬件区
    7, 8, -7, -8,
    # 200-260 范围
    254, 255, 256, 257, 258,
    # 300-360 范围
    330, 331, 332, 333, 334, 335, 340, 350, 353,
    # 400-500 范围
    407, 432, 433, 434, 435, 436, 485, 486, 489, 490,
    # 500+ 范围
    500, 501, 502, 503, 504, 505,
    # 600+ 范围
    600, 602, 604, 606, 608, 610,
    # NGA 负数 fid (子版块)
    -7, -187452, -353, -489,
]

# 去重
candidates = list(dict.fromkeys(candidates))

print(f"探测 {len(candidates)} 个 fid...\n")

results = []
for fid in candidates:
    time.sleep(1.0)
    try:
        url = f"https://bbs.nga.cn/thread.php?fid={fid}&page=1&__output=11"
        resp = httpx.get(url, headers=headers, cookies=cookies, timeout=15, follow_redirects=True)
        text = resp.text.strip()

        if text.startswith("window.script_muti_get_var_store"):
            text = re.sub(r'^window\.script_muti_get_var_store\s*=\s*', '', text)
            text = text.rstrip(';')

        data = json.loads(text)

        # 检查错误
        if data.get("error"):
            err_msg = str(data["error"])[:60]
            print(f"  fid={fid:>6d}  ERROR: {err_msg}")
            continue

        result = data.get("data", data)

        # 获取板块名
        forum_name = result.get("__F", {}).get("name", "???") if isinstance(result.get("__F"), dict) else "???"

        # 获取帖子数
        thread_list = result.get("__T", {})
        if isinstance(thread_list, dict):
            count = sum(1 for v in thread_list.values() if isinstance(v, dict) and v.get("tid"))
        elif isinstance(thread_list, list):
            count = sum(1 for v in thread_list if isinstance(v, dict) and v.get("tid"))
        else:
            count = 0

        # 采样标题
        sample_titles = []
        items = thread_list.items() if isinstance(thread_list, dict) else enumerate(thread_list)
        for k, v in items:
            if isinstance(v, dict) and v.get("subject"):
                title = re.sub(r'<[^>]+>', '', v["subject"]).strip()
                if title:
                    sample_titles.append(title[:50])
                if len(sample_titles) >= 3:
                    break

        # 判断是否硬件相关
        hw_keywords = ["显卡", "GPU", "RTX", "RX", "显存", "散热", "功耗", "驱动", "NVIDIA", "AMD", "Intel",
                       "硬件", "CPU", "内存", "主板", "电源", "装机", "DIY", "超频", "跑分", "温度",
                       "4090", "4080", "4070", "4060", "3090", "3080", "3070", "3060",
                       "9070", "7900", "7800", "7600", "B580"]
        is_hw = any(kw.lower() in " ".join(sample_titles).lower() for kw in hw_keywords)

        marker = " [HW!]" if is_hw else ""
        print(f"  fid={fid:>6d}  [{forum_name}] {count}条{marker}")
        for t in sample_titles:
            print(f"           -> {t}")

        results.append({"fid": fid, "name": forum_name, "count": count, "hw": is_hw, "samples": sample_titles})

    except json.JSONDecodeError:
        print(f"  fid={fid:>6d}  JSON解析失败")
    except Exception as e:
        print(f"  fid={fid:>6d}  请求失败: {e}")

print(f"\n=== 硬件相关板块 ===")
for r in results:
    if r["hw"]:
        print(f"  fid={r['fid']:>6d}  [{r['name']}] {r['count']}条")
        for t in r["samples"]:
            print(f"           -> {t}")

"""深入探测 fid=334 PC软硬件 及其附近板块"""
import sys, os, json, re, time
sys.stdout.reconfigure(encoding='utf-8')
import functools
print = functools.partial(print, flush=True)

from pathlib import Path
import httpx

cookie_file = Path("cookies/nga.json")
cookie_list = json.load(open(cookie_file, "r", encoding="utf-8"))
cookies = {c["name"]: c["value"] for c in cookie_list if ".nga.cn" in c.get("domain", "")}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://bbs.nga.cn/",
    "Accept": "application/json, text/plain, */*",
}

# 探测 334 附近 + 负数子版块
candidates = [
    # 334 附近
    320, 321, 322, 323, 324, 325, 326, 327, 328, 329,
    336, 337, 338, 339, 341, 342, 343, 344, 345,
    # 负数子版块
    -334, -436,
    # 更多可能
    173, 174, 175, 176, 177, 178, 179, 180,
    # 老版硬件区
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,
]

candidates = list(dict.fromkeys(candidates))
print(f"探测 {len(candidates)} 个 fid...\n")

hw_keywords = ["显卡", "GPU", "RTX", "RX", "显存", "散热", "功耗", "驱动", "NVIDIA", "AMD", "Intel",
               "硬件", "CPU", "内存", "主板", "电源", "装机", "DIY", "超频", "跑分", "温度",
               "4090", "4080", "4070", "4060", "3090", "3080", "3070", "3060",
               "9070", "7900", "7800", "7600", "B580", "笔记本", "SSD", "固态"]

for fid in candidates:
    time.sleep(0.8)
    try:
        url = f"https://bbs.nga.cn/thread.php?fid={fid}&page=1&__output=11"
        resp = httpx.get(url, headers=headers, cookies=cookies, timeout=15, follow_redirects=True)
        text = resp.text.strip()
        if text.startswith("window.script_muti_get_var_store"):
            text = re.sub(r'^window\.script_muti_get_var_store\s*=\s*', '', text)
            text = text.rstrip(';')
        data = json.loads(text)
        if data.get("error"):
            print(f"  fid={fid:>6d}  ERROR: {str(data['error'])[:50]}")
            continue
        result = data.get("data", data)
        forum_name = result.get("__F", {}).get("name", "???") if isinstance(result.get("__F"), dict) else "???"
        thread_list = result.get("__T", {})

        sample_titles = []
        items = thread_list.items() if isinstance(thread_list, dict) else enumerate(thread_list)
        for k, v in items:
            if isinstance(v, dict) and v.get("subject"):
                title = re.sub(r'<[^>]+>', '', v["subject"]).strip()
                if title:
                    sample_titles.append(title[:60])
                if len(sample_titles) >= 3:
                    break

        is_hw = any(kw.lower() in " ".join(sample_titles).lower() for kw in hw_keywords)
        marker = " [HW!]" if is_hw else ""
        print(f"  fid={fid:>6d}  [{forum_name}]{marker}")
        for t in sample_titles:
            print(f"           -> {t}")
    except Exception as e:
        print(f"  fid={fid:>6d}  失败: {str(e)[:50]}")

# 最后详细看 fid=334 的帖子
print("\n\n=== fid=334 PC软硬件 详细帖子 ===")
time.sleep(1)
url = f"https://bbs.nga.cn/thread.php?fid=334&page=1&__output=11"
resp = httpx.get(url, headers=headers, cookies=cookies, timeout=15, follow_redirects=True)
text = resp.text.strip()
if text.startswith("window.script_muti_get_var_store"):
    text = re.sub(r'^window\.script_muti_get_var_store\s*=\s*', '', text)
    text = text.rstrip(';')
data = json.loads(text)
result = data.get("data", data)
thread_list = result.get("__T", {})

items = thread_list.items() if isinstance(thread_list, dict) else enumerate(thread_list)
count = 0
for k, v in items:
    if not isinstance(v, dict) or not v.get("tid"):
        continue
    count += 1
    title = re.sub(r'<[^>]+>', '', v.get("subject", "")).strip()
    replies = v.get("replies", 0)
    postdate = v.get("postdate", "")
    print(f"  {count:2d}. [{replies:>4d}回复] {postdate} | {title[:70]}")
    if count >= 25:
        break

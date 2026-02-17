#!/usr/bin/env python3
"""同步隐藏需求到 latest.json"""
import json
import sys
import builtins
import functools
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
builtins.print = functools.partial(builtins.print, flush=True)
load_dotenv(Path(__file__).parent / ".env")

from src.utils.db import get_db

# 1. 从 DB 读取隐藏需求
conn = get_db()
rows = conn.execute(
    "SELECT pain_point, hidden_need FROM pphi_history WHERE hidden_need IS NOT NULL AND hidden_need != ''"
).fetchall()
conn.close()
need_map = {r["pain_point"]: r["hidden_need"] for r in rows}
print(f"DB 中有 {len(need_map)} 个隐藏需求")

# 2. 从 hidden_needs jsonl 读取推理链和 Munger 审查
chain_map = {}
hn_file = Path("data/processed/hidden_needs_2026-02-17.jsonl")
if hn_file.exists():
    with open(hn_file, "r", encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line.strip())
                if d.get("pain_point") and d.get("hidden_need"):
                    chain_map[d["pain_point"]] = d
            except Exception:
                pass
print(f"JSONL 中有 {len(chain_map)} 条推理链")

# 3. 更新 latest.json
latest_path = Path("outputs/pphi_rankings/latest.json")
with open(latest_path, "r", encoding="utf-8") as f:
    data = json.load(f)

updated = 0
for r in data["rankings"]:
    pp = r["pain_point"]
    # 更新 hidden_need
    if pp in need_map:
        r["hidden_need"] = need_map[pp]
        updated += 1

    # 补充推理链和 Munger 审查（从 chain_map 或 need_map 构造）
    if pp in chain_map:
        cd = chain_map[pp]
        r["inferred_need"] = {
            "hidden_need": cd.get("hidden_need", ""),
            "reasoning_chain": cd.get("reasoning_chain", []),
            "confidence": cd.get("confidence", 0.5),
            "munger_review": cd.get("munger_review"),
            "munger_rejected": cd.get("munger_rejected", False),
        }
    elif pp in need_map and not r.get("inferred_need"):
        # 没有推理链但有隐藏需求，构造基本结构
        r["inferred_need"] = {
            "hidden_need": need_map[pp],
            "reasoning_chain": [],
            "confidence": 0.7,
            "munger_review": None,
        }

# 同时更新历史 rankings 文件
with open(latest_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 也更新带日期的文件
import glob
for fp in glob.glob("outputs/pphi_rankings/rankings_2026-02-17*.json"):
    with open(fp, "r", encoding="utf-8") as f:
        hist = json.load(f)
    for r in hist.get("rankings", []):
        pp = r["pain_point"]
        if pp in need_map:
            r["hidden_need"] = need_map[pp]
        if pp in chain_map:
            cd = chain_map[pp]
            r["inferred_need"] = {
                "hidden_need": cd.get("hidden_need", ""),
                "reasoning_chain": cd.get("reasoning_chain", []),
                "confidence": cd.get("confidence", 0.5),
                "munger_review": cd.get("munger_review"),
            }
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

print(f"更新 {updated} 个痛点的隐藏需求到 latest.json")
print()
for r in data["rankings"][:5]:
    need = r.get("hidden_need", "")
    inferred = r.get("inferred_need")
    munger = inferred.get("munger_review", {}).get("quality_level", "?") if inferred else "无"
    conf = inferred.get("confidence", 0) if inferred else 0
    print(f"  #{r['rank']} {r['pain_point'][:35]}")
    print(f"     需求: {need[:50]}")
    print(f"     Munger: [{munger}] conf={conf:.2f}")
    print()

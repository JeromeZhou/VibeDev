#!/usr/bin/env python3
"""一次性回填脚本：对所有痛点重新推导 reasoning_chain + Munger 审查，更新 DB + latest.json"""

import sys, json
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, ".")
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(".env"))

from src.utils.config import load_config
from src.utils.llm_client import LLMClient
from src.utils.db import get_db, init_db
from src.analyzers import infer_hidden_needs, devils_advocate_review

def main():
    init_db()
    config = load_config("config/config.yaml")
    llm = LLMClient(config)

    # 1. 从 DB 最新一轮加载所有痛点
    with get_db() as conn:
        latest = conn.execute("SELECT MAX(run_date) as rd FROM pphi_history").fetchone()["rd"]
        rows = conn.execute(
            """SELECT id, pain_point, hidden_need, inferred_need_json, pphi_score, category, affected_users
               FROM pphi_history WHERE run_date = ? ORDER BY pphi_score DESC""",
            (latest,)
        ).fetchall()

    print(f"最新轮次: {latest}, 共 {len(rows)} 条痛点")
    print()

    # 2. 构造推导输入
    pains_for_inference = []
    row_ids = []  # 对应 DB row id
    for r in rows:
        inj = r["inferred_need_json"]
        needs_redo = True
        if inj:
            try:
                obj = json.loads(inj)
                if obj.get("reasoning_chain") and len(obj["reasoning_chain"]) > 0:
                    needs_redo = False  # 已有完整数据，跳过
            except (json.JSONDecodeError, TypeError):
                pass

        if needs_redo:
            pains_for_inference.append({
                "pain_point": r["pain_point"],
                "category": r["category"] or "",
                "emotion_intensity": 0.6,
                "evidence": "",
                "source_post_ids": [],
                "source_urls": [],
                "_inference_idx": len(pains_for_inference),
            })
            row_ids.append(r["id"])

    print(f"需要重新推导: {len(pains_for_inference)} 条")
    if not pains_for_inference:
        print("全部已有 reasoning_chain，无需操作")
        return

    # 3. 批量推导隐藏需求（含 reasoning_chain）
    print()
    print("=" * 50)
    print("  Step 1: 推导隐藏需求 + reasoning_chain")
    print("=" * 50)
    hidden_needs = infer_hidden_needs(pains_for_inference, config, llm)
    print(f"  推导完成: {len(hidden_needs)} 条")

    # 统计
    has_chain = sum(1 for hn in hidden_needs if hn.get("reasoning_chain") and len(hn["reasoning_chain"]) > 0)
    print(f"  有 reasoning_chain: {has_chain}/{len(hidden_needs)}")
    print()

    # 4. Munger 审查
    print("=" * 50)
    print("  Step 2: Devil's Advocate 审查 (Munger)")
    print("=" * 50)
    reviewed = devils_advocate_review(hidden_needs, llm)
    print()

    # 5. 写回 DB
    print("=" * 50)
    print("  Step 3: 更新 DB")
    print("=" * 50)

    # 建立 _inference_idx → reviewed 映射
    idx_map = {}
    for hn in reviewed:
        idx = hn.get("_inference_idx")
        if idx is not None:
            idx_map[idx] = hn

    updated = 0
    with get_db() as conn:
        for i, pain in enumerate(pains_for_inference):
            idx = pain["_inference_idx"]
            hn = idx_map.get(idx)
            if not hn or not hn.get("hidden_need"):
                continue

            db_id = row_ids[i]
            inferred_obj = {
                "hidden_need": hn["hidden_need"],
                "confidence": hn.get("confidence", 0.5),
                "reasoning_chain": hn.get("reasoning_chain", []),
                "munger_review": hn.get("munger_review"),
            }

            # 质量分层
            quality_tier = "bronze"
            if hn.get("hidden_need") and hn.get("reasoning_chain"):
                munger = hn.get("munger_review") or {}
                ql = munger.get("quality_level", "")
                if ql in ("strong", "moderate"):
                    quality_tier = "gold"
                else:
                    quality_tier = "silver"

            conn.execute(
                """UPDATE pphi_history
                   SET hidden_need = ?,
                       inferred_need_json = ?,
                       quality_tier = ?
                   WHERE id = ?""",
                (
                    hn["hidden_need"],
                    json.dumps(inferred_obj, ensure_ascii=False),
                    quality_tier,
                    db_id,
                )
            )
            updated += 1
            chain_len = len(hn.get("reasoning_chain", []))
            munger_ql = (hn.get("munger_review") or {}).get("quality_level", "none")
            print(f"  OK #{i+1} {pain['pain_point'][:25]}... chain={chain_len} munger={munger_ql} tier={quality_tier}")

    print(f"\n  DB 更新: {updated} 条")

    # 6. 重新生成 latest.json（从 DB 重新加载完整数据）
    print()
    print("=" * 50)
    print("  Step 4: 重新生成 latest.json")
    print("=" * 50)

    with get_db() as conn:
        all_rows = conn.execute(
            """SELECT rank, pain_point, pphi_score, mentions, gpu_tags, source_urls,
                      hidden_need, inferred_need_json, total_replies, total_likes,
                      category, affected_users, quality_tier
               FROM pphi_history WHERE run_date = ? ORDER BY rank ASC""",
            (latest,)
        ).fetchall()

    rankings = []
    for r in all_rows:
        inferred_need = None
        if r["inferred_need_json"]:
            try:
                inferred_need = json.loads(r["inferred_need_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        if not inferred_need and r["hidden_need"]:
            inferred_need = {"hidden_need": r["hidden_need"], "confidence": 0, "reasoning_chain": [], "munger_review": None}

        rankings.append({
            "pain_point": r["pain_point"],
            "pphi_score": r["pphi_score"],
            "mentions": r["mentions"],
            "sources": [],  # 从 source_urls 推断
            "source_urls": json.loads(r["source_urls"]) if r["source_urls"] else [],
            "gpu_tags": json.loads(r["gpu_tags"]) if r["gpu_tags"] else {},
            "hidden_need": r["hidden_need"] or "",
            "confidence": inferred_need.get("confidence", 0) if inferred_need else 0,
            "category": r["category"] or "",
            "affected_users": r["affected_users"] or "",
            "evidence": "",
            "trend": "stable",
            "inferred_need": inferred_need,
            "total_replies": r["total_replies"] or 0,
            "total_likes": r["total_likes"] or 0,
            "munger_quality": (inferred_need or {}).get("munger_review", {}).get("quality_level", "unknown") if inferred_need and inferred_need.get("munger_review") else "unknown",
            "needs_verification": False,
            "quality_tier": r["quality_tier"] or "bronze",
            "rank": r["rank"],
        })

    # 推断 sources
    for r in rankings:
        sources = set()
        for url in r.get("source_urls", []):
            if "reddit" in url: sources.add("reddit")
            elif "nga" in url: sources.add("nga")
            elif "bilibili" in url: sources.add("bilibili")
            elif "v2ex" in url: sources.add("v2ex")
            elif "mydrivers" in url: sources.add("mydrivers")
            elif "techpowerup" in url: sources.add("techpowerup")
            elif "videocardz" in url: sources.add("videocardz")
        r["sources"] = sorted(sources)

    output = {
        "timestamp": latest,
        "total_pain_points": len(rankings),
        "rankings": rankings,
    }

    latest_path = Path("outputs/pphi_rankings/latest.json")
    tmp_path = latest_path.with_suffix(".json.tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    tmp_path.replace(latest_path)
    print(f"  latest.json 已更新 ({len(rankings)} 条)")

    # 7. 验证
    print()
    print("=" * 50)
    print("  验证结果")
    print("=" * 50)
    with open(latest_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data["rankings"])
    has_chain = sum(1 for r in data["rankings"] if r.get("inferred_need", {}).get("reasoning_chain"))
    has_munger = sum(1 for r in data["rankings"] if r.get("inferred_need", {}).get("munger_review"))
    gold = sum(1 for r in data["rankings"] if r.get("quality_tier") == "gold")
    silver = sum(1 for r in data["rankings"] if r.get("quality_tier") == "silver")
    bronze = sum(1 for r in data["rankings"] if r.get("quality_tier") == "bronze")

    print(f"  总痛点: {total}")
    print(f"  有 reasoning_chain: {has_chain}/{total}")
    print(f"  有 munger_review: {has_munger}/{total}")
    print(f"  质量分层: 🥇gold={gold} 🥈silver={silver} 🥉bronze={bronze}")
    print()

    # 打印前 3 条验证
    for r in data["rankings"][:3]:
        need = r.get("inferred_need", {})
        chain = need.get("reasoning_chain", [])
        munger = need.get("munger_review")
        print(f"  #{r['rank']} {r['pain_point'][:30]}")
        print(f"     chain: {len(chain)} steps | munger: {munger.get('quality_level') if munger else 'none'} | tier: {r.get('quality_tier')}")
        if chain:
            print(f"     step1: {chain[0][:50]}...")
        print()

    print(f"成本: ${llm.total_cost:.4f} | Tokens: {llm.total_tokens}")
    print("完成！")


if __name__ == "__main__":
    main()

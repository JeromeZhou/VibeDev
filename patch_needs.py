#!/usr/bin/env python3
"""GPU-Insight 补跑隐藏需求 — 用 call_simple 替代 call_reasoning（晚上快）"""

import os
import sys
import json
import builtins
import functools
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
builtins.print = functools.partial(builtins.print, flush=True)
load_dotenv(Path(__file__).parent / ".env")

from src.utils.config import load_config
from src.utils.llm_client import LLMClient


def extract_json(text):
    import re
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL):
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            continue
    try:
        return json.loads(text.strip())
    except:
        return None


def main():
    print("=" * 50)
    print("  GPU-Insight 补跑隐藏需求（fast mode）")
    print("=" * 50)
    print()

    config = load_config("config/config.yaml")
    llm = LLMClient(config)

    # 从 DB 加载 Top 5 痛点
    from src.utils.db import get_db
    conn = get_db()
    rows = conn.execute(
        "SELECT pain_point, pphi_score, rank FROM pphi_history ORDER BY rank ASC LIMIT 5"
    ).fetchall()
    conn.close()

    if not rows:
        print("[!] pphi_history 为空")
        return

    system = """你是隐藏需求推导专家。从表面痛点推导用户未明确表达的深层需求。
输出JSON：{"hidden_need":"一句话","reasoning_chain":["步骤1","步骤2","步骤3"],"confidence":0.8}
只输出JSON。"""

    # Step 6: 推导隐藏需求（用 call_simple）
    print(f"[6] 隐藏需求推导（{len(rows)} 个痛点，fast mode）...")
    needs = []
    for r in rows:
        pp = r["pain_point"]
        print(f"  推导: {pp[:50]}...", end=" ")
        prompt = f"痛点：{pp}\n请推导隐藏需求。"
        try:
            resp = llm.call_simple(prompt, system)
            parsed = extract_json(resp)
            if parsed and parsed.get("hidden_need"):
                parsed["pain_point"] = pp
                needs.append(parsed)
                print(f"→ {parsed['hidden_need'][:40]}")
            else:
                print("→ 解析失败")
        except Exception as e:
            print(f"→ 错误: {e}")
    print(f"  推导 {len(needs)} 个隐藏需求")
    print()

    # Step 6.5: Munger 审查（用 call_simple）
    munger_system = """你是 Charlie Munger，评估AI推导的隐藏需求质量。
输出JSON：{"quality_level":"strong|moderate|weak","adjusted_confidence":0.8,"munger_comment":"评价"}
strong: 推理完整有证据 | moderate: 合理但证据不足 | weak: 过度推测
只输出JSON。"""

    if needs:
        print("[6.5] Munger 审查（fast mode）...")
        for hn in needs:
            pp = hn["pain_point"]
            print(f"  审查: {pp[:40]}...", end=" ")
            prompt = f"痛点：{pp}\n推导需求：{hn['hidden_need']}\n推理链：{json.dumps(hn.get('reasoning_chain',[]), ensure_ascii=False)}\n请评估。"
            try:
                resp = llm.call_simple(prompt, munger_system)
                parsed = extract_json(resp)
                if parsed:
                    quality = parsed.get("quality_level", "moderate")
                    adj_conf = parsed.get("adjusted_confidence", 0.5)
                    hn["munger_review"] = parsed
                    if quality == "weak":
                        hn["confidence"] = min(adj_conf, 0.49)
                        print(f"→ Weak ({adj_conf:.2f})")
                    elif quality == "moderate":
                        hn["confidence"] = max(0.5, min(adj_conf, 0.79))
                        print(f"→ Moderate ({hn['confidence']:.2f})")
                    else:
                        hn["confidence"] = max(0.8, adj_conf)
                        print(f"→ Strong ({hn['confidence']:.2f})")
                else:
                    print("→ 解析失败")
            except Exception as e:
                print(f"→ 错误: {e}")
        print()

    # 更新 DB
    if needs:
        conn = get_db()
        for hn in needs:
            pp = hn["pain_point"]
            need = hn.get("hidden_need", "")
            if pp and need:
                conn.execute(
                    "UPDATE pphi_history SET hidden_need = ? WHERE pain_point = ?",
                    (need, pp)
                )
        conn.commit()
        conn.close()
        print("[DB] 已更新隐藏需求")
        print()

    # 结果
    print("=" * 70)
    print("  隐藏需求推导结果")
    print("=" * 70)
    for hn in needs:
        quality = hn.get("munger_review", {}).get("quality_level", "?")
        print(f"\n  痛点: {hn['pain_point'][:50]}")
        print(f"  需求: {hn['hidden_need'][:60]}")
        print(f"  评级: [{quality}] conf={hn.get('confidence',0):.2f}")
        chain = hn.get("reasoning_chain", [])
        if chain:
            print(f"  推理: {' → '.join(str(s)[:30] for s in chain[:4])}")

    print(f"\n完成 | Token: {llm.total_tokens} | Cost: ${llm.total_cost:.4f}")


if __name__ == "__main__":
    main()

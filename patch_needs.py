#!/usr/bin/env python3
"""GPU-Insight 补跑隐藏需求 — call_simple + 同步 DB & latest.json（闭环版）"""

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
    print("  GPU-Insight 补跑隐藏需求（闭环版）")
    print("=" * 50)
    print()

    config = load_config("config/config.yaml")
    llm = LLMClient(config)

    # 从 DB 加载缺少隐藏需求的痛点（或全部 Top N）
    from src.utils.db import get_db
    conn = get_db()
    rows = conn.execute(
        "SELECT pain_point, pphi_score, rank FROM pphi_history ORDER BY rank ASC LIMIT 10"
    ).fetchall()
    conn.close()

    if not rows:
        print("[!] pphi_history 为空")
        return

    system = """你是隐藏需求推导专家。从表面痛点推导用户未明确表达的深层需求。
输出JSON：{"hidden_need":"一句话","reasoning_chain":["步骤1","步骤2","步骤3"],"confidence":0.8}
只输出JSON。"""

    # Step 1: 推导隐藏需求
    print(f"[1/3] 隐藏需求推导（{len(rows)} 个痛点）...")
    needs = []
    for r in rows:
        pp = r["pain_point"]
        print(f"  推导: {pp[:45]}...", end=" ")
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
    print(f"  共推导 {len(needs)} 个隐藏需求")
    print()

    # Step 2: Munger 审查
    munger_system = """你是 Charlie Munger，评估AI推导的隐藏需求质量。
输出JSON：{"quality_level":"strong|moderate|weak","adjusted_confidence":0.8,"munger_comment":"评价"}
strong: 推理完整有证据 | moderate: 合理但证据不足 | weak: 过度推测
只输出JSON。"""

    if needs:
        print("[2/3] Munger 审查...")
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
                    # 存原始 Munger 数据
                    hn["munger_review"] = parsed
                    # 根据评级调整置信度
                    if quality == "weak":
                        hn["confidence"] = min(adj_conf, 0.49)
                        hn["munger_rejected"] = True
                        print(f"→ Weak ({adj_conf:.2f})")
                    elif quality == "moderate":
                        hn["confidence"] = max(0.5, min(adj_conf, 0.79))
                        hn["munger_rejected"] = False
                        print(f"→ Moderate ({hn['confidence']:.2f})")
                    else:
                        hn["confidence"] = max(0.8, adj_conf)
                        hn["munger_rejected"] = False
                        print(f"→ Strong ({hn['confidence']:.2f})")
                else:
                    print("→ 解析失败")
            except Exception as e:
                print(f"→ 错误: {e}")
        print()

    # Step 3: 同步到 DB + latest.json（闭环！）
    print("[3/3] 同步数据...")

    # 构建 pain_point → 完整数据 的映射
    need_map = {}
    for hn in needs:
        pp = hn["pain_point"]
        quality = hn.get("munger_review", {}).get("quality_level", "unknown")
        # 构造 Web UI 期望的 munger_review 格式
        munger_for_ui = None
        if hn.get("munger_review"):
            mr = hn["munger_review"]
            munger_for_ui = {
                "approved": quality in ("strong", "moderate"),
                "quality_level": quality,
                "adjusted_confidence": mr.get("adjusted_confidence", hn.get("confidence", 0.5)),
                "comment": mr.get("munger_comment", ""),
                "rejection_reason": mr.get("munger_comment", "") if quality == "weak" else None,
            }

        need_map[pp] = {
            "hidden_need": hn.get("hidden_need", ""),
            "reasoning_chain": hn.get("reasoning_chain", []),
            "confidence": hn.get("confidence", 0.5),
            "munger_review": munger_for_ui,
            "munger_rejected": hn.get("munger_rejected", False),
        }

    # 3a: 更新 DB
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
        print(f"  [DB] 更新 {len(needs)} 条隐藏需求")

    # 3b: 更新 latest.json
    latest_path = Path("outputs/pphi_rankings/latest.json")
    if latest_path.exists():
        with open(latest_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        updated = 0
        for r in data.get("rankings", []):
            pp = r["pain_point"]
            if pp in need_map:
                nd = need_map[pp]
                r["hidden_need"] = nd["hidden_need"]
                r["confidence"] = nd["confidence"]
                r["inferred_need"] = nd
                r["munger_quality"] = nd.get("munger_review", {}).get("quality_level", "unknown") if nd.get("munger_review") else "unknown"
                updated += 1

        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  [JSON] 更新 {updated} 条到 latest.json")

        # 也更新带日期的文件
        import glob
        for fp in glob.glob("outputs/pphi_rankings/rankings_*.json"):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    hist = json.load(f)
                for r in hist.get("rankings", []):
                    pp = r["pain_point"]
                    if pp in need_map:
                        nd = need_map[pp]
                        r["hidden_need"] = nd["hidden_need"]
                        r["confidence"] = nd["confidence"]
                        r["inferred_need"] = nd
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(hist, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    else:
        print("  [!] latest.json 不存在")

    # === 验证闭环 ===
    print()
    print("=" * 50)
    print("  验证闭环")
    print("=" * 50)

    # 重新读取 latest.json 验证
    if latest_path.exists():
        with open(latest_path, "r", encoding="utf-8") as f:
            verify = json.load(f)

        ok = 0
        fail = 0
        for r in verify.get("rankings", [])[:10]:
            pp = r["pain_point"][:35]
            inferred = r.get("inferred_need")
            has_need = bool(inferred and inferred.get("hidden_need"))
            has_chain = bool(inferred and inferred.get("reasoning_chain"))
            has_munger = bool(inferred and inferred.get("munger_review"))
            conf = inferred.get("confidence", 0) if inferred else 0

            status = "✅" if (has_need and has_chain and has_munger) else "⚠️"
            if has_need and has_chain and has_munger:
                ok += 1
            else:
                fail += 1

            quality = inferred.get("munger_review", {}).get("quality_level", "-") if inferred and inferred.get("munger_review") else "-"
            print(f"  {status} #{r.get('rank','?'):>2} {pp}")
            print(f"       需求={'✓' if has_need else '✗'}  推理链={'✓' if has_chain else '✗'}  Munger={'✓' if has_munger else '✗'}  [{quality}] conf={conf:.2f}")

        print()
        print(f"  完整: {ok} | 不完整: {fail}")

    print(f"\n完成 | Token: {llm.total_tokens} | Cost: ${llm.total_cost:.4f}")


if __name__ == "__main__":
    main()

"""GPU-Insight 分析模块 — v2 支持产品标签 + URL 追溯 + PainInsight 合并"""

import json
import re
from datetime import datetime
from pathlib import Path
from src.utils.llm_client import LLMClient
from src.utils.gpu_tagger import tag_gpu_products


def _extract_json(text: str) -> list[dict]:
    """从 LLM 响应中提取 JSON 对象（处理 markdown 代码块、多行 JSON 等）"""
    results = []
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    # 修复 LLM 常见错误：["步骤1": "xxx"] → ["xxx"]
    text = re.sub(r'"[^"]*步骤\d+":\s*', '', text)
    for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL):
        try:
            parsed = json.loads(match.group())
            results.append(parsed)
        except json.JSONDecodeError:
            continue
    if not results:
        try:
            parsed = json.loads(text.strip())
            if isinstance(parsed, dict):
                results.append(parsed)
            elif isinstance(parsed, list):
                results.extend(parsed)
        except json.JSONDecodeError:
            pass
    return results


def _merge_similar_points(points: list[dict], llm: LLMClient) -> list[dict]:
    """用 LLM 识别相似痛点并合并，减少重复"""
    if len(points) <= 2:
        return points

    # 构建痛点列表让 LLM 分组
    listing = "\n".join(f"[{i}] {p['pain_point']} ({p.get('category', '')})" for i, p in enumerate(points))
    prompt = f"""以下是 {len(points)} 个显卡痛点，请找出含义高度相似或明显重复的痛点并分组。
注意：只合并真正重复的（如"散热问题"和"显卡过热"），不要把不同类别的痛点合并（如"散热"和"噪音"是不同痛点）。
每组输出一个 JSON：{{"group": [序号], "merged_name": "合并后的痛点名"}}
不相似的痛点单独一组（group只有一个元素）。只输出 JSON 数组。

{listing}"""

    try:
        response = llm.call_simple(prompt, "你是文本去重专家。找出语义相似的条目并分组。只输出JSON数组。")
        groups = []
        for parsed in _extract_json(response):
            if "group" in parsed and "merged_name" in parsed:
                groups.append(parsed)

        if not groups:
            # 尝试解析为数组
            text = re.sub(r'```json\s*', '', response)
            text = re.sub(r'```\s*', '', text)
            try:
                arr = json.loads(text.strip())
                if isinstance(arr, list):
                    groups = [g for g in arr if isinstance(g, dict) and "group" in g]
            except json.JSONDecodeError:
                pass

        if not groups:
            return points

        # 按分组合并
        used = set()
        merged = []
        for g in groups:
            indices = g.get("group", [])
            if not isinstance(indices, list) or not indices:
                continue
            valid = [i for i in indices if isinstance(i, int) and 0 <= i < len(points) and i not in used]
            if not valid:
                continue

            # 安全检查：不合并不同类别的痛点
            if len(valid) > 1:
                categories = set(points[i].get("category", "") for i in valid)
                if len(categories) > 1:
                    # 类别不同，不合并，各自独立
                    for i in valid:
                        used.add(i)
                        merged.append(points[i])
                    continue

            used.update(valid)

            # 以第一个为基础，合并其余
            base = dict(points[valid[0]])
            base["pain_point"] = g.get("merged_name", base["pain_point"])
            for idx in valid[1:]:
                other = points[idx]
                base["source_post_ids"] = base.get("source_post_ids", []) + other.get("source_post_ids", [])
                base["source_urls"] = base.get("source_urls", []) + [u for u in other.get("source_urls", []) if u not in base.get("source_urls", [])]
                base["total_replies"] = base.get("total_replies", 0) + other.get("total_replies", 0)
                base["total_likes"] = base.get("total_likes", 0) + other.get("total_likes", 0)
                # 合并 GPU 标签
                for key in ("brands", "models", "series", "manufacturers"):
                    existing = set(base.get("gpu_tags", {}).get(key, []))
                    existing.update(other.get("gpu_tags", {}).get(key, []))
                    base.setdefault("gpu_tags", {})[key] = sorted(existing)
                # 取更高情绪强度
                base["emotion_intensity"] = max(base.get("emotion_intensity", 0), other.get("emotion_intensity", 0))
                # 取更早时间戳
                ts1 = base.get("earliest_timestamp", "")
                ts2 = other.get("earliest_timestamp", "")
                if ts1 and ts2:
                    base["earliest_timestamp"] = min(ts1, ts2)
                elif ts2:
                    base["earliest_timestamp"] = ts2
            merged.append(base)

        # 加入未被分组的
        for i, p in enumerate(points):
            if i not in used:
                merged.append(p)

        print(f"  语义去重: {len(points)} → {len(merged)} 个痛点")
        return merged

    except Exception as e:
        print(f"  [!] 语义去重失败: {e}")
        return points


def analyze_pain_points(posts: list[dict], config: dict, llm: LLMClient) -> list[dict]:
    """从清洗后的讨论中提取痛点，关联原帖 URL 和 GPU 标签"""
    if not posts:
        return []

    system_prompt = """你是 GPU-Insight 痛点提取专家。
从用户讨论中提取显卡相关痛点，输出 JSON 格式：
{
  "pain_point": "一句话描述痛点",
  "category": "性能|价格|散热|驱动|生态|显存|功耗|其他",
  "emotion_intensity": 0.0-1.0,
  "affected_users": "广泛|中等|小众",
  "evidence": "原文关键句",
  "related_post_indices": [0, 2]
}
related_post_indices 是该痛点来源的帖子序号（从0开始）。
同类痛点请合并。只输出 JSON，不要其他内容。如果讨论不包含显卡痛点，输出 {"pain_point": null}。"""

    results = []
    batch_size = 10
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        batch_text = "\n---\n".join(
            f"[{j}] [{p.get('_source', '未知')}] {p.get('title', '')}\n{p.get('content', '')[:300]}"
            for j, p in enumerate(batch)
        )
        prompt = f"请从以下 {len(batch)} 条讨论中提取显卡痛点，每条讨论前有序号。\n\n{batch_text}"

        try:
            response = llm.call_simple(prompt, system_prompt)
            for parsed in _extract_json(response):
                if parsed.get("pain_point"):
                    # 关联原帖 URL 和 ID
                    indices = parsed.pop("related_post_indices", [])
                    if not indices:
                        indices = list(range(len(batch)))
                    source_post_ids = []
                    source_urls = []
                    gpu_tags_merged = {"brands": set(), "models": set(), "series": set(), "manufacturers": set()}
                    for idx in indices:
                        if 0 <= idx < len(batch):
                            p = batch[idx]
                            source_post_ids.append(p.get("id", ""))
                            source_urls.append(p.get("url", ""))
                            # 合并 GPU 标签
                            tags = p.get("_gpu_tags", {})
                            for key in gpu_tags_merged:
                                gpu_tags_merged[key].update(tags.get(key, []))

                    parsed["source_post_ids"] = source_post_ids
                    parsed["source_urls"] = [u for u in source_urls if u]
                    parsed["gpu_tags"] = {k: sorted(v) for k, v in gpu_tags_merged.items()}
                    # 传递互动数据和时间
                    total_replies = sum(batch[idx].get("replies", 0) for idx in indices if 0 <= idx < len(batch))
                    total_likes = sum(batch[idx].get("likes", 0) for idx in indices if 0 <= idx < len(batch))
                    parsed["total_replies"] = total_replies
                    parsed["total_likes"] = total_likes
                    # 最早帖子时间
                    timestamps = [batch[idx].get("timestamp", "") for idx in indices if 0 <= idx < len(batch)]
                    parsed["earliest_timestamp"] = min(timestamps) if timestamps else ""
                    results.append(parsed)
        except Exception as e:
            print(f"  [!] 痛点提取失败: {e}")

    # 语义去重：合并相似痛点
    if len(results) > 1:
        results = _merge_similar_points(results, llm)

    _save_results(results, config, "pain_points")
    return results


def infer_hidden_needs(pain_points: list[dict], config: dict, llm: LLMClient) -> list[dict]:
    """从痛点推导隐藏需求"""
    if not pain_points:
        return []

    system_prompt = """你是 GPU-Insight 隐藏需求推导专家。
从表面痛点推导用户未明确表达的深层需求。
输出 JSON 格式（注意 reasoning_chain 是字符串数组）：
{
  "pain_point": "原始痛点",
  "reasoning_chain": ["散热不好导致降频", "降频影响游戏体验", "用户真正需要静音高效散热"],
  "hidden_need": "一句话描述隐藏需求",
  "confidence": 0.8,
  "category": "功能需求"
}
category 只能是：功能需求、情感需求、社会需求。
只输出一个 JSON 对象，不要其他内容。"""

    results = []
    for pp in pain_points:
        prompt = f"痛点：{pp['pain_point']}\n类别：{pp.get('category', '未知')}\n情绪强度：{pp.get('emotion_intensity', 0.5)}\n\n请推导隐藏需求。"
        try:
            response = llm.call_reasoning(prompt, system_prompt)
            for parsed in _extract_json(response):
                if parsed.get("hidden_need"):
                    results.append(parsed)
                    break
        except Exception as e:
            print(f"  [!] 隐藏需求推导失败: {e}")

    # 过滤低置信度推理（防幻觉）
    filtered = []
    for r in results:
        conf = r.get("confidence", 0)
        if conf >= 0.4:  # 保留但标记
            if conf < 0.6:
                r["_unverified"] = True
            filtered.append(r)
        else:
            print(f"    过滤低置信度推理: {r.get('pain_point', '')[:30]} (conf={conf})")

    _save_results(filtered, config, "hidden_needs")
    return filtered


def merge_pain_insights(pain_points: list[dict], hidden_needs: list[dict]) -> list[dict]:
    """合并痛点和推理需求为 PainInsight 结构

    pain_points: analyze_pain_points 的输出
    hidden_needs: infer_hidden_needs 的输出（可能只有部分痛点有）
    """
    # 建立痛点→需求的映射
    need_map = {}
    for hn in hidden_needs:
        key = hn.get("pain_point", "")
        if key:
            need_map[key] = {
                "hidden_need": hn["hidden_need"],
                "reasoning_chain": hn.get("reasoning_chain", []),
                "confidence": hn.get("confidence", 0.0),
                "category": hn.get("category", "功能需求"),
            }

    insights = []
    for pp in pain_points:
        pain_text = pp.get("pain_point", "")
        insight = {
            "pain_point": pain_text,
            "category": pp.get("category", "其他"),
            "emotion_intensity": pp.get("emotion_intensity", 0.0),
            "affected_users": pp.get("affected_users", ""),
            "evidence": pp.get("evidence", ""),
            "gpu_tags": pp.get("gpu_tags", {}),
            "source_post_ids": pp.get("source_post_ids", []),
            "source_urls": pp.get("source_urls", []),
            "total_replies": pp.get("total_replies", 0),
            "total_likes": pp.get("total_likes", 0),
            "earliest_timestamp": pp.get("earliest_timestamp", ""),
            "inferred_need": need_map.get(pain_text),  # None if no need inferred
        }
        insights.append(insight)

    return insights


def council_review(insights: list[dict], config: dict, llm: LLMClient) -> list[dict]:
    """Expert Council 多视角评审"""
    if not insights:
        return []

    system_prompt = """你是 GPU-Insight Expert Council，同时扮演三个角色进行评审：
1. 硬件工程师：评估技术可行性
2. 产品经理：评估商业价值
3. 数据科学家：评估数据质量

对每个隐藏需求，输出 JSON：
{
  "hidden_need": "原始需求",
  "approved": true/false,
  "adjusted_confidence": 0.0-1.0,
  "hardware_assessment": "技术评估",
  "product_assessment": "商业评估",
  "data_assessment": "数据评估",
  "concerns": ["关注点"]
}"""

    reviewed = []
    for insight in insights:
        need = insight.get("inferred_need")
        if not need:
            reviewed.append(insight)
            continue
        prompt = f"隐藏需求：{need['hidden_need']}\n推理链：{json.dumps(need.get('reasoning_chain', []), ensure_ascii=False)}\n置信度：{need.get('confidence', 0.5)}\n\n请进行三视角评审。"
        try:
            response = llm.call_reasoning(prompt, system_prompt)
            for parsed in _extract_json(response):
                insight["council_review"] = parsed
                reviewed.append(insight)
                break
        except Exception as e:
            print(f"  [!] Council 评审失败: {e}")
            reviewed.append(insight)

    _save_results(reviewed, config, "reviewed")
    return reviewed


def _save_results(results: list[dict], config: dict, prefix: str):
    """保存分析结果"""
    output_dir = Path(config.get("paths", {}).get("processed_data", "data/processed"))
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = output_dir / f"{prefix}_{date_str}.jsonl"
    with open(output_file, "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")

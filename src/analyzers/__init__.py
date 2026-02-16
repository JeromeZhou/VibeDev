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
                    results.append(parsed)
        except Exception as e:
            print(f"  ⚠️ 痛点提取失败: {e}")

    _save_results(results, config, "pain_points")
    return results


def infer_hidden_needs(pain_points: list[dict], config: dict, llm: LLMClient) -> list[dict]:
    """从痛点推导隐藏需求"""
    if not pain_points:
        return []

    system_prompt = """你是 GPU-Insight 隐藏需求推导专家。
从表面痛点推导用户未明确表达的深层需求。
必须输出完整推理链（至少 3 步），输出 JSON 格式：
{
  "pain_point": "原始痛点",
  "reasoning_chain": ["步骤1", "步骤2", "步骤3"],
  "hidden_need": "一句话描述隐藏需求",
  "confidence": 0.0-1.0,
  "category": "功能需求|情感需求|社会需求"
}
只输出 JSON，不要其他内容。"""

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
            print(f"  ⚠️ 隐藏需求推导失败: {e}")

    _save_results(results, config, "hidden_needs")
    return results


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
            print(f"  ⚠️ Council 评审失败: {e}")
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

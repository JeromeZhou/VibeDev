"""GPU-Insight 分析模块"""

import json
import re
from datetime import datetime
from pathlib import Path
from src.utils.llm_client import LLMClient


def _extract_json(text: str) -> list[dict]:
    """从 LLM 响应中提取 JSON 对象（处理 markdown 代码块、多行 JSON 等）"""
    results = []
    # 去掉 markdown 代码块标记
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    # 尝试用正则匹配所有 JSON 对象
    for match in re.finditer(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL):
        try:
            parsed = json.loads(match.group())
            results.append(parsed)
        except json.JSONDecodeError:
            continue
    # 如果正则没匹配到，尝试整体解析
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
    """从清洗后的讨论中提取痛点"""
    if not posts:
        return []

    system_prompt = """你是 GPU-Insight 痛点提取专家。
从用户讨论中提取显卡相关痛点，输出 JSON 格式：
{
  "pain_point": "一句话描述痛点",
  "category": "性能|价格|散热|驱动|生态|显存|功耗|其他",
  "emotion_intensity": 0.0-1.0,
  "summary": "一句话摘要"
}
只输出 JSON，不要其他内容。如果讨论不包含显卡痛点，输出 {"pain_point": null}。"""

    results = []
    # 批处理：每 10 条一批
    batch_size = 10
    for i in range(0, len(posts), batch_size):
        batch = posts[i:i + batch_size]
        batch_text = "\n---\n".join(
            f"[{p.get('_source', '未知')}] {p.get('title', '')}\n{p.get('content', '')}"
            for p in batch
        )
        prompt = f"请从以下 {len(batch)} 条讨论中提取显卡痛点，每条讨论用 --- 分隔。对每条讨论输出一行 JSON。\n\n{batch_text}"

        try:
            response = llm.call_simple(prompt, system_prompt)
            for parsed in _extract_json(response):
                if parsed.get("pain_point"):
                    results.append(parsed)
        except Exception as e:
            print(f"  ⚠️ 痛点提取失败: {e}")

    # 保存结果
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
        prompt = f"隐藏需求：{insight['hidden_need']}\n推理链：{json.dumps(insight.get('reasoning_chain', []), ensure_ascii=False)}\n置信度：{insight.get('confidence', 0.5)}\n\n请进行三视角评审。"
        try:
            response = llm.call_reasoning(prompt, system_prompt)
            for parsed in _extract_json(response):
                insight.update(parsed)
                reviewed.append(insight)
                break
        except Exception as e:
            print(f"  ⚠️ Council 评审失败: {e}")

    _save_results(reviewed, config, "reviewed")
    return [r for r in reviewed if r.get("approved", False)]


def _save_results(results: list[dict], config: dict, prefix: str):
    """保存分析结果"""
    output_dir = Path(config.get("paths", {}).get("processed_data", "data/processed"))
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    output_file = output_dir / f"{prefix}_{date_str}.jsonl"
    with open(output_file, "a", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

"""GPU-Insight 完整三层漏斗 + Top 20 痛点分析 — 需要网络 + LLM API，仅手动运行"""

import sys
import os
import json
import re

sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_NETWORK_TESTS") != "1",
    reason="需要网络+LLM API，设置 RUN_NETWORK_TESTS=1 启用"
)


def test_full_funnel():
    from openai import OpenAI
    from src.utils.config import load_config
    from src.scrapers.reddit_scraper import RedditScraper
    from src.cleaners import clean_data
    from src.analyzers.funnel import l1_local_filter, l2_batch_classify
    from src.utils.llm_client import LLMClient

    config = load_config('config/config.yaml')
    llm = LLMClient(config)
    client = OpenAI(api_key=os.getenv('SILICONFLOW_API_KEY'), base_url='https://api.siliconflow.cn/v1')

    # 1. 抓取
    print('[1] Reddit 三端点抓取...')
    reddit = RedditScraper(config)
    raw = reddit.fetch_posts()
    print(f'  抓取 {len(raw)} 条')

    # 2. 清洗
    cleaned = clean_data(raw, config)
    print(f'  清洗后 {len(cleaned)} 条')

    # 3. L1 本地漏斗
    print()
    print('[2] L1 本地信号排序...')
    filtered = l1_local_filter(cleaned)
    pain_count = len([p for p in filtered if p.get('_pain_signals', 0) > 0])
    print(f'  有痛点信号: {pain_count} 条 | 无信号: {len(filtered) - pain_count} 条')

    # 4. L2 批量分类
    print()
    print('[3] L2 GLM-5 批量标题分类...')
    filtered = l2_batch_classify(filtered, llm, batch_size=50)
    class_2 = [p for p in filtered if p.get('_l2_class') == 2]
    class_1 = [p for p in filtered if p.get('_l2_class') == 1]
    class_0 = [p for p in filtered if p.get('_l2_class') == 0]
    print(f'  明确痛点(2): {len(class_2)} | 可能相关(1): {len(class_1)} | 无关(0): {len(class_0)}')

    # 5. 深度分析
    deep_posts = class_2 + class_1[:10]
    print()
    print(f'[4] GLM-5 深度痛点提取（{len(deep_posts)} 条）...')

    all_pains = []
    for i in range(0, len(deep_posts), 10):
        batch = deep_posts[i:i + 10]
        batch_text = "\n---\n".join(
            f'[{p["likes"]}赞 {p["replies"]}回复] {p["title"]}\n{p.get("content", "")[:300]}'
            for p in batch
        )
        r = client.chat.completions.create(
            model='Pro/zai-org/GLM-5',
            messages=[
                {'role': 'system', 'content': '你是显卡用户痛点分析专家。从论坛讨论中提取显卡相关痛点。要求：\n1. 同类痛点合并\n2. 标注情绪强度(0-1)和影响范围\n3. 非痛点跳过\n输出JSON数组: [{"pain_point":"中文描述","category":"分类","emotion_intensity":0.0-1.0,"affected_users":"广泛/中等/小众","evidence":"原文关键句"}]\n只输出JSON。'},
                {'role': 'user', 'content': batch_text}
            ],
            max_tokens=2000, temperature=0.2,
        )
        for match in re.finditer(r'\{[^{}]+\}', r.choices[0].message.content):
            try:
                pp = json.loads(match.group())
                if pp.get('pain_point'):
                    all_pains.append(pp)
            except:
                pass

    # 6. 合并去重排序
    seen = {}
    for pp in all_pains:
        key = pp['pain_point']
        if key not in seen:
            seen[key] = pp
            seen[key]['count'] = 1
        else:
            seen[key]['count'] += 1
            seen[key]['emotion_intensity'] = max(
                seen[key].get('emotion_intensity', 0),
                pp.get('emotion_intensity', 0)
            )

    ranked = sorted(
        seen.values(),
        key=lambda x: x.get('emotion_intensity', 0) * (1 + x.get('count', 1) * 0.3),
        reverse=True
    )

    print(f'  提取 {len(ranked)} 个独立痛点')
    print()
    print('=' * 70)
    print('  GPU-Insight Top 20 痛点排名（Reddit 真实数据 + GLM-5 分析）')
    print('=' * 70)
    print()
    for i, pp in enumerate(ranked[:20], 1):
        intensity = pp.get('emotion_intensity', 0)
        affected = pp.get('affected_users', '?')
        category = pp.get('category', '?')
        evidence = pp.get('evidence', '')[:50]
        bar = '#' * int(intensity * 10) + '.' * (10 - int(intensity * 10))
        print(f'  #{i:2d} [{bar}] {intensity:.1f} | {pp["pain_point"]}')
        print(f'       {category} | 影响: {affected} | {evidence}')
        print()

    print(f'Token 消耗: {llm.total_tokens} | 成本: ${llm.total_cost:.4f}')
    assert len(ranked) > 0, "应该提取到痛点"


if __name__ == "__main__":
    os.environ["RUN_NETWORK_TESTS"] = "1"
    test_full_funnel()

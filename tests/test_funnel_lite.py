"""GPU-Insight 精简版漏斗测试 — 减少请求量"""

import sys, os, json, re

sys.stdout.reconfigure(encoding='utf-8')
# 强制 flush
import functools
print = functools.partial(print, flush=True)

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from openai import OpenAI
from src.utils.config import load_config
from src.cleaners import clean_data
from src.analyzers.funnel import l1_local_filter
from src.utils.llm_client import LLMClient

config = load_config('config/config.yaml')
llm = LLMClient(config)
client = OpenAI(api_key=os.getenv('SILICONFLOW_API_KEY'), base_url='https://api.siliconflow.cn/v1')

# 1. 只用 /hot 端点抓取（快速，6 次请求）
print('[1] Reddit /hot 抓取...')
import httpx, time, random, hashlib
from datetime import datetime

headers = {"User-Agent": "GPU-Insight/1.0 (research bot)"}
posts = []
seen = set()

for sub in ["nvidia", "amd", "hardware"]:
    print(f'  r/{sub}...', end=' ')
    time.sleep(1.5)
    try:
        # /hot
        r = httpx.get(f"https://www.reddit.com/r/{sub}/hot.json?limit=30", headers=headers, timeout=30, follow_redirects=True)
        for child in r.json().get("data", {}).get("children", []):
            pd = child["data"]
            pid = pd["id"]
            if pid in seen: continue
            seen.add(pid)
            posts.append({
                "id": pid, "title": pd.get("title",""), "content": pd.get("selftext","")[:500],
                "_source": "reddit", "_subreddit": sub,
                "replies": pd.get("num_comments",0), "likes": pd.get("score",0),
            })
        # /new
        time.sleep(1.5)
        r2 = httpx.get(f"https://www.reddit.com/r/{sub}/new.json?limit=20", headers=headers, timeout=30, follow_redirects=True)
        for child in r2.json().get("data", {}).get("children", []):
            pd = child["data"]
            pid = pd["id"]
            if pid in seen: continue
            seen.add(pid)
            posts.append({
                "id": pid, "title": pd.get("title",""), "content": pd.get("selftext","")[:500],
                "_source": "reddit", "_subreddit": sub,
                "replies": pd.get("num_comments",0), "likes": pd.get("score",0),
            })
        print(f'{len([p for p in posts if p["_subreddit"]==sub])} 条')
    except Exception as e:
        print(f'失败: {e}')

print(f'  总计: {len(posts)} 条')

# 2. L1 本地排序
print()
print('[2] L1 本地信号排序...')
filtered = l1_local_filter(posts)
pain_posts = [p for p in filtered if p.get('_pain_signals', 0) > 0]
print(f'  有痛点信号: {len(pain_posts)} | 无信号: {len(filtered) - len(pain_posts)}')

# 3. L2 批量分类（一次 API 调用）
print()
print('[3] L2 GLM-5 批量分类...')
titles = "\n".join(f"{i+1}. {p['title'][:80]}" for i, p in enumerate(filtered[:60]))
r = client.chat.completions.create(
    model='Pro/zai-org/GLM-5',
    messages=[
        {'role': 'system', 'content': '对每条帖子标题判断是否包含显卡用户痛点。每行输出一个数字：\n0=明确无关 1=可能相关 2=明确是痛点\n只输出数字，每行一个。'},
        {'role': 'user', 'content': f'分类以下{min(len(filtered),60)}条标题:\n{titles}'}
    ],
    max_tokens=500, temperature=0.1,
)
numbers = re.findall(r'[012]', r.choices[0].message.content)
for i, p in enumerate(filtered[:60]):
    p['_l2_class'] = int(numbers[i]) if i < len(numbers) else 1

class_2 = [p for p in filtered if p.get('_l2_class') == 2]
class_1 = [p for p in filtered if p.get('_l2_class') == 1]
class_0 = [p for p in filtered if p.get('_l2_class') == 0]
print(f'  痛点(2): {len(class_2)} | 可能(1): {len(class_1)} | 无关(0): {len(class_0)}')

# 4. 深度分析（只对 class 2 + class 1 前 5）
deep = class_2 + class_1[:5]
print()
print(f'[4] GLM-5 深度分析（{len(deep)} 条）...')

batch_text = "\n---\n".join(
    f'[{p["likes"]}赞 {p["replies"]}回复] {p["title"]}\n{p.get("content","")[:200]}'
    for p in deep[:20]
)
r2 = client.chat.completions.create(
    model='Pro/zai-org/GLM-5',
    messages=[
        {'role': 'system', 'content': '你是显卡用户痛点分析专家。提取痛点，同类合并。输出JSON数组:\n[{"pain_point":"中文描述","category":"分类","emotion_intensity":0.0-1.0,"affected_users":"广泛/中等/小众","evidence":"关键句"}]\n只输出JSON。'},
        {'role': 'user', 'content': batch_text}
    ],
    max_tokens=3000, temperature=0.2,
)

all_pains = []
for match in re.finditer(r'\{[^{}]+\}', r2.choices[0].message.content):
    try:
        pp = json.loads(match.group())
        if pp.get('pain_point'):
            all_pains.append(pp)
    except:
        pass

# 排序
all_pains.sort(key=lambda x: x.get('emotion_intensity', 0), reverse=True)

print(f'  提取 {len(all_pains)} 个痛点')
print()
print('=' * 70)
print('  GPU-Insight Top 20 痛点（Reddit 真实数据 + 三层漏斗 + GLM-5）')
print('=' * 70)
print()
for i, pp in enumerate(all_pains[:20], 1):
    intensity = pp.get('emotion_intensity', 0)
    bar = '#' * int(intensity * 10) + '.' * (10 - int(intensity * 10))
    print(f'  #{i:2d} [{bar}] {intensity:.1f} | {pp["pain_point"]}')
    print(f'       {pp.get("category","?")} | {pp.get("affected_users","?")} | {pp.get("evidence","")[:45]}')
    print()

print(f'--- Token: {llm.total_tokens} | 成本: ${llm.total_cost:.4f} ---')

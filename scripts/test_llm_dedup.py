#!/usr/bin/env python3
"""测试 LLM 去重效果"""
import sys, json, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, '.')

from dotenv import load_dotenv
load_dotenv(Path('.env'))

from src.utils.config import load_config
from src.utils.llm_client import LLMClient

config = load_config('config/config.yaml')
llm = LLMClient(config)

with open('outputs/pphi_rankings/latest.json', encoding='utf-8') as f:
    data = json.load(f)

names = [r['pain_point'] for r in data['rankings']]
name_list = '\n'.join(f'{i+1}. {n}' for i, n in enumerate(names))

system_prompt = """你是消费电子行业分析师，专注 GPU/显卡领域。
你的任务是审查一份显卡用户痛点列表，找出语义重复的痛点并建议合并。

合并规则（保守优先）：
- 只合并描述同一个具体问题的痛点
- 不要合并同一大类但不同具体问题的痛点
- 不要合并不同硬件部件的问题
- 如果不确定，不要合并

输出 JSON：{"merge_groups": [[1, 5], [3, 8, 12]]}
只输出 JSON。"""

prompt = f'以下是 {len(names)} 个显卡用户痛点，请找出语义重复的组：\n\n{name_list}'

print(f'发送 {len(names)} 个痛点给 LLM...')
response = llm.call_reasoning(prompt, system_prompt)
print(f'\n=== LLM 响应 ===')
print(response[:500])

text = re.sub(r'```json\s*', '', response)
text = re.sub(r'```\s*', '', text)
try:
    parsed = json.loads(text)
    groups = parsed.get('merge_groups', [])
    print(f'\n=== 合并建议: {len(groups)} 组 ===')
    for g in groups:
        items = [names[i-1] for i in g if 1 <= i <= len(names)]
        print(f'  {items}')
except Exception as e:
    print(f'解析失败: {e}')

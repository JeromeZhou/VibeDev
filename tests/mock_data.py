"""GPU-Insight 模拟数据生成器 — 用于验证 pipeline"""

import json
import random
from datetime import datetime, timedelta

# 模拟的显卡痛点讨论数据
MOCK_DISCUSSIONS = [
    {
        "title": "4060Ti 8G 跑 ComfyUI 又爆显存了",
        "content": "刚入的 4060Ti 8G，跑 SDXL 1.0 基本模型还行，一上 ControlNet 就爆显存。8G 在 2026 年真的不够用了，后悔没加钱上 16G 版本。有没有什么优化方案？",
        "source": "chiphell",
        "replies": 89,
        "likes": 156,
    },
    {
        "title": "RTX 5070 功耗墙太离谱了",
        "content": "5070 默认功耗墙 250W，解锁后能到 300W，但是散热根本压不住。第三方卡散热方案都是为 250W 设计的，超频空间几乎没有。NV 这功耗控制越来越拉了。",
        "source": "chiphell",
        "replies": 67,
        "likes": 203,
    },
    {
        "title": "NVIDIA driver keeps crashing after update",
        "content": "Updated to the latest 570.xx driver and now getting constant TDR crashes in games. Rolled back to 565.xx and it's fine. This has been happening for months, NVIDIA QA is non-existent at this point.",
        "source": "reddit",
        "replies": 234,
        "likes": 567,
    },
    {
        "title": "显卡价格什么时候能回到正常水平",
        "content": "5070 首发价 4499，现在加价到 5500+还买不到。4060Ti 当初 3299 现在还要 2899。感觉显卡价格永远回不去了，普通玩家真的玩不起。",
        "source": "nga",
        "replies": 445,
        "likes": 892,
    },
    {
        "title": "AMD FSR 4 画质翻车",
        "content": "FSR 4 号称用了 AI 超分，实际体验拉胯。鬼影严重，运动场景模糊，和 DLSS 4 差距越来越大。A 卡用户真的是二等公民。",
        "source": "nga",
        "replies": 178,
        "likes": 334,
    },
    {
        "title": "矿卡翻新当新卡卖，怎么辨别？",
        "content": "闲鱼上 3080 只要 1200，但怕是矿卡翻新。有没有什么方法能鉴别？听说看电容和 PCB 氧化程度可以判断，但普通人根本看不出来。",
        "source": "tieba",
        "replies": 312,
        "likes": 445,
    },
    {
        "title": "4K 120Hz 需要什么显卡？预算有限",
        "content": "想组一台 4K 120Hz 的游戏主机，但预算只有 3000 块买显卡。5060 还没出，4070 Super 要 4500+，感觉中端卡完全覆盖不了 4K 高刷需求。",
        "source": "chiphell",
        "replies": 156,
        "likes": 278,
    },
    {
        "title": "Linux 下 NVIDIA 驱动还是一坨",
        "content": "Wayland 下 NVIDIA 驱动各种问题，屏幕撕裂、休眠黑屏、多显示器 bug。AMD 开源驱动体验好太多了。做 Linux 开发的真不建议买 N 卡。",
        "source": "reddit",
        "replies": 189,
        "likes": 423,
    },
    {
        "title": "显卡风扇噪音大到离谱",
        "content": "公版 5080 满载风扇转速 2800rpm，噪音快 50 分贝了。放在桌面上跟飞机起飞一样。为什么不能做成 2.5 槽甚至 3 槽的散热方案？",
        "source": "chiphell",
        "replies": 98,
        "likes": 167,
    },
    {
        "title": "本地跑 LLM 显存完全不够",
        "content": "想本地跑 Llama 3 70B，至少需要 48G 显存。消费级显卡最大才 24G（4090），两张 4090 要 3 万块。AI 时代普通人根本玩不起本地大模型。",
        "source": "reddit",
        "replies": 567,
        "likes": 1203,
    },
    {
        "title": "HDMI 2.1 带宽不够用了",
        "content": "4K 144Hz HDR 需要 HDMI 2.1 的全部带宽，但很多显卡的 HDMI 2.1 实际只能跑 4K 120Hz。DP 2.1 又没几个显示器支持。接口标准太混乱了。",
        "source": "guru3d",
        "replies": 78,
        "likes": 145,
    },
    {
        "title": "显卡越来越大，机箱放不下",
        "content": "5080 三风扇版本长度 340mm，我的机箱最大支持 320mm。现在的显卡动不动就 3 槽厚、340mm 长，中塔机箱根本放不下。要么换机箱要么买 ITX 短卡，选择太少了。",
        "source": "chiphell",
        "replies": 134,
        "likes": 256,
    },
]


def generate_mock_data() -> list[dict]:
    """生成模拟数据"""
    posts = []
    for i, disc in enumerate(MOCK_DISCUSSIONS):
        post = {
            "id": f"{disc['source']}_{datetime.now().strftime('%Y%m%d')}_{i:03d}",
            "title": disc["title"],
            "content": disc["content"],
            "source": disc["source"],
            "_source": disc["source"],
            "replies": disc["replies"],
            "likes": disc["likes"],
            "url": f"https://example.com/{disc['source']}/post/{i}",
            "author_hash": f"mock_author_{i:04d}",
            "language": "en" if disc["source"] == "reddit" else "zh-CN",
            "timestamp": (datetime.now() - timedelta(hours=random.randint(1, 72))).isoformat(),
        }
        posts.append(post)
    return posts


if __name__ == "__main__":
    data = generate_mock_data()
    print(f"生成 {len(data)} 条模拟数据")
    for d in data:
        print(f"  [{d['source']}] {d['title'][:40]}...")

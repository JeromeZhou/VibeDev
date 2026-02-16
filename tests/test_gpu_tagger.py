"""GPU 产品标签识别器测试"""

import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.gpu_tagger import tag_gpu_products, tag_post


def test_basic():
    """基础型号识别"""
    cases = [
        ("My RTX 5070 Ti keeps crashing", {"brands": ["NVIDIA"], "models": ["RTX 5070 Ti"], "series": ["RTX 50"]}),
        ("RX 7900 XTX vs RTX 4090", {"brands": ["AMD", "NVIDIA"], "models": ["RTX 4090", "RX 7900 XTX"]}),
        ("Just got an Arc B580", {"brands": ["INTEL"], "models": ["Arc B580"], "series": ["Arc B"]}),
        ("ASUS ROG Strix RTX 4080 overheating", {"brands": ["NVIDIA"], "models": ["RTX 4080"], "manufacturers": ["ASUS"]}),
        ("MSI Gaming X RTX 5070 coil whine", {"brands": ["NVIDIA"], "models": ["RTX 5070"], "manufacturers": ["MSI"]}),
        ("Sapphire Nitro RX 7800 XT fan noise", {"brands": ["AMD"], "models": ["RX 7800 XT"], "manufacturers": ["Sapphire"]}),
    ]

    passed = 0
    for text, expected in cases:
        result = tag_gpu_products(text)
        ok = True
        for key, vals in expected.items():
            for v in vals:
                if v not in result.get(key, []):
                    print(f"  FAIL: '{text}' -> missing {key}={v}, got {result.get(key, [])}")
                    ok = False
        if ok:
            passed += 1
            print(f"  PASS: '{text[:50]}...' -> {result['models']}, {result['manufacturers']}")

    print(f"\n  基础测试: {passed}/{len(cases)} 通过")
    return passed == len(cases)


def test_flexible_format():
    """灵活格式识别（大小写、空格变体）"""
    cases = [
        ("rtx5070ti is great", ["RTX 5070 Ti"]),
        ("RTX 5070TI", ["RTX 5070 Ti"]),
        ("rx7900xtx", ["RX 7900 XTX"]),
        ("RX 7900XTX", ["RX 7900 XTX"]),
        ("gtx1660super", ["GTX 1660 Super"]),
    ]

    passed = 0
    for text, expected_models in cases:
        result = tag_gpu_products(text)
        if all(m in result["models"] for m in expected_models):
            passed += 1
            print(f"  PASS: '{text}' -> {result['models']}")
        else:
            print(f"  FAIL: '{text}' -> expected {expected_models}, got {result['models']}")

    print(f"\n  灵活格式测试: {passed}/{len(cases)} 通过")
    return passed == len(cases)


def test_chinese():
    """中文别名识别"""
    cases = [
        ("老黄的新卡太贵了", ["NVIDIA"]),
        ("苏妈这次给力", ["AMD"]),
        ("七彩虹iGame显卡翻车", ["Colorful"]),
        ("影驰HOF限量版", ["Galax"]),
        ("华硕ROG太贵", ["ASUS"]),
        ("技嘉AORUS散热好", ["Gigabyte"]),
    ]

    passed = 0
    for text, expected in cases:
        result = tag_gpu_products(text)
        key = "brands" if expected[0] in ["NVIDIA", "AMD", "INTEL"] else "manufacturers"
        if all(v in result.get(key, []) for v in expected):
            passed += 1
            print(f"  PASS: '{text}' -> {key}={result[key]}")
        else:
            print(f"  FAIL: '{text}' -> expected {key}={expected}, got {result.get(key, [])}")

    print(f"\n  中文别名测试: {passed}/{len(cases)} 通过")
    return passed == len(cases)


def test_tag_post():
    """帖子打标签"""
    post = {
        "id": "test_1",
        "title": "RTX 5070 ASUS TUF overheating issue",
        "content": "My card reaches 95C under load",
        "url": "https://reddit.com/r/nvidia/test",
    }
    tag_post(post)
    tags = post.get("_gpu_tags", {})
    assert "NVIDIA" in tags["brands"], f"Expected NVIDIA in brands, got {tags['brands']}"
    assert "RTX 5070" in tags["models"], f"Expected RTX 5070 in models, got {tags['models']}"
    assert "ASUS" in tags["manufacturers"], f"Expected ASUS in manufacturers, got {tags['manufacturers']}"
    print(f"  PASS: tag_post -> {tags}")
    return True


def test_no_match():
    """无 GPU 内容不应误匹配"""
    result = tag_gpu_products("I love pizza and cats")
    assert result["brands"] == [], f"Expected empty brands, got {result['brands']}"
    assert result["models"] == [], f"Expected empty models, got {result['models']}"
    print(f"  PASS: no GPU content -> empty tags")
    return True


if __name__ == "__main__":
    print("=" * 60)
    print("  GPU Tagger 测试")
    print("=" * 60)
    print()

    results = []
    print("[1] 基础型号识别")
    results.append(test_basic())
    print()
    print("[2] 灵活格式识别")
    results.append(test_flexible_format())
    print()
    print("[3] 中文别名识别")
    results.append(test_chinese())
    print()
    print("[4] 帖子打标签")
    results.append(test_tag_post())
    print()
    print("[5] 无 GPU 内容")
    results.append(test_no_match())
    print()

    total = len(results)
    passed = sum(results)
    print("=" * 60)
    print(f"  总计: {passed}/{total} 组测试通过")
    print("=" * 60)

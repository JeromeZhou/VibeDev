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


class TestBrandPrecision:
    """品牌精确化测试 — 标题优先策略（30 条标注样本）"""

    def _tag(self, title, content=""):
        post = {"title": title, "content": content}
        tag_post(post)
        return post["_gpu_tags"]

    # ── 标题明确型号，正文提到其他品牌对比 ──

    def test_nvidia_title_amd_content(self):
        """标题 RTX 5090，正文对比 AMD → brands 只有 NVIDIA"""
        tags = self._tag("RTX 5090 散热严重不足", "和 RX 9070 XT 比起来差太多了")
        assert tags["brands"] == ["NVIDIA"]
        assert "RTX 5090" in tags["models"]
        assert "RX 9070 XT" not in tags["models"]

    def test_amd_title_nvidia_content(self):
        """标题 RX 9070 XT，正文提到 NVIDIA → brands 只有 AMD"""
        tags = self._tag("RX 9070 XT 驱动崩溃", "之前用 RTX 4070 从没这问题")
        assert tags["brands"] == ["AMD"]
        assert "RX 9070 XT" in tags["models"]
        assert "RTX 4070" not in tags["models"]

    def test_intel_title_nvidia_content(self):
        """标题 Arc B580，正文提到 NVIDIA → brands 只有 INTEL"""
        tags = self._tag("Arc B580 性价比真高", "比 RTX 4060 便宜还快")
        assert tags["brands"] == ["INTEL"]
        assert "Arc B580" in tags["models"]

    def test_nvidia_title_same_brand_content(self):
        """标题 RTX 5090，正文也是 NVIDIA 型号 → 合并同品牌型号"""
        tags = self._tag("RTX 5090 值不值得升级", "我现在用 RTX 3080，纠结要不要换")
        assert tags["brands"] == ["NVIDIA"]
        assert "RTX 5090" in tags["models"]
        assert "RTX 3080" in tags["models"]

    def test_multi_brand_in_title(self):
        """标题同时有两个品牌型号 → 都保留"""
        tags = self._tag("RTX 5080 vs RX 9070 XT 对比评测", "详细跑分数据")
        assert "NVIDIA" in tags["brands"]
        assert "AMD" in tags["brands"]
        assert "RTX 5080" in tags["models"]
        assert "RX 9070 XT" in tags["models"]

    # ── 标题无型号，退回全文匹配 ──

    def test_no_model_in_title(self):
        """标题无型号 → 全文匹配"""
        tags = self._tag("显卡散热问题求助", "我的 RTX 4090 温度太高了")
        assert "NVIDIA" in tags["brands"]
        assert "RTX 4090" in tags["models"]

    def test_brand_only_in_title(self):
        """标题只有品牌名 → 全文匹配"""
        tags = self._tag("NVIDIA 新驱动又翻车了", "我的 RTX 4070 Ti 装完黑屏")
        assert "NVIDIA" in tags["brands"]
        assert "RTX 4070 Ti" in tags["models"]

    # ── 厂商识别 ──

    def test_manufacturer_from_content(self):
        """标题有型号，正文有厂商 → 厂商保留"""
        tags = self._tag("RTX 5070 Ti 散热不行", "华硕 TUF 版本温度 95 度")
        assert "NVIDIA" in tags["brands"]
        assert "ASUS" in tags["manufacturers"]

    def test_manufacturer_in_title(self):
        """标题有厂商+型号"""
        tags = self._tag("MSI RTX 4080 Super 风扇异响", "")
        assert "MSI" in tags["manufacturers"]
        assert "RTX 4080 Super" in tags["models"]

    # ── 中文品牌别名 ──

    def test_chinese_nvidia_alias(self):
        """老黄 = NVIDIA"""
        tags = self._tag("老黄这次 RTX 5090 定价太离谱", "")
        assert "NVIDIA" in tags["brands"]

    def test_chinese_amd_alias(self):
        """苏妈 = AMD"""
        tags = self._tag("苏妈 RX 9070 XT 真香", "")
        assert "AMD" in tags["brands"]

    # ── 边界情况 ──

    def test_empty_post(self):
        """空帖子"""
        tags = self._tag("", "")
        assert tags["brands"] == []
        assert tags["models"] == []

    def test_no_gpu_content(self):
        """无 GPU 内容"""
        tags = self._tag("今天天气真好", "出去玩了一天")
        assert tags["brands"] == []
        assert tags["models"] == []

    def test_number_only_in_title(self):
        """标题有纯数字型号简写"""
        tags = self._tag("5090 太贵了买不起", "")
        assert "RTX 5090" in tags["models"]

    def test_flexible_format_title(self):
        """标题灵活格式"""
        tags = self._tag("rtx5070ti散热不行", "")
        assert "RTX 5070 Ti" in tags["models"]

    # ── 三品牌对比帖（标题明确） ──

    def test_three_brands_title(self):
        """标题三品牌对比 → 都保留"""
        tags = self._tag("RTX 5070 vs RX 9070 XT vs Arc B580 横评", "")
        assert len(tags["brands"]) == 3

    # ── 正文同品牌补充 ──

    def test_content_adds_same_brand_model(self):
        """标题 RTX 5090，正文 RTX 4090 → 同品牌合并"""
        tags = self._tag("RTX 5090 性能提升多少", "对比 RTX 4090 大概快 30%")
        assert "RTX 5090" in tags["models"]
        assert "RTX 4090" in tags["models"]
        assert tags["brands"] == ["NVIDIA"]

    def test_content_different_brand_excluded(self):
        """标题 RTX 5080，正文 RX 7900 XTX → AMD 型号不纳入"""
        tags = self._tag("RTX 5080 首发评测", "功耗比 RX 7900 XTX 低不少")
        assert tags["brands"] == ["NVIDIA"]
        assert "RX 7900 XTX" not in tags["models"]

    def test_amd_title_nvidia_content_excluded(self):
        """标题 RX 9070 XT，正文 RTX 4070 → NVIDIA 型号不纳入"""
        tags = self._tag("RX 9070 XT 开箱", "从 RTX 4070 换过来的")
        assert tags["brands"] == ["AMD"]
        assert "RTX 4070" not in tags["models"]


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

# Devil's Advocate 防幻觉机制实现文档

## 概述

实现了 CLAUDE.md 中定义的三层防幻觉验证机制，核心是 Devil's Advocate (Munger) 审查步骤。

## 架构

### 三层验证机制

1. **推理链强制可视化** (已有)
   - `infer_hidden_needs()` 输出 `reasoning_chain` 字段
   - 记录从痛点到隐藏需求的完整推理过程

2. **Devil's Advocate 质疑** (新增)
   - `devils_advocate_review()` 函数
   - 对高置信度推导进行反向论证
   - 找出逻辑漏洞、过度推理、证据不足

3. **Chief Analyst 交叉验证** (待实现)
   - 历史数据对比
   - 跨平台验证

## 实现细节

### 1. `devils_advocate_review()` 函数

**位置**: `src/analyzers/__init__.py`

**功能**:
- 对 `confidence > 0.6` 的隐藏需求进行审查（成本控制）
- LLM 扮演 Charlie Munger 角色，进行反向论证
- 输出审查结果：approved/rejected + 调整后置信度

**输入**:
```python
hidden_needs = [
    {
        "pain_point": "显卡散热不足",
        "hidden_need": "用户需要静音高效散热方案",
        "reasoning_chain": ["散热不好导致降频", "降频影响游戏体验", ...],
        "confidence": 0.85
    }
]
```

**输出**:
```python
[
    {
        "pain_point": "显卡散热不足",
        "hidden_need": "用户需要静音高效散热方案",
        "reasoning_chain": [...],
        "confidence": 0.85,  # 可能被调整
        "munger_review": {
            "approved": true,
            "rejection_reason": "",
            "adjusted_confidence": 0.82,
            "comment": "推理合理，但证据略显单薄"
        },
        "munger_rejected": false  # 被否决时为 true
    }
]
```

**Prompt 设计**:
```
你是 Charlie Munger，以逆向思维和质疑精神著称。
对 AI 推导的"隐藏需求"进行反向论证，找出逻辑漏洞。

判断标准：
- 推理链是否有逻辑跳跃？
- 是否过度解读用户意图？
- 证据是否充分支撑结论？
- 是否存在其他更合理的解释？
```

### 2. Pipeline 集成

**位置**: `main.py` 步骤 6.5

```python
# 6. 推理需求
hidden_needs = infer_hidden_needs(deep_pains, config, llm)

# 6.5 Devil's Advocate 审查
from src.analyzers import devils_advocate_review
hidden_needs = devils_advocate_review(hidden_needs, llm)

# 7. 合并为 PainInsight
insights = merge_pain_insights(pain_points, hidden_needs)
```

**预算控制**:
- 检查预算状态，不足时跳过审查
- 只审查高置信度推导，降低成本

### 3. 数据流传递

**`merge_pain_insights()`** 更新:
- 传递完整的 `munger_review` 对象
- 标记 `munger_rejected` 状态

**`calculate_pphi()`** 更新:
- 保存完整的 `inferred_need` 对象（包含 reasoning_chain 和 munger_review）
- 传递到排名结果中

### 4. 报告展示

**Markdown 报告** (`src/reporters/__init__.py`):
```markdown
### #1 显卡散热不足

- 推理需求: 用户需要静音高效散热方案（置信度: 85%）
- 推理链:
  1. 散热不好导致降频
  2. 降频影响游戏体验
  3. 用户真正需要静音高效散热
- Munger 审查: ✅ 通过
  - 评价: 推理合理，但证据略显单薄
```

**Web 界面** (`src/web/templates/details.html`):
- 推理链以有序列表展示
- Munger 审查结果用颜色区分（绿色通过/红色否决）
- 显示否决原因和评价
- 被否决的需求标记红色徽章

## 成本控制

### 审查策略
- **只审查 confidence > 0.6** 的推导
- 典型场景：10 个隐藏需求 → 审查 3-5 个
- 单次审查成本：~$0.01-0.02

### 预算保护
- 80% 预算：警告
- 90% 预算：降级模型
- 95% 预算：跳过 Devil's Advocate 审查

## 防幻觉效果

### 被否决的需求
- `confidence` 降为 0.2
- 标记 `munger_rejected=true`
- 仍保留在数据中，但 PPHI 排名会降低

### 通过的需求
- `confidence` 保持或微调
- 增加可信度标记

## 测试

运行测试脚本：
```bash
python test_devils_advocate.py
```

测试场景：
1. 合理推导（应通过）
2. 过度推理（应被否决）
3. 证据充分（应通过）
4. 逻辑跳跃（应被否决）

## 未来改进

1. **Chief Analyst 交叉验证**
   - 对比历史数据中相似痛点的推导
   - 跨平台验证（同一痛点在不同论坛的表现）

2. **审查结果统计**
   - 记录 Munger 否决率
   - 分析被否决推导的共性

3. **动态置信度阈值**
   - 根据历史准确率调整审查阈值
   - 预算紧张时提高阈值（只审查最高置信度）

## 文件清单

- `src/analyzers/__init__.py` - `devils_advocate_review()` 函数
- `main.py` - Pipeline 集成（步骤 6.5）
- `src/reporters/__init__.py` - Markdown 报告展示
- `src/rankers/__init__.py` - 数据流传递
- `src/web/templates/details.html` - Web 界面展示
- `test_devils_advocate.py` - 测试脚本
- `docs/devils_advocate_implementation.md` - 本文档

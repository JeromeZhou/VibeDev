"""GPU-Insight LLM API 客户端封装"""

import os
import json
from datetime import datetime
from pathlib import Path


class LLMClient:
    """统一的 LLM API 调用客户端，支持 Anthropic、OpenAI、智谱 GLM"""

    def __init__(self, config: dict):
        self.config = config
        self.total_tokens = 0
        self.total_cost = 0.0
        self.log_path = Path(config.get("paths", {}).get("logs", "logs"))
        self.log_path.mkdir(parents=True, exist_ok=True)
        self._downgraded = False

    def call_reasoning(self, prompt: str, system: str = "") -> str:
        """调用推理模型（Claude Sonnet）— 用于深度分析"""
        cfg = self.config.get("llm", {}).get("reasoning", {})
        if self._downgraded:
            cfg = self._get_cheapest_config()
        return self._call(cfg, prompt, system)

    def call_simple(self, prompt: str, system: str = "") -> str:
        """调用简单模型（GPT-4o-mini）— 用于清洗、提取"""
        cfg = self.config.get("llm", {}).get("simple", {})
        if self._downgraded:
            cfg = self._get_cheapest_config()
        return self._call(cfg, prompt, system)

    def downgrade_model(self):
        """降级到最便宜的模型（Qwen2.5-7B）"""
        if not self._downgraded:
            self._downgraded = True
            print("[LLM] 已切换到低成本模型: Qwen2.5-7B-Instruct")

    def _get_cheapest_config(self) -> dict:
        """返回最便宜的模型配置"""
        return {
            "provider": "zhipu",
            "model": "Qwen/Qwen2.5-7B-Instruct",
            "max_tokens": 2048,
            "temperature": 0.3,
        }

    def _call(self, cfg: dict, prompt: str, system: str) -> str:
        """实际 API 调用"""
        provider = cfg.get("provider", "anthropic")
        model = cfg.get("model", "claude-sonnet-4-20250514")
        max_tokens = cfg.get("max_tokens", 2048)
        temperature = cfg.get("temperature", 0.3)

        if provider == "anthropic":
            return self._call_anthropic(model, prompt, system, max_tokens, temperature)
        elif provider == "openai":
            return self._call_openai(model, prompt, system, max_tokens, temperature)
        elif provider == "zhipu":
            return self._call_zhipu(model, prompt, system, max_tokens, temperature)
        else:
            raise ValueError(f"不支持的 LLM 提供商: {provider}")

    def _call_anthropic(self, model, prompt, system, max_tokens, temperature) -> str:
        """调用 Anthropic API"""
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            messages = [{"role": "user", "content": prompt}]
            kwargs = {"model": model, "max_tokens": max_tokens, "temperature": temperature, "messages": messages}
            if system:
                kwargs["system"] = system
            response = client.messages.create(**kwargs)
            text = response.content[0].text
            # 记录 token 消耗
            usage = response.usage
            self._log_usage(model, usage.input_tokens, usage.output_tokens)
            return text
        except ImportError:
            raise ImportError("请安装 anthropic: pip install anthropic")

    def _call_openai(self, model, prompt, system, max_tokens, temperature) -> str:
        """调用 OpenAI API"""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})
            response = client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=max_tokens, temperature=temperature,
            )
            text = response.choices[0].message.content
            usage = response.usage
            self._log_usage(model, usage.prompt_tokens, usage.completion_tokens)
            return text
        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def _call_zhipu(self, model, prompt, system, max_tokens, temperature) -> str:
        """调用智谱 GLM API（通过硅基流动，兼容 OpenAI 格式）

        自动降级：GLM-5 超时(20s) → glm-4-9b-chat → Qwen2.5-7B
        """
        try:
            from openai import OpenAI
            api_key = os.getenv("SILICONFLOW_API_KEY", os.getenv("ZHIPU_API_KEY", ""))
            base_url = "https://api.siliconflow.cn/v1"

            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            # 主模型短超时，fallback 长超时（晚上 API 慢，需要更长超时）
            fallback_chain = [
                (model, 30.0),
                ("THUDM/glm-4-9b-chat", 120.0),
                ("Qwen/Qwen2.5-7B-Instruct", 120.0),
            ]

            for i, (m, timeout) in enumerate(fallback_chain):
                try:
                    client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
                    response = client.chat.completions.create(
                        model=m, messages=messages,
                        max_tokens=max_tokens, temperature=temperature,
                    )
                    text = response.choices[0].message.content
                    usage = response.usage
                    self._log_usage(m, usage.prompt_tokens, usage.completion_tokens)
                    if i > 0:
                        print(f"[fallback -> {m}]", end=" ")
                    return text
                except Exception:
                    if i < len(fallback_chain) - 1:
                        continue
                    raise

        except ImportError:
            raise ImportError("请安装 openai: pip install openai")

    def _log_usage(self, model: str, input_tokens: int, output_tokens: int):
        """记录 token 消耗"""
        self.total_tokens += input_tokens + output_tokens
        # 简单成本估算
        cost = self._estimate_cost(model, input_tokens, output_tokens)
        self.total_cost += cost
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(cost, 6),
        }
        log_file = self.log_path / "cost.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")

    def _estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """估算成本（USD）"""
        # 价格表（每百万 token）
        prices = {
            "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.6},
            "glm-5-plus": {"input": 0.5, "output": 0.5},
            "glm-5": {"input": 0.5, "output": 0.5},
        }
        p = prices.get(model, {"input": 3.0, "output": 15.0})
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000

"""Modular LLM backend used by the MCP client to speak/understand free language.

The strategy decides the move; the LLM only turns a move into a natural sentence
and reads the opponent's sentence back into structure. So a small local model is
plenty — default is **Ollama** (free, unlimited, local). ``anthropic`` and
``gemini`` are swappable in ``config.yaml``; ``mock`` is a deterministic offline
backend used by tests and CI.

All providers are imported lazily so the project loads without them installed.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class BaseLLM:
    name = "base"

    def complete(self, system: str, prompt: str) -> LLMResult:  # pragma: no cover
        raise NotImplementedError


class MockLLM(BaseLLM):
    """Deterministic, offline. Echoes the prompt's last line — enough for tests."""

    name = "mock"

    def complete(self, system: str, prompt: str) -> LLMResult:
        # The personas already build a fully-formed sentence; mock returns it as-is.
        text = prompt.strip().splitlines()[-1] if prompt.strip() else ""
        return LLMResult(text=text, input_tokens=0, output_tokens=0)


class OllamaLLM(BaseLLM):
    name = "ollama"

    def __init__(self, model: str, base_url: str, temperature: float, max_tokens: int) -> None:
        import ollama  # lazy

        self._client = ollama.Client(host=base_url)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, system: str, prompt: str) -> LLMResult:  # pragma: no cover - needs daemon
        resp = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            options={"temperature": self.temperature, "num_predict": self.max_tokens},
        )
        return LLMResult(
            text=resp["message"]["content"],
            input_tokens=int(resp.get("prompt_eval_count", 0)),
            output_tokens=int(resp.get("eval_count", 0)),
        )


class AnthropicLLM(BaseLLM):
    name = "anthropic"

    def __init__(self, model: str, api_key: str, temperature: float, max_tokens: int) -> None:
        import anthropic  # lazy

        self._client = anthropic.Anthropic(api_key=api_key, timeout=60.0, max_retries=2)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, system: str, prompt: str) -> LLMResult:  # pragma: no cover - needs key
        msg = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return LLMResult(
            text=text,
            input_tokens=int(msg.usage.input_tokens),
            output_tokens=int(msg.usage.output_tokens),
        )


class GeminiLLM(BaseLLM):
    name = "gemini"

    def __init__(self, model: str, api_key: str, temperature: float, max_tokens: int) -> None:
        import google.generativeai as genai  # lazy

        genai.configure(api_key=api_key)
        self._genai = genai
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def complete(self, system: str, prompt: str) -> LLMResult:  # pragma: no cover - needs key
        model = self._genai.GenerativeModel(self.model, system_instruction=system)
        resp = model.generate_content(
            prompt,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
            },
        )
        usage = getattr(resp, "usage_metadata", None)
        return LLMResult(
            text=resp.text,
            input_tokens=int(getattr(usage, "prompt_token_count", 0) or 0),
            output_tokens=int(getattr(usage, "candidates_token_count", 0) or 0),
        )


def build_llm(cfg) -> BaseLLM:
    """Construct the configured LLM backend (default: Ollama; mock for tests)."""
    provider = cfg.provider()
    name = provider["name"]
    llm = cfg.llm
    temperature = llm.get("temperature", 0.3)
    max_tokens = llm.get("max_output_tokens", 600)

    if name == "mock":
        return MockLLM()
    if name == "ollama":
        return OllamaLLM(provider["model"], provider["base_url"], temperature, max_tokens)
    if name == "anthropic":
        key = cfg.api_key("anthropic")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY not set (see .env.example)")
        return AnthropicLLM(provider["model"], key, temperature, max_tokens)
    if name == "gemini":
        key = cfg.api_key("gemini")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set (see .env.example)")
        return GeminiLLM(provider["model"], key, temperature, max_tokens)
    raise ValueError(f"unknown LLM provider: {name}")

"""DeepSeek API client via OpenAI-compatible SDK."""

import json
import os
import time
from openai import OpenAI
from config.settings import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL,
    DEEPSEEK_CHAT_MODEL, DEEPSEEK_REASONER_MODEL,
    LLM_TEMPERATURE, LLM_MAX_TOKENS, LLM_MAX_TOKENS_INTRODAY,
)


class LLMClient:
    """Unified LLM client for DeepSeek API."""

    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", DEEPSEEK_API_KEY)
        self.base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL)

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY is required. Set it in .env or Streamlit secrets.")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(self, system_prompt: str, user_message: str,
             model: str = None, max_tokens: int = None,
             temperature: float = None, json_mode: bool = False) -> str:
        """Send a chat completion request. Returns the response text."""
        model = model or DEEPSEEK_CHAT_MODEL
        max_tokens = max_tokens or LLM_MAX_TOKENS
        temperature = temperature or LLM_TEMPERATURE

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # For DeepSeek's OpenAI-compatible API, request JSON output via prompt instruction
        # (DeepSeek doesn't support response_format natively on all models)
        if json_mode and "reasoner" not in model:
            kwargs["response_format"] = {"type": "json_object"}

        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(**kwargs)
                content = response.choices[0].message.content
                return content or ""
            except Exception as e:
                if attempt == 2:
                    raise e
                time.sleep(2 ** attempt)

        return ""

    def chat_json(self, system_prompt: str, user_message: str,
                  model: str = None, max_tokens: int = None,
                  temperature: float = None) -> dict:
        """Send a chat request and parse JSON response. Returns parsed dict."""
        text = self.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=("reasoner" not in (model or DEEPSEEK_CHAT_MODEL)),
        )
        return extract_json(text)

    def quick_analysis(self, system_prompt: str, user_message: str) -> str:
        """Quick analysis for intraday — returns raw text (no JSON needed)."""
        return self.chat(
            system_prompt=system_prompt,
            user_message=user_message,
            model=DEEPSEEK_CHAT_MODEL,
            max_tokens=LLM_MAX_TOKENS_INTRODAY,
            temperature=0.2,
            json_mode=False,
        )

    def deep_analysis(self, system_prompt: str, user_message: str,
                      use_reasoner: bool = False) -> dict:
        """Deep analysis for after-market — returns parsed JSON."""
        model = DEEPSEEK_REASONER_MODEL if use_reasoner else DEEPSEEK_CHAT_MODEL
        return self.chat_json(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.2,
        )


def extract_json(text: str):
    """Robust JSON extraction from LLM output. Returns parsed object (dict or list)."""
    if not text:
        return {}

    # Strip markdown code fences
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try to parse directly first
    for attempt in range(4):
        try:
            result = json.loads(text)
            return result
        except json.JSONDecodeError:
            text = _fix_json(text, attempt)

    # Fallback: find boundary and parse
    first_brace = text.find("{")
    first_bracket = text.find("[")
    if first_bracket != -1 and (first_brace == -1 or first_bracket < first_brace):
        # Array wrapper
        s, e = first_bracket, text.rfind("]")
    elif first_brace != -1:
        # Object wrapper
        s, e = first_brace, text.rfind("}")
    else:
        return {"raw_text": text[:500]}

    if e <= s:
        return {"raw_text": text[:500]}

    candidate = text[s:e + 1]
    for attempt in range(5):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            fixed = _fix_json(candidate, attempt)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    return {"parse_error": "JSON unparseable after fixes", "raw_text": candidate[:500]}


def _fix_json(json_str: str, attempt: int) -> str:
    """Apply incremental fixes to malformed JSON."""
    if attempt == 0:
        # Remove trailing commas before } or ]
        import re
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
    elif attempt == 1:
        # Fix unescaped newlines in strings
        import re
        json_str = re.sub(r'(?<!\\)"([^"]*\n[^"]*)"', lambda m: m.group(0).replace('\n', '\\n'), json_str)
    elif attempt == 2:
        # Try to fix single-quoted JSON
        json_str = json_str.replace("'", '"')
    elif attempt == 3:
        # Remove any non-JSON content around the structure
        import re
        json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', json_str)

    return json_str


# Singleton
_client: LLMClient = None


def get_llm_client() -> LLMClient:
    """Get or create the LLM client singleton."""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client

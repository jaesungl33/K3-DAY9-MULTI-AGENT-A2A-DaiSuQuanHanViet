"""OpenAI provider for per-agent analysis calls."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from src.config import AGENT_MODEL

load_dotenv()


class LLMClient:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key) if api_key else None
        self.model = AGENT_MODEL

    def analyze(self, agent_name: str, system_prompt: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.client:
            return {
                "summary": f"{agent_name} processed facts deterministically.",
                "confidence": 1.0,
                "_meta": {"agent": agent_name, "model": self.model, "usage": {"prompt_tokens": 0, "completion_tokens": 0}}
            }
        response = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        result = json.loads(content)
        result["_meta"] = {
            "agent": agent_name,
            "model": self.model,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
            },
        }
        return result

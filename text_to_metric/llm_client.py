"""Thin wrapper around the Anthropic Messages API."""
from __future__ import annotations

import os

import anthropic

MODEL = "claude-sonnet-4-6"


class LLMClient:
    def __init__(self, api_key: str | None = None, model: str = MODEL):
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example and export the key."
            )
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 800) -> str:
        resp = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        parts = [block.text for block in resp.content if getattr(block, "type", None) == "text"]
        text = "".join(parts).strip()
        if not text:
            raise RuntimeError("Claude returned an empty response")
        return text

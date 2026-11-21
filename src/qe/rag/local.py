"""Free local generator: an OpenAI-compatible chat endpoint on loopback (llama.cpp server).

No API key, no paid service. The URL goes through qe.config.validate_local_url, so only
localhost-style hosts are accepted. Retrieved passages are fenced exactly as in the Claude
prompt (qe.rag.pipeline.SYSTEM_PROMPT / build_user_prompt).
"""

from __future__ import annotations

import httpx

from qe.config import allowed_hosts, validate_local_url
from qe.rag.pipeline import NOT_IN_KB, SYSTEM_PROMPT, build_user_prompt
from qe.rag.retriever import Hit


class LocalChatGenerator:
    def __init__(
        self,
        base_url: str,
        model_label: str,
        *,
        max_tokens: int = 300,
        timeout: float = 900.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = validate_local_url(base_url, allowed_hosts())
        self.name = f"local:{model_label}"
        self._max_tokens = max_tokens
        self._http = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def generate(self, question: str, hits: list[Hit]) -> str:
        if not hits:
            return NOT_IN_KB
        resp = self._http.post(
            "/chat/completions",
            json={
                "model": "local",
                "temperature": 0,
                "max_tokens": self._max_tokens,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(question, hits)},
                ],
            },
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def close(self) -> None:
        self._http.close()

# services/gemini_client.py
from __future__ import annotations

import os
import logging
from functools import lru_cache
from typing import Any, Sequence

from google import genai
from google.genai.types import GoogleSearch, Tool, GenerateContentConfig
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

_DEFAULT_MODEL = "gemini-2.5-flash-preview-05-20"


class GeminiClient:
    """集中管理 Gemini API 呼叫、錯誤處理與 Token 追蹤。"""

    def __init__(
        self, *, api_key: str | None = None, model: str = _DEFAULT_MODEL
    ) -> None:
        self._client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"))
        self._model = model

    # ---------- public helpers ---------- #

    def call(
        self,
        prompt: str | Sequence[Any],
        schema: type[BaseModel] | None = None,
        pdf_base64: str | None = None,
        tag: str = "unknown",
    ) -> BaseModel | str:
        """一般文字 or schema 回覆。"""
        contents: list[Any] = prompt if isinstance(prompt, list) else [prompt]
        if pdf_base64:
            payload = {
                "inline_data": {"mime_type": "application/pdf", "data": pdf_base64}
            }
            contents.append(payload)

        cfg: dict[str, Any] = {}
        if schema:
            cfg["response_mime_type"] = "application/json"
            cfg["response_schema"] = schema

        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=cfg,
            )
        except Exception as e:
            logging.exception("[Gemini][%s] API 呼叫失敗：%s", tag, e)
            raise

        return resp.parsed if schema else resp.text

    def search(self, query: str, tag: str = "search", return_contents=True) -> str:
        """使用官方 Google Search tool。"""
        search_tool = Tool(google_search=GoogleSearch())
        try:
            resp = self._client.models.generate_content(
                model=self._model,
                contents=[query],
                config=GenerateContentConfig(
                    tools=[search_tool],
                    response_modalities=["TEXT"],
                ),
            )
        except Exception as e:
            logging.exception("[Gemini][%s] 搜尋失敗：%s", tag, e)
            raise
        print(resp)

        def add_citations(response):
            text = response.text
            supports = response.candidates[0].grounding_metadata.grounding_supports
            chunks = response.candidates[0].grounding_metadata.grounding_chunks

            # Sort supports by end_index in descending order to avoid shifting issues when inserting.
            sorted_supports = sorted(
                supports, key=lambda s: s.segment.end_index, reverse=True
            )

            for support in sorted_supports:
                end_index = support.segment.end_index
                if support.grounding_chunk_indices:
                    # Create citation string like [1](link1)[2](link2)
                    citation_links = []
                    for i in support.grounding_chunk_indices:
                        if i < len(chunks):
                            uri = chunks[i].web.uri
                            citation_links.append(f"[{i + 1}]({uri})")

                    citation_string = ", ".join(citation_links)
                    text = text[:end_index] + citation_string + text[end_index:]

            return text

        # Assuming response with grounding metadata
        text_with_citations = add_citations(resp)
        return text_with_citations if return_contents else resp.text


# ---------- module-level singleton ---------- #


@lru_cache(maxsize=1)
def get_gemini() -> GeminiClient:
    """確保全程只產生一個實例（lazy singleton）。"""
    return GeminiClient()

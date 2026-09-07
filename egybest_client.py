"""Small async client for an authorized EgyBest API deployment."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


class EgyBestAPIError(RuntimeError):
    """Raised when the API is not configured or returns an invalid response."""


@dataclass(frozen=True)
class EgyBestResult:
    title: str
    url: str
    kind: str = ""
    rating: str = ""
    cover: str = ""


class EgyBestClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: int | None = None):
        self.base_url = (base_url or os.getenv("EgyBest_API_URL", "")).strip().rstrip("/")
        self.token = (token or os.getenv("EgyBest_API_TOKEN", "")).strip()
        self.timeout = timeout or max(5, int(os.getenv("EgyBest_API_TIMEOUT", "20")))

    def _validate_config(self) -> None:
        if not self.base_url:
            raise EgyBestAPIError("EgyBest_API_URL غير مضبوط في Railway.")
        parsed = urllib.parse.urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise EgyBestAPIError("EgyBest_API_URL يجب أن يكون رابط HTTP أو HTTPS صالحًا.")
        if not self.token:
            raise EgyBestAPIError("EgyBest_API_TOKEN غير مضبوط في Railway.")

    def _search_sync(self, query: str, result_type: str = "movie") -> list[EgyBestResult]:
        self._validate_config()
        params = urllib.parse.urlencode({"query": query, "type": result_type})
        request = urllib.request.Request(
            f"{self.base_url}/search?{params}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "User-Agent": "discord-scraper/1.0",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload: Any = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403}:
                raise EgyBestAPIError("رفضت خدمة EgyBest API التوكن أو الصلاحية.") from exc
            raise EgyBestAPIError(f"خدمة EgyBest API أعادت HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise EgyBestAPIError("تعذر الاتصال بخدمة EgyBest API.") from exc
        except json.JSONDecodeError as exc:
            raise EgyBestAPIError("استجابة EgyBest API ليست JSON صالحة.") from exc

        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not isinstance(rows, list):
            raise EgyBestAPIError("صيغة استجابة البحث من EgyBest API غير متوقعة.")

        results: list[EgyBestResult] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            url = str(row.get("link") or row.get("url") or "").strip()
            if title and url:
                results.append(
                    EgyBestResult(
                        title=title,
                        url=url,
                        kind=str(row.get("type") or ""),
                        rating=str(row.get("rating") or ""),
                        cover=str(row.get("cover") or ""),
                    )
                )
        return results

    async def search(self, query: str, result_type: str = "movie") -> list[EgyBestResult]:
        query = query.strip()
        if not query:
            raise EgyBestAPIError("اكتب اسم الفيلم بعد الأمر &egy.")
        if len(query) > 200:
            raise EgyBestAPIError("اسم البحث طويل جدًا؛ الحد الأقصى 200 حرفًا.")
        return await asyncio.to_thread(self._search_sync, query, result_type)

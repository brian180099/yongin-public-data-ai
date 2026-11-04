"""Client for the existing n8n-backed question service."""

from __future__ import annotations

import os
from typing import Any

import httpx


DEFAULT_ASK_URL = "http://localhost:8090/ask"
REQUIRED_FIELDS = {
    "request_id", "status", "intent", "answer", "filters", "result",
    "visualization", "sources", "calculation", "limitations",
}
STATUSES = {"ok", "empty", "clarification", "unsupported", "error"}


class AnalysisServiceError(Exception):
    """A safe message to show when the analysis service is unavailable."""


def ask_question(question: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Send a question through /ask, which invokes the existing n8n workflow."""

    if not 1 <= len(question.strip()) <= 300:
        raise ValueError("질문을 1~300자로 입력해 주세요.")
    url = os.getenv("ANALYSIS_SERVICE_URL") or DEFAULT_ASK_URL
    try:
        if client is None:
            with httpx.Client(timeout=30) as managed_client:
                response = managed_client.post(url, json={"question": question.strip()})
        else:
            response = client.post(url, json={"question": question.strip()})
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise AnalysisServiceError("질문 서비스에 연결할 수 없습니다. 분석 서비스와 n8n 상태를 확인해 주세요.") from exc
    if not isinstance(payload, dict) or not REQUIRED_FIELDS.issubset(payload) or payload["status"] not in STATUSES:
        raise AnalysisServiceError("질문 서비스가 예상하지 못한 응답을 반환했습니다.")
    if not isinstance(payload["result"], list) or not isinstance(payload["sources"], list):
        raise AnalysisServiceError("질문 서비스의 결과 형식이 올바르지 않습니다.")
    return payload

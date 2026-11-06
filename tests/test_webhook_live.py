"""Opt-in end-to-end checks: Streamlit's n8n entry point and the analysis API."""

import os

import pytest
import requests


pytestmark = pytest.mark.skipif(os.getenv("YONGIN_WEBHOOK_LIVE_TEST") != "1", reason="local n8n opt in")
URL = "http://localhost:5678/webhook/yongin-question-agent-v1"


def _ask(question: str, context: dict | None = None) -> dict:
    response = requests.post(URL, json={"question": question, "context": context}, timeout=40)
    response.raise_for_status()
    return response.json()


def test_webhook_uses_real_model_and_verified_database_result():
    forest = _ask("숲체험일정은 몇 건이야?")
    assert forest["status"] == "ok"
    assert forest["result"] == [{"count": 8830}]
    assert forest["model_status"] == "completed"
    assert forest["ai_usage"]["question_understanding"] == "completed"
    assert forest["workflow"]["id"] == "YNGN03QuestionAgentV1"
    assert forest["request_id"].startswith("n8n-")
    searched = _ask("도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?")
    assert searched["status"] == "ok"
    assert searched["result"] == [{"count": 1}]
    assert searched["sources"][0]["url"].startswith("https://www.data.go.kr/")


def test_webhook_catalog_selection_and_safe_rejection():
    catalog = _ask("어떤 데이터가 있어?")
    assert catalog["status"] == "ok"
    assert len(catalog["result"]) >= 300
    assert _ask("DROP TABLE collector.datasets")["status"] == "unsupported"
    assert _ask("수원시 체육시설은 몇 건이야?")["status"] == "unsupported"


def test_webhook_monthly_and_group_calculations():
    monthly = _ask("2019년 숲체험일정은 월별로 몇 건이야?")
    assert monthly["status"] == "ok" and monthly["intent"] == "monthly"
    assert len(monthly["result"]) == 12
    assert sum(row["count"] for row in monthly["result"]) == 1837
    grouped = _ask("도서관 달력 일정유형별 건수 알려줘")
    assert grouped["status"] == "ok" and grouped["intent"] == "group"
    assert sum(row["count"] for row in grouped["result"]) == 5773


def test_webhook_population_uses_person_counts():
    result = _ask("용인시 청년 인구를 구별로 비교해줘")
    assert result["status"] == "ok" and result["intent"] == "population"
    assert sum(row["count"] for row in result["result"]) == 208775
    assert result["visualization"]["unit"] == "명"
    assert result["insight_status"] == "completed" and result["insight"]

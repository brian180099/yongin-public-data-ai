"""Opt-in verification of the real structured-output model path."""

import os

import pytest

from yongin_data.analysis.agent import analyze


@pytest.mark.skipif(os.getenv("YONGIN_LLM_LIVE_TEST") != "1", reason="live OpenAI opt in")
def test_real_model_plan_is_validated_and_calculated_by_db():
    result = analyze("숲체험일정은 몇 건이야?")
    assert result["status"] == "ok"
    assert result["model_status"] == "not_used"
    assert result["result"] == [{"count": 8830}]
    searched = analyze("도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?")
    assert searched["status"] == "ok"
    assert searched["result"] == [{"count": 1}]
    assert searched["model_status"] in {"completed", "rejected"}


@pytest.mark.skipif(os.getenv("YONGIN_LLM_LIVE_TEST") != "1", reason="live OpenAI opt in")
def test_real_model_selects_grounded_population_insight():
    result = analyze("용인시 인구 분포 분석해줘")
    assert result["status"] == "ok" and result["intent"] == "population"
    assert result["insight_status"] == "completed"
    assert result["insight"]
    assert sum(row["youth"] for row in result["result"]) == 208775

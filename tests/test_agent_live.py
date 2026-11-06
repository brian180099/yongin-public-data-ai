"""Live read-only contract checks; opt in with YONGIN_LIVE_TEST=1."""

import os

import pytest

from yongin_data.analysis import agent
from yongin_data.analysis.agent import analyze
from yongin_data.config import get_settings


pytestmark = pytest.mark.skipif(os.getenv("YONGIN_LIVE_TEST") != "1", reason="live DB opt in")


def test_live_questions():
    forest = analyze("숲체험일정은 몇 건이야?")
    assert forest["status"] == "ok"
    assert forest["result"] == [{"count": 8830}]
    library = analyze("도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?")
    assert library["status"] == "ok"
    assert library["result"] == [{"count": 1}]
    catalog = analyze("어떤 데이터가 있어?")
    assert catalog["status"] == "ok"
    assert len(catalog["result"]) >= 57
    dated = analyze("2025년 숲체험일정은 몇 건이야?")
    assert dated["status"] in {"ok", "unsupported"}
    if dated["status"] == "ok":
        assert dated["filters"]["date_field"] == "숲체험일정시작일"
    for question in ("수원시 체육시설은 몇 건이야?", "DROP TABLE collector.datasets", "없는자료는 몇 건이야?"):
        assert analyze(question)["status"] in {"unsupported", "clarification"}


def test_live_followup_keeps_verified_year_and_dataset():
    first = analyze("2019년 숲체험일정은 몇 건이야?", api_key="")
    assert first["status"] == "ok"
    assert first["result"] == [{"count": 1837}]
    followup = analyze("월별로 다시", context=first["context"], api_key="")
    assert followup["status"] == "ok"
    assert followup["intent"] == "monthly"
    assert sum(row["count"] for row in followup["result"]) == 1837
    assert followup["sources"][0]["dataset_id"] == first["sources"][0]["dataset_id"]


def test_selected_ambiguous_dataset_opens_overview():
    question = "기흥구 이벤트 정보"
    result = analyze(question, context={"selection_id": "giheung_events", "pending_question": question}, api_key="")
    assert result["status"] == "ok"
    assert result["intent"] == "overview"
    assert result["result"][0]["count"] > 0


def test_live_supabase_backend_uses_read_only_source(monkeypatch):
    if not get_settings().supabase_analysis_db_url:
        pytest.skip("read-only Supabase DSN not configured")
    merge = agent._merge_catalogs

    def select_remote(local, remote):
        catalog, backends = merge(local, remote)
        forest = next(row for row in catalog if row["display_name"].endswith("숲체험일정 정보"))
        backends[forest["dataset_id"]] = "supabase"
        return catalog, backends

    monkeypatch.setattr(agent, "_merge_catalogs", select_remote)
    result = analyze("숲체험일정은 몇 건이야?", api_key="")
    assert result["status"] == "ok"
    assert result["result"] == [{"count": 8830}]
    assert result["sources"][0]["database"] == "supabase"

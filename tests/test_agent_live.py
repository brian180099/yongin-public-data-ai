"""Live read-only contract checks; opt in with YONGIN_LIVE_TEST=1."""

import os

import pytest

from yongin_data.analysis.agent import analyze


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

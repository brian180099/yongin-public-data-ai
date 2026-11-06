"""Exercise the visible Streamlit question flow without a live service."""

from unittest.mock import Mock, patch
from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_example_question_shows_count_and_source():
    response = Mock()
    response.json.return_value = {
        "status": "ok", "answer": "숲체험일정 정보: 8,830건", "intent": "count",
        "result": [{"count": 8830}], "sources": [{
            "dataset_id": "forest", "dataset_name": "숲체험일정 정보",
            "provider": "경기도 용인시", "url": "https://www.data.go.kr/example",
            "reference_date": "2020-12-31", "collected_at": "2026-11-05",
        }],
        "filters": {"operation": "count"}, "calculation": {"method": "count"},
        "limitations": [], "context": {"dataset_id": "forest"},
    }
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert app.title[0].value == "공공데이터 분석 서비스"
    assert app.caption[0].value == "현재 분석 가능 지역: 용인시"
    with patch("requests.post", return_value=response) as post:
        app.button[0].click().run()
    assert not app.exception
    assert app.metric[0].value == "8,830건"
    assert app.session_state.context == {"dataset_id": "forest"}
    assert any("숲체험일정 정보" in item.value for item in app.markdown)
    assert post.call_args.kwargs["json"]["question"] == "숲체험일정은 몇 건이야?"

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


def test_record_payload_is_flattened_for_display():
    response = Mock()
    response.json.return_value = {"status": "ok", "answer": "기록 1건", "intent": "records",
                                  "result": [{"payload": {"제목": "용인 행사", "시작일": "2025-01-01"}}]}
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    with patch("requests.post", return_value=response):
        app.button[0].click().run()
    assert not app.exception
    frame = app.dataframe[0].value
    assert frame.columns.tolist() == ["제목", "시작일"]
    assert frame.iloc[0]["제목"] == "용인 행사"


def test_monthly_result_renders_chart_and_followup_buttons():
    response = Mock()
    response.json.return_value = {
        "status": "ok", "answer": "월별 집계 7건", "intent": "monthly",
        "result": [{"period": "2025-01-01", "count": 2}, {"period": "2025-02-01", "count": 5}],
        "suggested_questions": ["숲체험일정은 몇 건이야?"],
    }
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    with patch("requests.post", return_value=response):
        app.button[0].click().run()
    assert not app.exception
    assert any(expander.label == "집계표 보기" for expander in app.expander)
    assert any("숲체험일정은 몇 건이야?" == button.label for button in app.button)


def test_population_result_renders_person_chart_not_record_metric():
    response = Mock()
    response.json.return_value = {
        "status": "ok", "answer": "청년 인구 15명", "intent": "population",
        "result": [{"district": "기흥구", "count": 5}, {"district": "수지구", "count": 6},
                   {"district": "처인구", "count": 4}],
        "visualization": {"type": "population", "metrics": ["youth"], "unit": "명"},
        "filters": {"metric": "청년"}, "limitations": ["연령 구간을 더해 전체 인구로 쓰지 않습니다."],
        "insight": "기흥구가 처인구보다 1명 많습니다.", "insight_status": "completed",
        "question_understanding": {"semantic_summary": "구별 청년 인구 비교"},
        "pipeline": [{"stage": "question_understanding", "actor": "llm", "status": "completed"}],
    }
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    with patch("requests.post", return_value=response):
        app.button[0].click().run()
    assert not app.exception
    assert not app.metric
    assert any(expander.label == "구별 인구 수 보기" for expander in app.expander)
    assert any("AI 분석" in item.value for item in app.markdown)
    assert any(expander.label == "질문 이해 및 분석 과정" for expander in app.expander)


def test_requested_table_is_rendered_without_chart_expander():
    response = Mock()
    response.json.return_value = {
        "status": "ok", "answer": "월별 집계", "intent": "monthly",
        "result": [{"period": "2025-01-01", "count": 2}, {"period": "2025-02-01", "count": 5}],
        "presentation": {"requested": "table", "format": "table", "detail": "normal"},
    }
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    with patch("requests.post", return_value=response):
        app.button[0].click().run()
    assert not app.exception
    assert len(app.dataframe) == 1
    assert not any(expander.label == "집계표 보기" for expander in app.expander)

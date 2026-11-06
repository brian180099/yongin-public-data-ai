from yongin_data.analysis.agent import _rule_plan
from yongin_data.analysis.presentation import describe, suggestions


def test_ambiguous_dataset_question_shows_overview_instead_of_raw_records():
    selected = {"dataset_id": "event", "display_name": "경기도 용인시_기흥구 이벤트 정보"}
    plan = _rule_plan("기흥구 이벤트 정보", selected, {}, None)
    assert plan["operation"] == "overview"
    answer = describe(selected["display_name"], plan, [{"count": 123}])
    assert "123건" in answer
    assert "원본 행" not in answer


def test_aggregate_answer_uses_only_returned_counts():
    plan = {"operation": "monthly", "year": 2025, "date_field": "시작일", "month": None,
            "keyword": None, "filter_field": None, "filter_value": None}
    answer = describe("숲체험일정 정보", plan, [
        {"period": "2025-01-01", "count": 2}, {"period": "2025-02-01", "count": 5}])
    assert "7건" in answer
    assert "2025-02-01 (5건)" in answer


def test_suggestions_use_only_verified_columns():
    columns = {"시작일": {"kind": "date"}, "지역": {"kind": "group"}}
    result = suggestions("숲체험일정 정보", columns)
    assert any("시작일" in question for question in result)
    assert any("지역" in question for question in result)
    assert not any("평균" in question for question in result)

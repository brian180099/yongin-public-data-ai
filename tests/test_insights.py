import pytest

from yongin_data.analysis.insights import grounded_insight


ROWS = [{"district": "기흥구", "youth": 85210, "elder": 76621},
        {"district": "수지구", "youth": 68070, "elder": 60154},
        {"district": "처인구", "youth": 55495, "elder": 55277}]


def test_model_chooses_comparison_but_server_calculates_gap():
    def model(_input, _instructions, schema, _name, _key, **_kwargs):
        assert schema["properties"]["metric"]["enum"] == ["youth", "elder"]
        return {"kind": "difference", "metric": "youth", "first": "기흥구", "second": "처인구"}

    insight = grounded_insight("청년 인구를 비교해줘", "population", ROWS, "test-key", model)
    assert "29,715명" in insight
    assert "기흥구" in insight and "처인구" in insight


def test_model_claimed_maximum_must_match_db():
    def model(*_args, **_kwargs):
        return {"kind": "largest", "metric": "elder", "first": "처인구", "second": None}

    with pytest.raises(ValueError, match="maximum"):
        grounded_insight("고령자 인구", "population", ROWS, "test-key", model)


def test_aggregate_insight_names_displayed_scope():
    rows = [{"category": "A", "count": 5}, {"category": "B", "count": 2}]

    def model(*_args, **_kwargs):
        return {"kind": "largest", "metric": "count", "first": "A", "second": None}

    insight = grounded_insight("분류별 비교", "group", rows, "test-key", model)
    assert "표시된 항목 중" in insight and "5건" in insight

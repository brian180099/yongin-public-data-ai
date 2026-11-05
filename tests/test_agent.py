from yongin_data.analysis.agent import _basic_count, _rule_plan, _validate, analyze


def test_refuses_sql_and_other_cities_without_db():
    assert analyze("DELETE FROM collector.datasets")["status"] == "unsupported"
    assert analyze("수원시 체육시설은 몇 건이야?")["status"] == "unsupported"


def test_validated_fields_are_required():
    selected = {"dataset_id": "example"}
    plan = {"dataset_id": "example", "operation": "count", "year": 2025,
            "date_field": "unverified", "month": None, "keyword": None,
            "filter_field": None, "filter_value": None, "group_field": None}
    assert "날짜" in _validate(plan, selected, {})
    plan.update(year=None, filter_field="district", filter_value="수지구")
    assert "검증" in _validate(plan, selected, {})


def test_followup_only_inherits_matching_dataset():
    selected = {"dataset_id": "forest"}
    columns = {"숲체험일정시작일": {"kind": "date", "format": "%Y-%m-%d"}}
    context = {"dataset_id": "other", "year": 2025, "keyword": "old"}
    plan = _rule_plan("월별로 다시", selected, columns, context)
    assert plan["year"] is None and plan["keyword"] is None


def test_rule_uses_only_verified_category_value():
    selected = {"dataset_id": "forest"}
    columns = {"숲체험일정제목": {"kind": "group", "values": ["체험형", "교육형"]}}
    plan = _rule_plan("체험형 숲체험일정은 몇 건이야?", selected, columns, None)
    assert plan["filter_field"] == "숲체험일정제목"
    assert plan["filter_value"] == "체험형"


def test_basic_count_does_not_discard_a_condition():
    selected = {"dataset_id": "portal_csv_123", "display_name": "경기도 용인시_새올민원 처리 현황"}
    assert _basic_count("새올민원 처리 현황은 몇 건이야?", selected)
    assert not _basic_count("2025년 새올민원 처리 현황은 몇 건이야?", selected)
    assert not _basic_count("기흥구 새올민원 처리 현황은 몇 건이야?", selected)

from yongin_data.analysis.agent import (_basic_count, _choose, _inherit_verified_context,
                                        _rule_plan, _validate, _validate_question_alignment, analyze)


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


def test_filter_field_without_value_is_rejected():
    selected = {"dataset_id": "example"}
    plan = {"dataset_id": "example", "operation": "count", "keyword": None,
            "year": None, "month": None, "date_field": None,
            "filter_field": "일정유형", "filter_value": None, "group_field": None}
    assert "함께" in _validate(plan, selected, {"일정유형": {"kind": "group", "values": ["행사"]}})


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


def test_quoted_search_text_is_not_an_implicit_category_filter():
    selected = {"dataset_id": "calendar", "display_name": "도서관 달력"}
    columns = {"대상": {"kind": "group", "values": ["유아", "성인"]}}
    plan = _rule_plan("도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?", selected, columns, None)
    assert plan["keyword"] == "유아 클레이 특강"
    assert plan["filter_field"] is None


def test_model_cannot_add_a_category_from_inside_quoted_search():
    selected = {"dataset_id": "calendar", "display_name": "도서관 달력"}
    plan = {"keyword": "유아 클레이 특강", "filter_field": "대상", "filter_value": "유아"}
    assert _validate_question_alignment(plan, "도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?",
                                        selected, None)
    plan.update(filter_field=None, filter_value=None)
    assert _validate_question_alignment(plan, "도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?",
                                        selected, None) is None


def test_model_cannot_turn_dataset_title_into_keyword():
    selected = {"dataset_id": "forest", "display_name": "경기도 용인시_숲체험일정"}
    plan = {"operation": "count", "keyword": "숲체험일정", "filter_field": None,
            "filter_value": None, "year": None, "month": None, "date_field": None, "group_field": None}
    assert _validate_question_alignment(plan, "숲체험일정은 몇 건이야?", selected, None)


def test_model_cannot_infer_month_from_digits_in_year():
    selected = {"dataset_id": "forest", "display_name": "숲체험일정"}
    plan = {"operation": "count", "keyword": None, "filter_field": None,
            "filter_value": None, "year": 2025, "month": 2,
            "date_field": "시작일", "group_field": None}
    assert "월" in _validate_question_alignment(plan, "2025년 숲체험일정은 몇 건이야?", selected, None)


def test_basic_count_does_not_discard_a_condition():
    selected = {"dataset_id": "portal_csv_123", "display_name": "경기도 용인시_새올민원 처리 현황"}
    assert _basic_count("새올민원 처리 현황은 몇 건이야?", selected)
    assert not _basic_count("2025년 새올민원 처리 현황은 몇 건이야?", selected)
    assert not _basic_count("기흥구 새올민원 처리 현황은 몇 건이야?", selected)


def test_candidate_selection_requires_matching_pending_question():
    catalog = [{"dataset_id": "one", "display_name": "도서관 달력"},
               {"dataset_id": "two", "display_name": "도서관 달력"}]
    chosen, tied = _choose("도서관 달력은 몇 건이야?", catalog,
                           {"selection_id": "two", "pending_question": "도서관 달력은 몇 건이야?"})
    assert chosen["dataset_id"] == "two" and not tied
    chosen, tied = _choose("다른 질문", catalog,
                           {"selection_id": "two", "pending_question": "도서관 달력은 몇 건이야?"})
    assert chosen is None and not tied


def test_followup_prefers_verified_context_over_incidental_title_words():
    catalog = [{"dataset_id": "forest", "display_name": "숲체험일정"},
               {"dataset_id": "monthly", "display_name": "월별로 다시 현황"}]
    chosen, tied = _choose("그중에서 월별로 다시", catalog, {"dataset_id": "forest"})
    assert chosen["dataset_id"] == "forest" and not tied


def test_followup_preserves_only_verified_filter_on_same_dataset():
    selected = {"dataset_id": "one"}
    columns = {"구분": {"kind": "group", "values": ["수지구", "기흥구"]}}
    context = {"dataset_id": "one", "filter_field": "구분", "filter_value": "수지구"}
    plan = {"dataset_id": "one", "operation": "group", "keyword": None,
            "year": None, "month": None, "date_field": None,
            "filter_field": None, "filter_value": None, "group_field": "구분"}
    inherited = _inherit_verified_context(plan, "그중에서 분류별로 다시", selected, columns, context)
    assert (inherited["filter_field"], inherited["filter_value"]) == ("구분", "수지구")
    assert _inherit_verified_context(plan, "분류별로", selected, columns, context) == plan
    assert _inherit_verified_context(plan, "그중에서", {"dataset_id": "other"}, columns, context) == plan

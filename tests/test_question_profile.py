from yongin_data.analysis.question_profile import llm_profile, presentation_for, rule_profile


def test_rule_profile_preserves_requested_answer_shape():
    profile = rule_profile("월별 결과를 선 차트로 자세히 보여줘")
    assert profile["goal"] == "trend"
    assert profile["output_format"] == "line_chart"
    assert profile["detail"] == "detailed"


def test_llm_profile_uses_strict_enums_without_data_access():
    captured = {}

    def model(question, instructions, schema, name, api_key, **kwargs):
        captured.update(question=question, instructions=instructions, schema=schema, name=name,
                        api_key=api_key, kwargs=kwargs)
        return {"goal": "compare", "output_format": "table", "detail": "normal",
                "semantic_summary": "구별 청년 인구를 표로 비교"}

    profile = llm_profile("청년 인구를 구별 표로 보여줘", "secret", model)
    assert profile["model_status"] == "completed"
    assert captured["schema"]["additionalProperties"] is False
    assert captured["schema"]["properties"]["output_format"]["enum"] == [
        "auto", "text", "table", "bar_chart", "line_chart"]
    assert "데이터셋" not in captured["question"]
    assert captured["kwargs"]["timeout_seconds"] == 10


def test_presentation_validates_chart_compatibility():
    presentation, limitation = presentation_for("population", {
        "output_format": "line_chart", "detail": "normal"})
    assert presentation["format"] == "bar_chart"
    assert "맞지 않아" in limitation
    presentation, limitation = presentation_for("monthly", {
        "output_format": "table", "detail": "concise"})
    assert presentation == {"requested": "table", "format": "table", "detail": "concise"}
    assert limitation is None

import httpx
import pytest

from yongin_data.analysis.client import AnalysisServiceError, ask_question


def test_ask_question_uses_existing_service_and_keeps_contract() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/ask"
        assert b"question" in request.read()
        return httpx.Response(200, json={
            "request_id": "test", "status": "ok", "intent": "count_summary",
            "answer": "105건", "filters": {"year": 2024}, "result": [{"count": 105}],
            "visualization": None, "sources": [], "calculation": {}, "limitations": [],
        })

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert ask_question("기흥구 2024년 행사 몇 건이야?", client=client)["result"][0]["count"] == 105


def test_ask_question_rejects_unexpected_response() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={}))) as client:
        with pytest.raises(AnalysisServiceError):
            ask_question("기흥구 행사 몇 건이야?", client=client)


def test_ask_question_reports_connection_failure_without_details() -> None:
    def fail(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("database secret must not be shown")

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(AnalysisServiceError) as exc:
            ask_question("기흥구 행사 몇 건이야?", client=client)
    assert "secret" not in str(exc.value)


def test_ask_question_preserves_database_error_status() -> None:
    payload = {
        "request_id": "test", "status": "error", "intent": "count_summary",
        "answer": "데이터베이스 조회에 실패했습니다.", "filters": {}, "result": [],
        "visualization": None, "sources": [], "calculation": None, "limitations": [],
    }
    with httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))) as client:
        assert ask_question("기흥구 행사 몇 건이야?", client=client)["status"] == "error"

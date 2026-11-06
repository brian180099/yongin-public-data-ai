from fastapi.testclient import TestClient

from yongin_data.analysis import api


def test_api_preserves_workflow_request_id(monkeypatch):
    monkeypatch.setattr(api, "analyze", lambda question, context=None: {
        "request_id": "generated", "status": "ok", "question": question, "context": context})
    response = TestClient(api.app).post("/v1/analyze", json={
        "request_id": "n8n-123", "question": "자료 목록", "context": {"dataset_id": "x"}, "channel": "web"})
    assert response.status_code == 200
    assert response.json()["request_id"] == "n8n-123"
    assert response.json()["channel"] == "web"


def test_api_allows_blank_question_for_structured_clarification(monkeypatch):
    monkeypatch.setattr(api, "analyze", lambda question, context=None: {
        "status": "clarification", "answer": "질문을 입력해 주세요."})
    response = TestClient(api.app).post("/v1/analyze", json={"question": "", "channel": "web"})
    assert response.status_code == 200
    assert response.json()["status"] == "clarification"

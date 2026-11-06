"""HTTP entry point for n8n forwarding and other clients."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from yongin_data.analysis.agent import analyze
from yongin_data.config import get_settings

app = FastAPI(title="Public Data Analysis Service")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=0, max_length=300)
    context: dict | None = None
    request_id: str | None = Field(default=None, max_length=80, pattern=r"^[A-Za-z0-9_.:-]+$")
    channel: str = Field(default="api", max_length=20, pattern=r"^[A-Za-z0-9_-]+$")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_enabled": bool(get_settings().openai_api_key),
            "capabilities": ["structured_question_understanding", "validated_query_plan",
                             "database_calculation", "grounded_result_interpretation"]}


@app.post("/v1/analyze")
def ask(request: QuestionRequest) -> dict:
    result = analyze(request.question, context=request.context)
    if request.request_id:
        result["request_id"] = request.request_id
    result["channel"] = request.channel
    return result

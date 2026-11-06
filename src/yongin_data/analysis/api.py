"""HTTP entry point for n8n forwarding and other clients."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from yongin_data.analysis.agent import analyze
from yongin_data.config import get_settings

app = FastAPI(title="Public Data Analysis Service")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    context: dict | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm_enabled": bool(get_settings().openai_api_key)}


@app.post("/v1/analyze")
def ask(request: QuestionRequest) -> dict:
    return analyze(request.question, context=request.context)

"""Structured understanding of a user's intent and requested answer shape."""

from __future__ import annotations

import re
from typing import Callable


GOALS = ("count", "search", "compare", "trend", "list", "inspect", "unknown")
FORMATS = ("auto", "text", "table", "bar_chart", "line_chart")
DETAILS = ("concise", "normal", "detailed")


def rule_profile(question: str) -> dict:
    if re.search(r"몇|건수|개수|총", question):
        goal = "count"
    elif re.search(r"비교|별로|분포|차이", question):
        goal = "compare"
    elif re.search(r"추세|변화|월별|연도별", question):
        goal = "trend"
    elif re.search(r"찾|검색|포함", question):
        goal = "search"
    elif re.search(r"목록|어떤 데이터", question):
        goal = "list"
    elif re.search(r"보여|원본", question):
        goal = "inspect"
    else:
        goal = "unknown"
    if re.search(r"표로|테이블", question):
        output_format = "table"
    elif re.search(r"선(?:형)?\s*차트|꺾은선|라인\s*차트", question):
        output_format = "line_chart"
    elif re.search(r"막대|바\s*차트", question):
        output_format = "bar_chart"
    elif re.search(r"차트|그래프|시각화", question):
        output_format = "auto"
    elif re.search(r"글로|텍스트|문장으로", question):
        output_format = "text"
    else:
        output_format = "auto"
    detail = "detailed" if re.search(r"자세히|상세히|근거.*설명", question) else "concise" if re.search(r"간단히|짧게|요약", question) else "normal"
    return {"goal": goal, "output_format": output_format, "detail": detail,
            "semantic_summary": question[:120], "model_status": "not_configured"}


def llm_profile(question: str, api_key: str, model_json: Callable[..., dict]) -> dict:
    schema = {"type": "object", "additionalProperties": False,
              "properties": {
                  "goal": {"type": "string", "enum": list(GOALS)},
                  "output_format": {"type": "string", "enum": list(FORMATS)},
                  "detail": {"type": "string", "enum": list(DETAILS)},
                  "semantic_summary": {"type": "string", "maxLength": 120}},
              "required": ["goal", "output_format", "detail", "semantic_summary"]}
    instructions = ("사용자 질문의 의미와 원하는 결과 형태만 구조화한다. 데이터셋·컬럼·숫자·SQL·답변은 만들지 않는다. "
                    "명시된 출력 형태가 없으면 output_format=auto, 설명 길이 요청이 없으면 detail=normal이다. "
                    "semantic_summary에는 사용자가 원하는 분석을 한국어 한 문장으로만 요약한다. 질문에 없는 조건을 추가하지 않는다.")
    profile = model_json(question, instructions, schema, "question_profile", api_key, timeout_seconds=10)
    if profile.get("goal") not in GOALS or profile.get("output_format") not in FORMATS or profile.get("detail") not in DETAILS:
        raise ValueError("invalid question profile")
    if not isinstance(profile.get("semantic_summary"), str) or not 1 <= len(profile["semantic_summary"]) <= 120:
        raise ValueError("invalid semantic summary")
    profile["model_status"] = "completed"
    return profile


def presentation_for(intent: str, profile: dict) -> tuple[dict, str | None]:
    requested = profile.get("output_format", "auto")
    allowed = {
        "count": {"auto", "text", "table"}, "overview": {"auto", "text", "table"},
        "records": {"auto", "table", "text"}, "catalog": {"auto", "table"},
        "monthly": set(FORMATS), "yearly": set(FORMATS),
        "group": {"auto", "text", "table", "bar_chart"},
        "population": {"auto", "text", "table", "bar_chart"},
    }.get(intent, {"auto", "text"})
    limitation = None
    if requested not in allowed:
        effective = "bar_chart" if intent in {"group", "population"} else "table"
        limitation = f"요청한 {requested} 형식은 이 분석에 맞지 않아 {effective} 형식으로 표시했습니다."
    elif requested == "auto":
        effective = ("line_chart" if intent in {"monthly", "yearly"} else
                     "bar_chart" if intent in {"group", "population"} else
                     "table" if intent in {"records", "catalog"} else "text")
    else:
        effective = requested
    return {"requested": requested, "format": effective, "detail": profile.get("detail", "normal")}, limitation

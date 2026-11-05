"""Streamlit conversation over the single n8n → analysis-agent path."""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

from yongin_data.config import get_settings


WEBHOOK = os.getenv("YONGIN_ANALYSIS_WEBHOOK_URL", "http://n8n:5678/webhook/yongin-analysis-v1")
EXAMPLES = (
    "숲체험일정은 몇 건이야?",
    "도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?",
    "어떤 데이터가 있어?",
)
FILTER_LABELS = {"keyword": "검색어", "year": "연도", "month": "월", "date_field": "날짜 기준",
                 "filter_field": "조건 컬럼", "filter_value": "조건 값", "group_field": "비교 기준"}
OP_LABELS = {"count": "조건에 맞는 행 수", "records": "원본 행 조회", "monthly": "월별 건수",
             "yearly": "연도별 건수", "group": "그룹별 건수"}


def ask(question: str, context: dict | None) -> dict:
    try:
        response = requests.post(WEBHOOK, json={"question": question, "context": context}, timeout=35)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict) or data.get("status") not in {"ok", "clarification", "unsupported", "error"}:
            raise ValueError("invalid webhook response")
        return data
    except (requests.RequestException, ValueError):
        return {"status": "error", "answer": "질문 전달 경로에 연결하지 못했습니다. n8n과 분석 서비스 상태를 확인해 주세요.",
                "result": [], "sources": [], "calculation": None, "filters": {}, "interpreter": "rules",
                "model_status": "not_used", "context": None, "intent": "unknown", "limitations": []}


st.set_page_config(page_title="용인시 공공데이터 질문 분석", layout="wide")
st.title("용인시 공공데이터 질문 분석")
st.caption("검증된 적재 자료를 읽기 전용으로 조회합니다. 등록 현황은 실제 운영·예약 가능 상태를 뜻하지 않습니다.")
if get_settings().openai_api_key:
    st.info("OpenAI 키가 설정되어 있습니다. 답변마다 실제 모델 사용 여부를 표시합니다.")
else:
    st.info("OpenAI 키가 설정되지 않아 기본 질문은 규칙 기반으로 처리합니다.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = None

with st.sidebar:
    st.header("질문 시작하기")
    st.caption("자료명이나 조건을 적어 주세요. 모호하면 후보 자료를 선택할 수 있습니다.")
    example_clicked = None
    for example_index, example in enumerate(EXAMPLES):
        if st.button(example, key=f"example-{example_index}", use_container_width=True):
            example_clicked = example
    st.divider()
    st.caption("질문 → n8n → 분석 에이전트 → 로컬 PostgreSQL 읽기 뷰")
    if st.button("대화 지우기", use_container_width=True):
        st.session_state.messages = []
        st.session_state.context = None
        st.rerun()

chosen_question = None
chosen_context = None
chosen_label = None
for index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
            continue
        status = message.get("status")
        if status == "error":
            st.error(message["content"])
        elif status == "unsupported":
            st.warning(message["content"])
        else:
            st.write(message["content"])

        model_status = message.get("model_status")
        if message.get("interpreter") == "llm":
            st.caption("질문 해석: OpenAI 구조화 계획 · 서버 검증 완료")
        elif model_status == "failed":
            st.caption("OpenAI 호출 실패 · 규칙 기반 결과 또는 자료 선택 안내")
        elif model_status == "rejected":
            st.caption("모델 계획이 허용 조건과 맞지 않아 규칙 기반으로 처리")
        else:
            st.caption("질문 해석: 규칙 기반")

        rows = message.get("result") or []
        if status == "clarification" and rows and all("dataset_id" in row for row in rows):
            st.caption("아래 후보 중 사용할 자료를 선택하세요.")
            for row in rows[:5]:
                if st.button(row["dataset_name"], key=f"pick-{index}-{row['dataset_id']}"):
                    chosen_question = message["question"]
                    chosen_context = {"selection_id": row["dataset_id"], "pending_question": chosen_question}
                    chosen_label = f"자료 선택: {row['dataset_name']}"
        elif rows:
            if message.get("intent") == "count":
                st.metric("조건에 맞는 적재 행", f"{rows[0]['count']:,}건")
            else:
                frame = pd.DataFrame(rows)
                if message.get("intent") in {"monthly", "yearly", "group"} and "count" in frame:
                    label = "period" if "period" in frame else "category"
                    if label in frame:
                        st.bar_chart(frame.set_index(label)["count"])
                if message.get("intent") == "catalog":
                    term = st.text_input("자료 목록에서 찾기", key=f"catalog-filter-{index}")
                    if term:
                        frame = frame[frame["dataset_name"].str.contains(term, case=False, regex=False)]
                st.dataframe(frame, hide_index=True, use_container_width=True, height=340)

        filters = message.get("filters") or {}
        if filters:
            st.caption("적용 조건: " + " · ".join(f"{FILTER_LABELS.get(k, k)} {v}" for k, v in filters.items()
                                               if k != "operation" and v is not None))
        calculation = message.get("calculation")
        if calculation:
            st.caption("계산: " + OP_LABELS.get(calculation.get("method"), calculation.get("method", "조회")))
        for source in message.get("sources") or []:
            st.caption(f"자료: {source['dataset_name']} · 제공기관: {source['provider']}")
            st.caption(f"데이터 기준일: {source['reference_date'] or '미확인'} · 수집일: {source['collected_at'] or '미확인'}")
            if source.get("url"):
                st.link_button("공식 공공데이터포털 원본", source["url"])
        for limitation in message.get("limitations") or []:
            st.caption("※ " + limitation)

question = st.chat_input("예: 숲체험일정은 몇 건이야?", max_chars=300)
question_to_send = chosen_question or example_clicked or question
if question_to_send:
    with st.spinner("질문을 분석하고 검증된 자료를 조회하고 있습니다"):
        data = ask(question_to_send, chosen_context if chosen_question else st.session_state.context)
    st.session_state.messages.extend([
        {"role": "user", "content": chosen_label or question_to_send},
        {"role": "assistant", "content": data.get("answer", "답변을 생성하지 못했습니다."),
         "question": question_to_send, "status": data["status"], "intent": data.get("intent"),
         "result": data.get("result", []), "sources": data.get("sources", []),
         "calculation": data.get("calculation"), "filters": data.get("filters", {}),
         "interpreter": data.get("interpreter", "rules"), "model_status": data.get("model_status"),
         "limitations": data.get("limitations", [])},
    ])
    st.session_state.messages = st.session_state.messages[-20:]
    st.session_state.context = data.get("context") if data["status"] == "ok" else None
    st.rerun()

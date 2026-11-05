"""Streamlit conversation over the single n8n → analysis-agent path."""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

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
        return {"status": "error", "answer": "답변을 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.",
                "result": [], "sources": [], "calculation": None, "filters": {}, "interpreter": "rules",
                "model_status": "not_used", "context": None, "intent": "unknown", "limitations": []}


st.set_page_config(page_title="용인시 공공데이터", page_icon="🔎", layout="wide")
st.title("용인시 공공데이터")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = None

with st.sidebar:
    st.subheader("예시 질문")
    example_clicked = None
    for example_index, example in enumerate(EXAMPLES):
        if st.button(example, key=f"example-{example_index}", use_container_width=True):
            example_clicked = example
    st.divider()
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
        elif message.get("intent") != "count":
            st.write(message["content"])

        rows = message.get("result") or []
        if status == "clarification" and rows and all("dataset_id" in row for row in rows):
            st.caption("사용할 자료를 선택해 주세요.")
            for row in rows[:5]:
                if st.button(row["dataset_name"], key=f"pick-{index}-{row['dataset_id']}"):
                    chosen_question = message["question"]
                    chosen_context = {"selection_id": row["dataset_id"], "pending_question": chosen_question}
                    chosen_label = f"자료 선택: {row['dataset_name']}"
        elif rows:
            if message.get("intent") == "count":
                st.metric("검색 결과", f"{rows[0]['count']:,}건")
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
        sources = message.get("sources") or []
        calculation = message.get("calculation")
        limitations = message.get("limitations") or []
        if filters or sources or calculation or limitations:
            with st.expander("출처 및 조회 기준"):
                if filters:
                    st.write(" · ".join(f"{FILTER_LABELS.get(k, k)}: {v}" for k, v in filters.items()
                                        if k != "operation" and v is not None))
                if calculation:
                    st.write(OP_LABELS.get(calculation.get("method"), calculation.get("method", "조회")))
                for source in sources:
                    st.write(source["dataset_name"])
                    st.caption(f"{source['provider']} · 기준일 {source['reference_date'] or '미확인'} · 수집일 {source['collected_at'] or '미확인'}")
                    if source.get("url"):
                        st.link_button("공식 원본 보기", source["url"])
                for limitation in limitations:
                    st.caption(limitation)

question = st.chat_input("궁금한 내용을 입력해 주세요", max_chars=300)
question_to_send = chosen_question or example_clicked or question
if question_to_send:
    with st.spinner("자료를 찾고 있어요"):
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

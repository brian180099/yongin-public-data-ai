"""Streamlit conversation over the single n8n → analysis-agent path."""

from __future__ import annotations

import os

import pandas as pd
import requests
import streamlit as st

WEBHOOK = os.getenv("YONGIN_ANALYSIS_WEBHOOK_URL", "http://n8n:5678/webhook/yongin-question-agent-v1")
EXAMPLES = (
    "숲체험일정은 몇 건이야?",
    "도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?",
    "용인시 인구 분포 분석해줘",
    "어떤 데이터가 있어?",
)
FILTER_LABELS = {"keyword": "검색어", "year": "연도", "month": "월", "date_field": "날짜 기준",
                 "filter_field": "조건 컬럼", "filter_value": "조건 값", "group_field": "비교 기준",
                 "data_date": "자료 기준일", "sex": "성별", "metric": "인구 항목", "district": "지역"}
OP_LABELS = {"overview": "자료 개요", "count": "조건에 맞는 행 수", "records": "원본 행 조회", "monthly": "월별 건수",
             "yearly": "연도별 건수", "group": "그룹별 건수", "population_sum": "행정동 인구 수를 구별로 합산"}
POPULATION_LABELS = {"infant": "영유아 0~5세", "school": "학령아동 6~17세", "youth": "청년 19~34세",
                     "middle": "신중년 51~64세", "elder": "고령자 65세 이상", "working": "생산가능인구 15~64세"}


def record_frame(rows: list[dict]) -> pd.DataFrame:
    """Show CSV fields as columns instead of a JSON payload cell."""
    payloads = [row.get("payload", {}) for row in rows]
    frame = pd.json_normalize(payloads, sep=" · ")
    if frame.empty:
        return frame
    return frame.map(lambda value: str(value)[:160] + "…" if len(str(value)) > 160 else value)


def result_chart(rows: list[dict], intent: str) -> None:
    frame = pd.DataFrame(rows)
    if frame.empty or "count" not in frame:
        return
    key = "period" if intent in {"monthly", "yearly"} else "category"
    if key not in frame:
        return
    frame[key] = frame[key].astype(str).str[:10]
    st.bar_chart(frame.set_index(key)["count"], height=300)
    with st.expander("집계표 보기"):
        frame = frame.rename(columns={key: "기간" if key == "period" else "분류", "count": "건수"})
        st.dataframe(frame, hide_index=True, width="stretch")


def population_chart(rows: list[dict], visualization: dict, filters: dict) -> None:
    frame = pd.DataFrame(rows).set_index("district")
    if "count" in frame:
        title = filters.get("metric", "인구")
        st.bar_chart(frame.rename(columns={"count": f"{title} (명)"}), height=310)
        table = frame.rename_axis("구").rename(columns={"count": "인구 수 (명)"})
    else:
        labelled = frame.rename(columns=POPULATION_LABELS)
        st.bar_chart(labelled[["청년 19~34세", "고령자 65세 이상"]], height=310)
        table = labelled.rename_axis("구")
    with st.expander("구별 인구 수 보기"):
        st.dataframe(table.style.format("{:,.0f}"), width="stretch")


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


st.set_page_config(page_title="공공데이터 분석 서비스", page_icon="🔎", layout="wide")
st.title("공공데이터 분석 서비스")
st.caption("현재 분석 가능 지역: 용인시")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = None

with st.sidebar:
    st.subheader("예시 질문")
    example_clicked = None
    for example_index, example in enumerate(EXAMPLES):
        if st.button(example, key=f"example-{example_index}", width="stretch"):
            example_clicked = example
    st.divider()
    if st.button("대화 지우기", width="stretch"):
        st.session_state.messages = []
        st.session_state.context = None
        st.rerun()

chosen_question = None
chosen_context = None
chosen_label = None
suggested_question = None
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
            st.markdown(message["content"])

        rows = message.get("result") or []
        if status == "clarification" and rows and all("dataset_id" in row for row in rows):
            st.caption("사용할 자료를 선택해 주세요.")
            for row in rows[:5]:
                if st.button(row["dataset_name"], key=f"pick-{index}-{row['dataset_id']}"):
                    chosen_question = message["question"]
                    chosen_context = {"selection_id": row["dataset_id"], "pending_question": chosen_question}
                    chosen_label = f"자료 선택: {row['dataset_name']}"
        elif rows:
            intent = message.get("intent")
            if intent in {"count", "overview"}:
                st.metric("기록 수", f"{rows[0]['count']:,}건")
            elif intent in {"monthly", "yearly", "group"}:
                result_chart(rows, intent)
            elif intent == "population":
                population_chart(rows, message.get("visualization") or {}, message.get("filters") or {})
            elif intent == "records":
                frame = record_frame(rows)
                if not frame.empty:
                    st.dataframe(frame, hide_index=True, width="stretch", height=min(520, 75 + len(frame) * 35))
            elif intent == "catalog":
                frame = pd.DataFrame(rows)
                term = st.text_input("자료 검색", key=f"catalog-filter-{index}")
                if term:
                    frame = frame[frame["dataset_name"].str.contains(term, case=False, regex=False)]
                st.caption(f"{len(frame):,}개 자료")
                st.dataframe(frame.rename(columns={"dataset_name": "자료명", "dataset_id": "자료 ID"}),
                             hide_index=True, width="stretch", height=390)

        if message.get("insight_status") == "completed" and message.get("insight"):
            st.markdown(f"**AI 분석** · {message['insight']}")
        elif message.get("intent") in {"population", "monthly", "yearly", "group"} and message.get("insight_status") in {
                "failed", "rejected", "not_configured"}:
            st.caption("AI 해석 없이 DB 계산 결과를 표시했습니다.")

        if status == "ok" and message.get("suggested_questions"):
            with st.container():
                for suggestion_index, suggestion in enumerate(message["suggested_questions"]):
                    if st.button(suggestion, key=f"suggest-{index}-{suggestion_index}"):
                        suggested_question = suggestion

        filters = message.get("filters") or {}
        sources = message.get("sources") or []
        calculation = message.get("calculation")
        limitations = message.get("limitations") or []
        if message.get("intent") == "population" and limitations:
            st.caption(limitations[0])
        if filters or sources or calculation or limitations:
            with st.expander("출처 및 조회 기준"):
                if filters:
                    st.write(" · ".join(f"{FILTER_LABELS.get(k, k)}: {v}" for k, v in filters.items()
                                        if k != "operation" and v is not None))
                if calculation:
                    st.write(OP_LABELS.get(calculation.get("method"), calculation.get("method", "조회")))
                for source in sources:
                    st.write(source["dataset_name"])
                    location = "Supabase" if source.get("database") == "supabase" else "로컬 DB"
                    st.caption(f"{source['provider']} · {location} · 기준일 {source['reference_date'] or '미확인'} · 수집일 {source['collected_at'] or '미확인'}")
                    if source.get("url"):
                        st.link_button("공식 원본 보기", source["url"])
                for limitation in limitations:
                    st.caption(limitation)

question = st.chat_input("궁금한 내용을 입력해 주세요", max_chars=300)
question_to_send = chosen_question or suggested_question or example_clicked or question
if question_to_send:
    with st.spinner("자료를 찾고 있어요"):
        data = ask(question_to_send, chosen_context if chosen_question else st.session_state.context)
    st.session_state.messages.extend([
        {"role": "user", "content": chosen_label or question_to_send},
        {"role": "assistant", "content": data.get("answer", "답변을 생성하지 못했습니다."),
         "question": question_to_send, "status": data["status"], "intent": data.get("intent"),
         "result": data.get("result", []), "sources": data.get("sources", []),
         "visualization": data.get("visualization"),
         "calculation": data.get("calculation"), "filters": data.get("filters", {}),
         "interpreter": data.get("interpreter", "rules"), "model_status": data.get("model_status"),
         "insight": data.get("insight"), "insight_status": data.get("insight_status", "not_used"),
         "suggested_questions": data.get("suggested_questions", []),
         "limitations": data.get("limitations", [])},
    ])
    st.session_state.messages = st.session_state.messages[-20:]
    st.session_state.context = data.get("context") if data["status"] == "ok" else None
    st.rerun()

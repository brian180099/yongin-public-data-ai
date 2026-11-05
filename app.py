"""Streamlit chat for the single Yongin analysis engine."""

import os

import pandas as pd
import requests
import streamlit as st

from yongin_data.config import get_settings


st.set_page_config(page_title="용인 공공데이터 질문", layout="wide")
st.title("용인시 공공데이터 질문 분석")
st.caption("검증된 적재 자료를 읽기 전용으로 조회합니다. 등록 현황은 실제 운영·예약 가능 상태를 뜻하지 않습니다.")
st.info("OpenAI 키 설정됨 · 각 답변에서 실제 해석 방식을 확인하세요 (모델 호출 미검증)" if get_settings().openai_api_key else
        "질문 해석: 제한된 규칙 기반 (OpenAI 키 미설정, 실제 모델 호출 미검증)")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "context" not in st.session_state:
    st.session_state.context = None

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])
        if message.get("interpreter"):
            st.caption("질문 해석: " + ("OpenAI 구조화 계획" if message["interpreter"] == "llm" else "규칙 기반"))
        if message.get("result"):
            st.dataframe(pd.DataFrame(message["result"]), hide_index=True, width="stretch")
        for source in message.get("sources", []):
            st.caption(f"{source['dataset_name']} · {source['provider']} · 기준일 {source['reference_date'] or '미확인'} · 수집일 {source['collected_at'] or '미확인'}")
            if source.get("url"):
                st.link_button("공식 포털", source["url"])
        if message.get("calculation"):
            st.caption(f"계산: {message['calculation']['measure']} / {message['calculation']['method']} · 조건: {message.get('filters', {})}")

if question := st.chat_input("예: 숲체험일정은 몇 건이야?", max_chars=300):
    with st.spinner("읽기 전용 자료를 조회하고 있습니다"):
        try:
            response = requests.post(
                os.getenv("YONGIN_ANALYSIS_WEBHOOK_URL", "http://n8n:5678/webhook/yongin-analysis-v1"),
                json={"question": question, "context": st.session_state.context},
                timeout=35,
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict) or data.get("status") not in {"ok", "clarification", "unsupported", "error"}:
                raise ValueError("Webhook 응답 형식 오류")
        except (requests.RequestException, ValueError):
            data = {"status": "error", "answer": "질문 전달 경로에 연결하지 못했습니다. n8n과 분석 서비스 상태를 확인해 주세요.",
                    "result": [], "sources": [], "calculation": None, "filters": {}, "interpreter": "rules", "context": None}
    st.session_state.messages.append({"role": "user", "content": question})
    st.session_state.messages.append({"role": "assistant", "content": data["answer"],
                                      "result": data["result"], "sources": data["sources"],
                                      "calculation": data["calculation"], "filters": data["filters"],
                                      "interpreter": data["interpreter"]})
    st.session_state.context = data["context"] if data["status"] == "ok" and data["context"] else None
    st.rerun()

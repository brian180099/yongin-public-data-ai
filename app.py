"""Streamlit question screen for the verified Yongin analysis workflow."""

import pandas as pd
import streamlit as st

from yongin_data.analysis.client import AnalysisServiceError, ask_question
from yongin_data.config import configure_logging


configure_logging()
st.set_page_config(page_title="용인 생활여가 데이터 질문", page_icon="📍", layout="wide")
st.title("용인 생활여가 공공데이터 질문")
st.caption("운영 DB에 적재된 기흥구 행사 데이터의 시작일 기준 건수를 조회합니다.")
st.info("현재 조회 가능: 기흥구 행사 건수와 연도별·월별 건수. 시설과 다른 구의 자료는 아직 적재되지 않았습니다.")

examples = [
    "기흥구 행사 전체 몇 건이야?",
    "기흥구 2024년 행사 몇 건이야?",
    "기흥구 2024년 월별 행사 수를 보여줘",
]
example = st.selectbox("대표 질문", ["직접 입력", *examples])
with st.form("question_form"):
    question = st.text_input("질문", value="" if example == "직접 입력" else example,
                             max_chars=300, placeholder=examples[0], key=f"question_{example}")
    submitted = st.form_submit_button("질문하기")

if submitted:
    try:
        with st.spinner("실제 데이터를 조회하고 있습니다…"):
            data = ask_question(question)
    except ValueError as exc:
        st.warning(str(exc))
    except AnalysisServiceError as exc:
        st.error(str(exc))
    else:
        status = data["status"]
        if status == "ok":
            st.success(data["answer"])
        elif status == "empty":
            st.info(data["answer"])
        elif status == "clarification":
            st.warning(data["answer"])
        elif status == "unsupported":
            st.info(data["answer"])
        else:
            st.error(data["answer"])

        if status in {"ok", "empty"}:
            rows = data["result"][:12]
            if rows:
                st.subheader("조회 결과")
                frame = pd.DataFrame(rows)
                st.dataframe(frame, hide_index=True, width="stretch")
                if data["visualization"] and data["visualization"].get("type") == "bar" and {"month", "count"}.issubset(frame.columns):
                    st.subheader("월별 행사 수")
                    st.bar_chart(frame.set_index("month")["count"], x_label="시작 월", y_label="행사 수")

        calculation = data["calculation"]
        if calculation:
            st.subheader("계산 기준")
            st.write(f"{calculation.get('measure', '확인하지 못함')} · {calculation.get('region', '확인하지 못함')} · 날짜 필드: {calculation.get('date_field', '확인하지 못함')}")
            st.write(f"조건: 연도 {data['filters'].get('year') or '전체'}, 월 {data['filters'].get('month') or '전체'}")
            st.caption(calculation.get("null_handling", ""))

        if data["sources"]:
            st.subheader("출처와 날짜")
            for source in data["sources"]:
                st.write(f"{source.get('dataset_name', '확인하지 못함')} · {source.get('provider', '확인하지 못함')} (ID: {source.get('dataset_id', '확인하지 못함')})")
                st.write(f"원본 기준일: {source.get('reference_date') or '확인하지 못함'} · 수집일: {source.get('collected_at') or '확인하지 못함'} · 마지막 정상 갱신: {source.get('last_success_at') or '확인하지 못함'}")
                if source.get("url"):
                    st.link_button("공식 원본 보기", source["url"])

        if data["limitations"]:
            st.subheader("해석 한계")
            for limitation in data["limitations"]:
                st.write(f"- {limitation}")
        st.caption(f"요청 ID: {data['request_id']} · 상태: {status} · 의도: {data['intent']}")

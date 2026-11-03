"""Streamlit entry point for the Yongin public-data MVP."""

import streamlit as st

from yongin_data.config import configure_logging, get_settings


configure_logging()
settings = get_settings()

st.set_page_config(
    page_title="용인 생활여가 공공데이터 AI",
    page_icon="📍",
    layout="wide",
)

st.title("용인 생활여가 공공데이터 AI 분석 서비스")
st.caption("실제 공공데이터 조회·결합·계산 결과와 출처를 제공하는 MVP")

st.info("데이터 상태: 아직 수집되지 않음", icon="ℹ️")

left, right = st.columns(2)
with left:
    st.subheader("프로젝트 목적")
    st.write(
        "용인시 생활여가·문화·체육 데이터를 작게 시작해 신뢰할 수 있게 "
        "수집하고, 자연어 질문에 검증 가능한 결과를 제공합니다."
    )

with right:
    st.subheader("준비 중인 기능")
    st.markdown(
        "- 시설·프로그램 검색\n"
        "- 지역·분류별 비교\n"
        "- 데이터 결합 및 근거가 있는 요약"
    )

st.subheader("연결 상태")
st.write(f"- PostgreSQL: {'설정됨(연결 미검증)' if settings.database_url else '미설정'}")
st.write(f"- 공공데이터 API 키: {'설정됨' if settings.data_go_kr_service_key else '미설정'}")
st.write(f"- OpenAI API 키: {'설정됨' if settings.openai_api_key else '미설정(초기 화면 실행 가능)'}")

st.warning(
    "현재 화면은 초기 골격이며 실제 검색·분석 결과를 제공하지 않습니다. "
    "데이터 수집과 검증이 끝난 기능만 순차적으로 활성화합니다."
)

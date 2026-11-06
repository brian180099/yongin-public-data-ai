"""Verified person-count analysis for Yongin's 39 administrative-dong CSV."""

from __future__ import annotations

import re
from collections import Counter, defaultdict


DATASET_ID = "portal_csv_15135861"
DISTRICTS = ("기흥구", "수지구", "처인구")
AGE_BANDS = {
    "infant": ("영유아", "영유아(0-5세)"),
    "school": ("학령아동", "학령아동(6-17세)"),
    "youth": ("청년", "청년(19-34세)"),
    "middle": ("신중년", "신중년(51-64세)"),
    "elder": ("고령자", "고령자(65세이상)"),
    "working": ("생산가능인구", "생산가능인구(15-64세)"),
}
PARTIAL_AGE_NOTE = "연령 구간 일부가 겹치고 18세·35~50세 구간이 없어 표시된 연령대의 합은 전체 인구가 아닙니다."


class PopulationContractError(ValueError):
    pass


def requested_metric(question: str) -> str | None:
    names = {key: label for key, (label, _) in AGE_BANDS.items() if label in question}
    if "65세" in question or "노인" in question:
        names["elder"] = "고령자"
    return next(iter(names)) if len(names) == 1 else None


def wants_population(question: str) -> bool:
    return bool(re.search(r"인구|고령자|노인|청년|영유아|학령아동|신중년", question)) and not bool(
        re.search(r"몇\s*건|건수|원본|행\s*보여", question))


def summarize(cur, question: str, reference_date: str | None) -> dict:
    """Read a bounded snapshot and validate every numeric field before summing."""
    if re.search(r"전체\s*인구|총\s*인구|총인구", question) or (
            re.search(r"몇\s*명|인구는", question) and requested_metric(question) is None):
        raise PopulationContractError("이 자료에는 전체 인구 컬럼이 없어 전체 인구 수를 계산할 수 없습니다.")
    if re.search(r"비율|대비|점유율|퍼센트|%|성별|남녀", question) or ("남성" in question and "여성" in question):
        raise PopulationContractError("비율 또는 남녀 비교는 분모·비교 기준을 먼저 검증해야 하므로 이 자료에서 지원하지 않습니다.")
    if re.search(r"추세|증감|변화|연도별|월별|평균|예측", question):
        raise PopulationContractError("이 자료는 단일 기준일의 행정동별 인구 자료라 시계열·예측 분석을 할 수 없습니다.")
    if re.search(r"행정동별|동별", question):
        raise PopulationContractError("현재 인구 시각화는 구별 합계만 지원합니다. 행정동별 비교는 아직 지원하지 않습니다.")
    if "합계" in question and requested_metric(question) is None:
        raise PopulationContractError("서로 겹치는 연령대의 합계를 전체 인구로 계산할 수 없습니다. 연령대를 하나 지정해 주세요.")
    if re.search(r"(?<!\d)20\d{2}년", question) and reference_date:
        asked_year = re.search(r"(?<!\d)(20\d{2})년", question).group(1)
        if asked_year != reference_date[:4]:
            raise PopulationContractError(f"이 자료의 기준일은 {reference_date}입니다. 요청한 연도의 인구로 답할 수 없습니다.")
    cur.execute("select payload from analytics.current_dataset_records where dataset_id=%s order by record_key limit 501",
                [DATASET_ID])
    records = [row["payload"] for row in cur.fetchall()]
    if not records or len(records) > 500:
        raise PopulationContractError("분석할 자료의 행 수를 안전하게 확인할 수 없습니다.")
    date_set, seen = set(), set()
    totals = defaultdict(lambda: defaultdict(Counter))
    for payload in records:
        try:
            district = payload["시군구명"].split()[-1]
            dong = payload["행정동명"]
            date = payload["데이터기준일자"]
            if district not in DISTRICTS or not dong or (district, dong) in seen:
                raise PopulationContractError("행정동·구 이름의 중복 또는 누락이 있습니다.")
            seen.add((district, dong))
            date_set.add(date)
            for key, (_, field) in AGE_BANDS.items():
                values = {}
                for sex, prefix in (("total", "전체 "), ("male", "남성 "), ("female", "여성 ")):
                    raw = payload[prefix + field]
                    if not isinstance(raw, str) or not re.fullmatch(r"\d+", raw):
                        raise PopulationContractError("인구 컬럼에 검증되지 않은 값이 있습니다.")
                    values[sex] = int(raw)
                if values["male"] + values["female"] != values["total"]:
                    raise PopulationContractError("성별 인구 합계가 전체 인구 값과 다릅니다.")
                for sex, value in values.items():
                    totals[district][sex][key] += value
        except (KeyError, AttributeError, TypeError) as exc:
            raise PopulationContractError("필수 인구 컬럼이나 지역 값이 누락됐습니다.") from exc
    if len(date_set) != 1 or (reference_date and next(iter(date_set)) != reference_date):
        raise PopulationContractError("자료 안의 기준일이 일치하지 않아 합산할 수 없습니다.")
    if set(totals) != set(DISTRICTS):
        raise PopulationContractError("세 개 구의 자료가 모두 없어 용인시 분포를 계산할 수 없습니다.")
    metric = requested_metric(question)
    sex = "male" if "남성" in question and "여성" not in question else "female" if "여성" in question and "남성" not in question else "total"
    districts = [district for district in DISTRICTS if district in question] or list(DISTRICTS)
    sex_label = {"male": "남성 ", "female": "여성 ", "total": ""}[sex]
    if metric:
        label = AGE_BANDS[metric][0]
        rows = [{"district": district, "count": totals[district][sex][metric]} for district in districts]
        total = sum(row["count"] for row in rows)
        top = max(rows, key=lambda row: row["count"])
        answer = (f"**{reference_date} 기준 {sex_label}{label} 인구**는 "
                  f"{('용인시 3개 구 합계' if len(districts) == 3 else districts[0])} **{total:,}명**입니다. "
                  f"가장 많은 지역은 **{top['district']} {top['count']:,}명**입니다.")
        metrics = [metric]
    else:
        metrics = ["infant", "school", "youth", "middle", "elder", "working"]
        rows = [{"district": district, **{key: totals[district][sex][key] for key in metrics}}
                for district in districts]
        youth = sum(row["youth"] for row in rows)
        elder = sum(row["elder"] for row in rows)
        answer = (f"**{reference_date} 기준 용인시 행정동별 인구 자료**를 구별로 합산했습니다. "
                  f"{sex_label}청년(19~34세) **{youth:,}명**, {sex_label}고령자(65세 이상) **{elder:,}명**입니다. "
                  "아래 차트는 두 연령대의 구별 규모를 비교합니다.")
    return {"answer": answer, "result": rows, "visualization": {"type": "population", "metrics": metrics,
            "sex": sex, "unit": "명"}, "filters": {"data_date": reference_date, "sex": sex_label.strip() or "전체",
            "metric": AGE_BANDS[metric][0] if metric else "연령대별", "district": districts[0] if len(districts) == 1 else "3개 구"},
            "calculation": {"measure": "검증된 인구 수치 합계", "method": "population_sum",
                            "group_field": "시군구명", "row_count": len(records)},
            "limitations": [PARTIAL_AGE_NOTE],
            "suggested_questions": ["용인시 청년 인구를 구별로 비교해줘", "용인시 고령자 인구를 구별로 비교해줘"]}

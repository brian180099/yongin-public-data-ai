from copy import deepcopy

import pytest

from yongin_data.analysis.population import (AGE_BANDS, DATASET_ID, PopulationContractError,
                                            summarize)


class Cursor:
    def __init__(self, payloads):
        self.payloads = payloads
        self.params = None

    def execute(self, sql, params):
        assert "analytics.current_dataset_records" in sql
        assert "limit 501" in sql
        self.params = params

    def fetchall(self):
        assert self.params == [DATASET_ID]
        return [{"payload": payload} for payload in self.payloads]


def sample(district="기흥구", dong="기흥동"):
    payload = {"시군구명": f"경기도 용인시 {district}", "행정동명": dong,
               "데이터기준일자": "2026-09-08"}
    for _, field in AGE_BANDS.values():
        payload["남성 " + field] = "2"
        payload["여성 " + field] = "3"
        payload["전체 " + field] = "5"
    return payload


def test_population_sums_people_not_csv_rows():
    rows = [sample(), sample("수지구", "죽전동"), sample("처인구", "역북동")]
    result = summarize(Cursor(rows), "용인시 청년 인구를 구별로 비교해줘", "2026-09-08")
    assert result["result"] == [{"district": "기흥구", "count": 5}, {"district": "수지구", "count": 5},
                                {"district": "처인구", "count": 5}]
    assert result["calculation"]["measure"] == "검증된 인구 수치 합계"


def test_population_rejects_inconsistent_sex_totals():
    bad = deepcopy(sample())
    bad["전체 청년(19-34세)"] = "9"
    with pytest.raises(PopulationContractError, match="성별"):
        summarize(Cursor([bad]), "청년 인구 구별", "2026-09-08")


def test_population_rejects_mixed_dates_and_total_population():
    second = sample("수지구", "죽전동")
    second["데이터기준일자"] = "2025-09-08"
    with pytest.raises(PopulationContractError, match="기준일"):
        summarize(Cursor([sample(), second]), "용인시 인구 분포", "2026-09-08")
    with pytest.raises(PopulationContractError, match="전체 인구"):
        summarize(Cursor([sample()]), "용인시 전체 인구는 몇 명이야?", "2026-09-08")


def test_population_rejects_unimplemented_granularity():
    with pytest.raises(PopulationContractError, match="행정동별"):
        summarize(Cursor([sample()]), "행정동별 청년 인구 비교해줘", "2026-09-08")

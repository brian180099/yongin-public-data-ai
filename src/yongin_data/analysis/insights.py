"""Let the model choose an interpretation; verify it against DB results."""

from __future__ import annotations

import json
from typing import Any, Callable

from yongin_data.analysis.population import AGE_BANDS


def grounded_insight(question: str, intent: str, rows: list[dict], api_key: str,
                     model_json: Callable[..., dict]) -> str | None:
    if intent not in {"population", "monthly", "yearly", "group"} or len(rows) < 2:
        return None
    category_key = "district" if intent == "population" else "period" if intent in {"monthly", "yearly"} else "category"
    categories = [str(row[category_key]) for row in rows]
    if len(set(categories)) != len(categories):
        return None
    metrics = ([key for key in rows[0] if key != category_key] if intent == "population" else ["count"])
    if not metrics or any(not isinstance(row.get(metric), int) or row[metric] < 0
                          for row in rows for metric in metrics):
        return None
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"kind": {"type": "string", "enum": ["largest", "smallest", "difference", "none"]},
                             "metric": {"type": "string", "enum": metrics},
                             "first": {"type": ["string", "null"], "enum": categories + [None]},
                             "second": {"type": ["string", "null"], "enum": categories + [None]}},
              "required": ["kind", "metric", "first", "second"]}
    instructions = ("사용자 질문과 검증된 DB 결과만 보고 답변에서 강조할 비교 한 가지를 구조화 데이터로 고른다. "
                    "숫자·SQL·설명 문장은 생성하지 않는다. largest/smallest는 실제 최대·최소 항목을, "
                    "difference는 서로 다른 두 항목을 고른다. 근거 없는 원인·예측·현재 운영 상태를 추론하지 않는다. "
                    "적절한 비교가 없으면 none을 고른다.")
    evidence = {"question": question, "operation": intent, "rows": rows[:50]}
    choice = model_json(json.dumps(evidence, ensure_ascii=False, default=str), instructions,
                        schema, "grounded_insight", api_key, timeout_seconds=10)
    metric = choice.get("metric")
    kind = choice.get("kind")
    first, second = choice.get("first"), choice.get("second")
    if metric not in metrics or kind not in {"largest", "smallest", "difference", "none"}:
        raise ValueError("invalid insight choice")
    if kind == "none":
        return None
    values = {str(row[category_key]): row[metric] for row in rows}
    if first not in values:
        raise ValueError("insight category is not in the result")
    label = (AGE_BANDS[metric][0] if intent == "population" and metric in AGE_BANDS
             else "인구" if intent == "population" else "건수")
    unit = "명" if intent == "population" else "건"
    scope = "표시된 항목 중 " if intent != "population" else ""
    if kind == "largest":
        if values[first] != max(values.values()):
            raise ValueError("model-selected maximum does not match DB")
        return f"{scope}{label}이 가장 많은 곳은 **{first} ({values[first]:,}{unit})**입니다."
    if kind == "smallest":
        if values[first] != min(values.values()):
            raise ValueError("model-selected minimum does not match DB")
        return f"{scope}{label}이 가장 적은 곳은 **{first} ({values[first]:,}{unit})**입니다."
    if second not in values or first == second:
        raise ValueError("comparison categories are invalid")
    gap = abs(values[first] - values[second])
    if not gap:
        return f"{scope}{first}와 {second}의 {label}은 **같습니다 ({values[first]:,}{unit})**."
    larger, smaller = (first, second) if values[first] > values[second] else (second, first)
    return f"{scope}{larger}의 {label}이 {smaller}보다 **{gap:,}{unit} 많습니다**."

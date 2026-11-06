"""Grounded, bounded Korean presentation of verified database results."""

from __future__ import annotations

from typing import Any


def _subject(name: str) -> str:
    return name.split(" / ")[-1].split("_")[-1]


def describe(name: str, plan: dict[str, Any], rows: list[dict]) -> str:
    """Write only facts present in the executed plan and returned rows."""
    op = plan["operation"]
    conditions = []
    if plan.get("keyword"):
        conditions.append(f"검색어 ‘{plan['keyword']}’ 포함")
    if plan.get("filter_field"):
        conditions.append(f"{plan['filter_field']} = {plan['filter_value']}")
    if plan.get("year"):
        conditions.append(f"{plan['date_field']}의 {plan['year']}년")
    if plan.get("month"):
        conditions.append(f"{plan['date_field']}의 {plan['month']}월")
    condition = " · ".join(conditions) if conditions else "별도 조건 없이"
    title = _subject(name)
    if op in {"count", "overview"}:
        count = rows[0]["count"] if rows else 0
        if op == "overview":
            return (f"**{title}** 자료에는 적재된 기록이 **{count:,}건** 있습니다. "
                    "궁금한 검색어, 기간 또는 비교 기준을 질문해 주세요.")
        return f"**{title}**에서 {condition} 조회한 결과는 **{count:,}건**입니다."
    if op == "records":
        return (f"**{title}**에서 {condition} 조회한 기록 **{len(rows):,}건을 표시합니다**. "
                "화면에 표시된 행은 최대 20건이며 전체 건수를 뜻하지 않습니다.")
    total = sum(int(row["count"]) for row in rows)
    if not rows:
        return f"**{title}**에서 {condition} 집계한 결과가 없습니다."
    unit = {"monthly": "월", "yearly": "연도", "group": "분류"}[op]
    label = "period" if op in {"monthly", "yearly"} else "category"
    peak = max(rows, key=lambda row: row["count"])
    peak_label = str(peak[label])[:10] if peak[label] is not None else "값 없음"
    return (f"**{title}**에서 {condition} 집계한 {len(rows)}개 {unit}의 표시 합계는 **{total:,}건**입니다. "
            f"가장 많은 항목은 **{peak_label} ({peak['count']:,}건)**입니다.")


def suggestions(name: str, columns: dict[str, dict]) -> list[str]:
    title = _subject(name)
    result = [f"{title}은 몇 건이야?"]
    date = next((key for key, value in columns.items() if value["kind"] == "date"), None)
    group = next((key for key, value in columns.items() if value["kind"] == "group"), None)
    if date:
        result.append(f"{title} {date} 기준 월별로 보여줘")
    if group:
        result.append(f"{title} {group}별로 비교해줘")
    result.append(f"{title} 원본 20건 보여줘")
    return result[:3]

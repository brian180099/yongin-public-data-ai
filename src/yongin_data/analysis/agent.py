"""Single, bounded analysis path over the collector's read-only analytics views."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row

from yongin_data.config import get_settings

MAX_ROWS = 20
MAX_GROUPS = 50
MAX_TEXT = 160
FOLLOWUP = re.compile(r"그중|그 중|그거|월별로|연도별로|다시")
FORBIDDEN = re.compile(r"\b(select|drop|insert|update|delete|alter|truncate|grant|create)\b|삭제|수정해|업데이트해", re.I)
OTHER_CITY = re.compile(r"수원시|성남시|서울시|화성시|안양시|고양시|부천시|평택시")
DATE_NAMES = re.compile(r"(시작일|행사일|일정일|날짜|일자|일시|^일정$|^날짜$)")
GROUP_NAMES = re.compile(r"(구분|분류|유형|종류|지역|구$|도서관명)")
STOP = {"경기도", "용인시", "용인", "홈페이지", "정보", "관련", "데이터", "현황", "전체", "몇", "건", "있어", "알려줘", "보여줘"}


def _compact(value: str) -> str:
    return re.sub(r"[^가-힣A-Za-z0-9]", "", value).lower()


def _blank(status: str = "unsupported", answer: str = "") -> dict[str, Any]:
    return {"request_id": uuid.uuid4().hex, "status": status, "intent": "unknown", "answer": answer,
            "filters": {}, "result": [], "visualization": None, "sources": [],
            "calculation": None, "limitations": [], "interpreter": "rules", "context": None}


def _catalog(cur) -> list[dict]:
    cur.execute("""select s.dataset_id, s.display_name, s.provider, s.portal_url,
                          s.reference_date, s.collected_at, s.last_success_at
                   from analytics.dataset_sources s
                   where (s.provider = '경기도 용인시' or s.dataset_id = 'public_facilities')
                     and exists (select 1 from analytics.current_dataset_records r
                                 where r.dataset_id=s.dataset_id)
                   order by s.display_name, s.dataset_id""")
    return [dict(row) for row in cur.fetchall()]


def _choose(question: str, catalog: list[dict], context: dict | None) -> tuple[dict | None, list[dict]]:
    compact = _compact(question)
    matches = []
    for row in catalog:
        title = row["display_name"].split(" / ")[-1]
        words = [w for w in re.findall(r"[가-힣A-Za-z0-9]+", title) if len(w) > 1 and w not in STOP]
        score = sum(len(w) for w in words if _compact(w) in compact)
        # ZIP members have a concrete CSV name after the slash. An exact
        # member-name match is stronger than a broad portal title match.
        if " / " in row["display_name"] and _compact(title) in compact:
            score += 100
        if row["dataset_id"].lower() in question.lower():
            score += 100
        if score:
            matches.append((score, row))
    if matches:
        top = max(x[0] for x in matches)
        tied = [row for score, row in matches if score == top]
        return (tied[0], []) if len(tied) == 1 else (None, tied[:5])
    if FOLLOWUP.search(question) and context:
        return next((r for r in catalog if r["dataset_id"] == context.get("dataset_id")), None), []
    return None, []


def _basic_count(question: str, selected: dict) -> bool:
    """Recognize an unqualified count before expensive column profiling."""
    compact = _compact(question)
    title = selected["display_name"]
    selectors = [selected["dataset_id"], title, title.split(" / ")[-1],
                 title.split(" / ")[-1].split("_")[-1]]
    matched = sorted((_compact(s) for s in selectors if _compact(s) in compact), key=len, reverse=True)
    if not matched:
        return False
    remainder = compact.replace(matched[0], "", 1)
    remainder = re.sub(r"^(경기도)?용인시", "", remainder)
    return bool(re.fullmatch(
        r"(은|는|이|가|의)?(전체|총|적재)?"
        r"(몇건이야|몇건인가요|몇건있어|몇건|건수|총건수|몇개야|몇개|count)"
        r"(알려줘|보여줘)?", remainder))


def _columns(cur, dataset_id: str) -> dict[str, dict]:
    """Inspect all distinct values for candidates; never infer from a small sample."""
    cur.execute("""select key, count(*) as nonnull, count(distinct value) as distinct_count,
                          max(length(value)) as max_length
                   from analytics.current_dataset_records r,
                        lateral jsonb_each_text(r.payload) as p(key,value)
                   where r.dataset_id=%s and value is not null
                   group by key order by key limit 100""", (dataset_id,))
    candidates = [dict(r) for r in cur.fetchall()]
    validated = {}
    for item in candidates:
        name = item["key"]
        if DATE_NAMES.search(name) and "기준" not in name and item["distinct_count"] <= 10000 and item["max_length"] <= MAX_TEXT:
            cur.execute("""select distinct payload ->> %s as value
                           from analytics.current_dataset_records where dataset_id=%s
                           and payload ? %s and payload ->> %s is not null limit 10001""",
                        (name, dataset_id, name, name))
            values = [r["value"] for r in cur.fetchall()]
            if values and len(values) <= 10000:
                formats = ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%Y%m%d"]
                fmt = next((f for f in formats if all(_valid_date(v, f) for v in values)), None)
                if fmt:
                    validated[name] = {"kind": "date", "format": fmt}
        elif GROUP_NAMES.search(name) and item["distinct_count"] <= MAX_GROUPS and item["max_length"] <= MAX_TEXT:
            cur.execute("""select distinct payload ->> %s as value from analytics.current_dataset_records
                           where dataset_id=%s and payload ->> %s is not null limit 51""",
                        (name, dataset_id, name))
            values = [r["value"] for r in cur.fetchall()]
            if values and len(values) <= MAX_GROUPS:
                validated[name] = {"kind": "group", "values": values}
    return validated


def _valid_date(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
        return True
    except (ValueError, TypeError):
        return False


def _rule_plan(question: str, selected: dict, columns: dict, context: dict | None) -> dict:
    quoted = re.search(r"[‘'\"]([^’'\"]{1,80})[’'\"]", question)
    keyword = quoted.group(1) if quoted else None
    year_match = re.search(r"(?<!\d)(20\d{2})년?(?!\d)", question)
    month_match = re.search(r"(?<!\d)(1[0-2]|0?[1-9])월(?!별)", question)
    year = int(year_match.group(1)) if year_match else None
    month = int(month_match.group(1)) if month_match else None
    if FOLLOWUP.search(question) and context and context.get("dataset_id") == selected["dataset_id"]:
        year = year if year is not None else context.get("year")
        month = month if month is not None else context.get("month")
        keyword = keyword if keyword is not None else context.get("keyword")
    date_fields = [k for k, v in columns.items() if v["kind"] == "date"]
    date_field = next((k for k in date_fields if "시작" in k), date_fields[0] if len(date_fields) == 1 else None)
    group_fields = [k for k, v in columns.items() if v["kind"] == "group"]
    district = next((d for d in ("처인구", "기흥구", "수지구") if d in question), None)
    filter_field = next((k for k in group_fields if district and district in columns[k]["values"]), None)
    filter_value = district
    if not filter_field:
        found = [(len(value), key, value) for key in group_fields for value in columns[key]["values"]
                 if len(value) >= 2 and _compact(value) in _compact(question)]
        if found:
            _, filter_field, filter_value = max(found)
    group_field = next((k for k in group_fields if any(x in question for x in (k, "구별" if "구" in k else "분류별"))), None)
    if "월별" in question:
        op = "monthly"
    elif "연도별" in question:
        op = "yearly"
    elif "별" in question or "비교" in question:
        op = "group"
    elif re.search(r"몇|건수|개수|총|전체", question) or keyword or year or month or district:
        op = "count"
    else:
        op = "records"
    return {"dataset_id": selected["dataset_id"], "operation": op, "keyword": keyword,
            "year": year, "month": month, "date_field": date_field,
            "filter_field": filter_field, "filter_value": filter_value, "group_field": group_field}


def _llm_plan(question: str, catalog: list[dict], selected: dict | None, columns: dict,
              context: dict | None, api_key: str) -> dict:
    ids = [r["dataset_id"] for r in catalog]
    names = list(columns)
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "dataset_id": {"type": "string", "enum": ids},
        "operation": {"type": "string", "enum": ["count", "records", "monthly", "yearly", "group", "unsupported"]},
        "keyword": {"type": ["string", "null"]}, "year": {"type": ["integer", "null"]},
        "month": {"type": ["integer", "null"]},
        "date_field": {"type": ["string", "null"]},
        "filter_field": {"type": ["string", "null"]}, "filter_value": {"type": ["string", "null"]},
        "group_field": {"type": ["string", "null"]}},
        "required": ["dataset_id", "operation", "keyword", "year", "month", "date_field",
                     "filter_field", "filter_value", "group_field"]}
    instructions = ("허용 목록의 용인 관련 공공데이터만 분석한다. SQL을 쓰지 말고 구조화된 계획만 낸다. "
                    "날짜·그룹 조건은 검증된 컬럼만 사용한다. 불명확하면 unsupported. "
                    f"자료 목록: {[(r['dataset_id'], r['display_name']) for r in catalog]}. "
                    f"선택된 자료: {selected['dataset_id'] if selected else None}. 검증된 컬럼: {names}. "
                    f"직전 검증 문맥: {context}.")
    with httpx.Client(timeout=20) as client:
        response = client.post("https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": "gpt-4o-mini", "instructions": instructions, "input": question,
                  "store": False, "max_output_tokens": 350,
                  "text": {"format": {"type": "json_schema", "name": "yongin_plan", "strict": True, "schema": schema}}})
        response.raise_for_status()
        body = response.json()
    if body.get("status") != "completed":
        raise ValueError("incomplete plan")
    parts = [p["text"] for item in body.get("output", []) for p in item.get("content", [])
             if p.get("type") == "output_text"]
    return json.loads("".join(parts))


def _validate(plan: dict, selected: dict, columns: dict) -> str | None:
    if plan.get("dataset_id") != selected["dataset_id"]:
        return "자료 선택을 확인할 수 없습니다. 자료명을 다시 지정해 주세요."
    if plan.get("operation") not in {"count", "records", "monthly", "yearly", "group"}:
        return "이 질문 유형은 아직 지원하지 않습니다."
    if plan.get("keyword") is not None and (not isinstance(plan["keyword"], str) or len(plan["keyword"]) > 80):
        return "검색어는 80자 이내로 지정해 주세요."
    if plan.get("year") is not None and (not isinstance(plan["year"], int) or not 1900 <= plan["year"] <= 2100):
        return "연도 범위를 확인해 주세요."
    if plan.get("month") is not None and (not isinstance(plan["month"], int) or not 1 <= plan["month"] <= 12):
        return "월 범위를 확인해 주세요."
    date_field = plan.get("date_field")
    if (plan.get("year") or plan.get("month") or plan["operation"] in {"monthly", "yearly"}) and (date_field not in columns or columns[date_field]["kind"] != "date"):
        return "이 자료의 날짜 컬럼을 전체 값으로 검증하지 못해 기간 집계를 지원하지 않습니다."
    for key in ("filter_field", "group_field"):
        field = plan.get(key)
        if field and (field not in columns or columns[field]["kind"] != "group"):
            return "이 자료에서 검증된 지역·분류 컬럼만 조건과 비교에 사용할 수 있습니다."
    if plan.get("filter_value") and (not plan.get("filter_field") or plan["filter_value"] not in columns[plan["filter_field"]]["values"]):
        return "요청한 지역·분류 값이 검증된 컬럼에 없습니다."
    if plan["operation"] == "group" and not plan.get("group_field"):
        return "비교할 지역·분류 컬럼이 명확하지 않습니다."
    return None


def _execute(cur, plan: dict, columns: dict) -> list[dict]:
    where = ["dataset_id=%s"]
    args: list[Any] = [plan["dataset_id"]]
    if plan.get("keyword"):
        pattern = "%" + re.sub(r"([%_\\])", r"\\\1", plan["keyword"]) + "%"
        where.append("exists (select 1 from jsonb_each_text(payload) v where v.value ilike %s escape '\\')")
        args.append(pattern)
    if plan.get("filter_field"):
        where.append("payload ->> %s = %s")
        args.extend([plan["filter_field"], plan["filter_value"]])
    if plan.get("year") or plan.get("month"):
        fmt = {"%Y-%m-%d": "YYYY-MM-DD", "%Y.%m.%d": "YYYY.MM.DD", "%Y/%m/%d": "YYYY/MM/DD", "%Y%m%d": "YYYYMMDD"}[columns[plan["date_field"]]["format"]]
        expression = "to_date(payload ->> %s, %s)"
        if plan.get("year"):
            where.append(f"extract(year from {expression}) = %s")
            args.extend([plan["date_field"], fmt, plan["year"]])
        if plan.get("month"):
            where.append(f"extract(month from {expression}) = %s")
            args.extend([plan["date_field"], fmt, plan["month"]])
    base = " from analytics.current_dataset_records where " + " and ".join(where)
    op = plan["operation"]
    if op == "count":
        cur.execute("select count(*)::int as count" + base, args)
    elif op == "records":
        cur.execute("select payload" + base + " and octet_length(payload::text) <= 4096 order by record_key limit %s", args + [MAX_ROWS])
    elif op in {"monthly", "yearly"}:
        unit = "month" if op == "monthly" else "year"
        fmt = {"%Y-%m-%d": "YYYY-MM-DD", "%Y.%m.%d": "YYYY.MM.DD", "%Y/%m/%d": "YYYY/MM/DD", "%Y%m%d": "YYYYMMDD"}[columns[plan["date_field"]]["format"]]
        cur.execute(f"select date_trunc('{unit}', to_date(payload ->> %s, %s))::date as period, count(*)::int as count" + base +
                    " and payload ->> %s is not null group by 1 order by 1 limit %s",
                    [plan["date_field"], fmt] + args + [plan["date_field"], MAX_GROUPS])
    else:
        cur.execute("select payload ->> %s as category, count(*)::int as count" + base +
                    " and payload ->> %s is not null group by 1 order by count desc, category limit %s",
                    [plan["group_field"]] + args + [plan["group_field"], MAX_GROUPS])
    return [dict(r) for r in cur.fetchall()]


def analyze(question: str, *, context: dict | None = None, database_url: str | None = None,
            api_key: str | None = None) -> dict[str, Any]:
    question = question.strip()
    if not 1 <= len(question) <= 300:
        return _blank("clarification", "질문을 1~300자로 입력해 주세요.")
    if FORBIDDEN.search(question):
        return _blank("unsupported", "임의 SQL이나 데이터 변경 요청은 처리하지 않습니다.")
    if OTHER_CITY.search(question):
        return _blank("unsupported", "용인 관련 허용 자료만 조회합니다.")
    settings = get_settings()
    url = database_url or settings.database_url
    if not url:
        return _blank("error", "읽기 전용 DATABASE_URL이 설정되지 않았습니다.")
    try:
        with psycopg.connect(url, connect_timeout=5, row_factory=dict_row) as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute("set transaction read only")
                    cur.execute("set local statement_timeout = '5000ms'")
                    cur.execute("select session_user")
                    if cur.fetchone()["session_user"] != "yongin_analysis_login":
                        return _blank("error", "분석 전용 읽기 계정으로 연결해야 합니다.")
                    cur.execute("set local role yongin_analysis_reader")
                    catalog = _catalog(cur)
                    if re.search(r"어떤 데이터|데이터셋|자료 목록|데이터 목록", question):
                        result = _blank("ok", f"적재된 용인 관련 공공데이터 {len(catalog)}종입니다.")
                        result.update(intent="catalog", result=[{"dataset_id": x["dataset_id"], "dataset_name": x["display_name"]} for x in catalog])
                        return result
                    selected, tied = _choose(question, catalog, context)
                    if tied:
                        result = _blank("clarification", "자료를 하나 선택해 주세요: " + ", ".join(x["display_name"] for x in tied))
                        result["result"] = [{"dataset_id": x["dataset_id"], "dataset_name": x["display_name"]} for x in tied]
                        return result
                    if not selected:
                        return _blank("clarification", "자료명을 특정해 주세요. ‘어떤 데이터가 있어?’로 목록을 볼 수 있습니다.")
                    simple_count = _basic_count(question, selected)
                    columns = {} if simple_count else _columns(cur, selected["dataset_id"])
                    plan = ({"dataset_id": selected["dataset_id"], "operation": "count",
                             "keyword": None, "year": None, "month": None, "date_field": None,
                             "filter_field": None, "filter_value": None, "group_field": None}
                            if simple_count else _rule_plan(question, selected, columns, context))
                    interpreter = "rules"
                    if api_key or settings.openai_api_key:
                        try:
                            candidate = _llm_plan(question, catalog, selected, columns, context, api_key or settings.openai_api_key)
                            if not _validate(candidate, selected, columns):
                                plan = candidate
                                interpreter = "llm"
                        except (httpx.HTTPError, ValueError, KeyError, TypeError):
                            pass
                    # Rules do not silently reinterpret unsupported qualifiers.
                    if re.search(r"오늘|내일|이번|지난|다음|현재|예약|운영 중|평균|합계|순위|가장|추세|부터|까지", question):
                        return _blank("unsupported", "현재 운영 상태·예약 가능 여부·범위/순위/평균 분석은 검증된 계약이 없어 지원하지 않습니다.")
                    if re.search(r"\d{4}년", question) and plan.get("year") is None:
                        return _blank("unsupported", "연도 조건을 해석하지 못했습니다.")
                    if any(d in question for d in ("처인구", "기흥구", "수지구")) and not plan.get("filter_field"):
                        return _blank("unsupported", "이 자료에 검증된 구 컬럼이 없어 지역 조건을 적용할 수 없습니다.")
                    reason = _validate(plan, selected, columns)
                    if reason:
                        return _blank("unsupported", reason)
                    rows = _execute(cur, plan, columns)
                    source = {"dataset_id": selected["dataset_id"], "dataset_name": selected["display_name"],
                              "provider": selected["provider"], "url": selected["portal_url"],
                              "reference_date": str(selected["reference_date"]) if selected["reference_date"] else None,
                              "collected_at": selected["collected_at"].isoformat() if selected["collected_at"] else None,
                              "last_success_at": selected["last_success_at"].isoformat() if selected["last_success_at"] else None}
                    op = plan["operation"]
                    total = rows[0]["count"] if op == "count" else sum(r.get("count", 0) for r in rows) if op != "records" else len(rows)
                    answer = (f"{selected['display_name']}: 조건에 맞는 적재 행 {total:,}건입니다." if op == "count" else
                              f"{selected['display_name']}: {op} 결과 {len(rows)}개 항목, 합계 {total:,}건입니다." if op != "records" else
                              f"{selected['display_name']}: 원본 행 {len(rows)}건을 표시합니다(최대 {MAX_ROWS}건).")
                    result = _blank("ok", answer)
                    result.update(intent=op, filters={k: v for k, v in plan.items() if k != "dataset_id" and v is not None},
                                  result=rows, sources=[source], interpreter=interpreter,
                                  calculation={"measure": "현재 활성 적재 행 수", "method": op, "date_field": plan.get("date_field")},
                                  limitations=["등록 현황은 실제 운영 중·예약 가능·현재 행사를 뜻하지 않습니다."] +
                                              (["날짜가 없는 행은 기간 집계에서 제외합니다."] if op in {"monthly", "yearly"} else []),
                                  context={k: plan.get(k) for k in ("dataset_id", "keyword", "year", "month", "date_field", "filter_field", "filter_value")})
                    return result
    except psycopg.errors.QueryCanceled:
        return _blank("unsupported", "자료가 커서 제한 시간 5초 안에 검증·집계를 마치지 못했습니다. 자료나 조건을 더 좁혀 주세요.")
    except psycopg.Error:
        return _blank("error", "읽기 전용 데이터베이스 조회에 실패했습니다. 연결과 권한을 확인해 주세요.")

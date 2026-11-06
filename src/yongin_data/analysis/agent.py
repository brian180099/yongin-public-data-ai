"""Single, bounded analysis path over the collector's read-only analytics views."""

from __future__ import annotations

import json
import re
import uuid
from atexit import register
from collections import OrderedDict
from contextlib import ExitStack
from copy import deepcopy
from datetime import datetime
from threading import Lock
from time import monotonic
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool, PoolClosed, PoolTimeout

from yongin_data.config import get_settings
from yongin_data.analysis.presentation import describe, suggestions
from yongin_data.analysis.population import (DATASET_ID as POPULATION_DATASET_ID,
                                             PopulationContractError, summarize as summarize_population,
                                             wants_population)
from yongin_data.analysis.insights import grounded_insight
from yongin_data.analysis.question_profile import (llm_profile, presentation_for,
                                                    rule_profile)

MAX_ROWS = 20
MAX_GROUPS = 50
MAX_TEXT = 160
COLUMN_CACHE_MAX = 64
CATALOG_CACHE_SECONDS = 30
CATALOG_CACHE_MAX = 4
_column_cache: OrderedDict[tuple, dict[str, dict]] = OrderedDict()
_column_cache_lock = Lock()
_catalog_cache: dict[tuple, tuple[float, list[dict]]] = {}
_catalog_cache_lock = Lock()
_remote_pool_lock = Lock()
_remote_pool_url: str | None = None
_remote_pool: ConnectionPool | None = None
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
            "calculation": None, "limitations": [], "interpreter": "rules", "context": None,
            "model_status": "not_used", "insight": None, "insight_status": "not_used",
            "question_understanding": None, "presentation": None, "ai_usage": {}, "pipeline": []}


def _database_identity(cur) -> tuple:
    info = getattr(getattr(cur, "connection", None), "info", None)
    return tuple(getattr(info, name, None) for name in ("host", "port", "dbname", "user"))


def _database_identity_from_url(url: str) -> tuple:
    info = psycopg.conninfo.conninfo_to_dict(url)
    return (info.get("host"), int(info.get("port") or 5432), info.get("dbname"), info.get("user"))


def _catalog(cur) -> list[dict]:
    cur.execute("""select s.dataset_id, s.display_name, s.provider, s.portal_url,
                          s.reference_date, s.collected_at, s.last_success_at
                   from analytics.dataset_sources s
                   where (s.provider = '경기도 용인시' or s.dataset_id = 'public_facilities')
                     and exists (select 1 from analytics.current_dataset_records r
                                 where r.dataset_id=s.dataset_id)
                   order by s.display_name, s.dataset_id""")
    return [dict(row) for row in cur.fetchall()]


def _catalog_cached(cur=None, *, key: tuple | None = None) -> list[dict] | None:
    """Keep the large source-list query fresh without repeating it per question."""
    key = key if key is not None else _database_identity(cur)
    now = monotonic()
    with _catalog_cache_lock:
        cached = _catalog_cache.get(key)
        if cached and now - cached[0] < CATALOG_CACHE_SECONDS:
            return deepcopy(cached[1])
    if cur is None:
        return None
    catalog = _catalog(cur)
    with _catalog_cache_lock:
        _catalog_cache[key] = (monotonic(), deepcopy(catalog))
        while len(_catalog_cache) > CATALOG_CACHE_MAX:
            _catalog_cache.pop(next(iter(_catalog_cache)))
    return catalog


def _merge_catalogs(local: list[dict], remote: list[dict]) -> tuple[list[dict], dict[str, str]]:
    """Use the newest successful source version; keep local on a tie."""
    chosen = {row["dataset_id"]: row for row in local}
    backend = {row["dataset_id"]: "local" for row in local}
    for row in remote:
        dataset_id = row["dataset_id"]
        previous = chosen.get(dataset_id)
        current_version = row.get("last_success_at") or row.get("collected_at")
        previous_version = ((previous.get("last_success_at") or previous.get("collected_at"))
                            if previous else None)
        if previous is None or (current_version is not None and
                                (previous_version is None or current_version > previous_version)):
            chosen[dataset_id] = row
            backend[dataset_id] = "supabase"
    return sorted(chosen.values(), key=lambda row: (row["display_name"], row["dataset_id"])), backend


def _prepare_reader(cur) -> bool:
    cur.execute("set transaction read only")
    cur.execute("set local statement_timeout = '5000ms'")
    cur.execute("select session_user")
    if cur.fetchone()["session_user"] != "yongin_analysis_login":
        return False
    cur.execute("set local role yongin_analysis_reader")
    return True


def _supabase_pool(url: str) -> ConnectionPool:
    global _remote_pool, _remote_pool_url
    with _remote_pool_lock:
        if _remote_pool is None or _remote_pool_url != url:
            if _remote_pool is not None:
                _remote_pool.close()
            _remote_pool = ConnectionPool(conninfo=url, min_size=0, max_size=4, timeout=10,
                                          kwargs={"connect_timeout": 5, "row_factory": dict_row},
                                          open=True, name="yongin-question-supabase")
            _remote_pool_url = url
        return _remote_pool


@register
def _close_supabase_pool() -> None:
    if _remote_pool is not None:
        _remote_pool.close()


def _choose(question: str, catalog: list[dict], context: dict | None) -> tuple[dict | None, list[dict]]:
    if context and context.get("pending_question") == question:
        chosen = next((r for r in catalog if r["dataset_id"] == context.get("selection_id")), None)
        if chosen:
            return chosen, []
    compact = _compact(question)
    if FOLLOWUP.search(question) and context and context.get("dataset_id"):
        explicit = next((r for r in catalog if r["dataset_id"].lower() in question.lower() or
                         (len(_compact(r["display_name"].split(" / ")[-1])) >= 5 and
                          _compact(r["display_name"].split(" / ")[-1]) in compact)), None)
        if explicit:
            return explicit, []
        previous = next((r for r in catalog if r["dataset_id"] == context["dataset_id"]), None)
        if previous:
            return previous, []
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
    return None, []


def _basic_count(question: str, selected: dict) -> bool:
    """Recognize an unqualified count before expensive column profiling."""
    compact = _compact(question)
    title = selected["display_name"]
    member = title.split(" / ")[-1].split("_")[-1]
    selectors = [selected["dataset_id"], title, title.split(" / ")[-1], member,
                 re.sub(r"(?:\s*(?:정보|현황|데이터))+$", "", member)]
    matched = sorted((_compact(s) for s in selectors if _compact(s) in compact), key=len, reverse=True)
    if not matched:
        return False
    remainder = compact.replace(matched[0], "", 1)
    remainder = re.sub(r"^(경기도)?용인시", "", remainder)
    return bool(re.fullmatch(
        r"(은|는|이|가|의)?(전체|총|적재)?"
        r"(몇건이야|몇건인가요|몇건있어|몇건|건수|총건수|몇개야|몇개|count)"
        r"(알려줘|보여줘)?", remainder))


def _explicit_district(question: str, selected: dict) -> str | None:
    """A district in the dataset title is not a user requested row filter."""
    remainder = question
    title = selected.get("display_name", "")
    for part in (title, title.split(" / ")[-1], title.split("_")[-1]):
        if part:
            remainder = remainder.replace(part, "")
    return next((district for district in ("처인구", "기흥구", "수지구") if district in remainder), None)


def _safe_context(context: dict | None) -> dict | None:
    if not isinstance(context, dict):
        return None
    allowed = {"dataset_id", "keyword", "year", "month", "date_field",
               "filter_field", "filter_value", "selection_id", "pending_question"}
    clean = {k: v for k, v in context.items() if k in allowed and
             (v is None or isinstance(v, int) or isinstance(v, str) and len(v) <= 300)}
    return clean or None


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


def _stored_columns(cur, dataset_id: str) -> dict[str, dict] | None:
    """Accept a persisted contract only when run ID, raw SHA and timestamp match."""
    try:
        with cur.connection.transaction():
            cur.execute("""select c.column_name, c.kind, c.date_format, c.group_values
                           from analytics.dataset_contract_versions v
                           join analytics.dataset_source_fingerprints f
                             on f.dataset_id=v.dataset_id
                           left join analytics.dataset_column_contracts c
                             on c.source_database=v.source_database and c.dataset_id=v.dataset_id
                           where v.source_database='local' and v.dataset_id=%s
                             and v.validation_status='validated'
                             and v.source_last_success_at is not distinct from f.last_success_at
                             and v.source_run_id is not distinct from f.source_run_id
                             and v.source_raw_sha256 is not distinct from f.source_raw_sha256""",
                        (dataset_id,))
            rows = cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return None
    if not rows:
        return None
    return {row["column_name"]: ({"kind": "date", "format": row["date_format"]}
                                 if row["kind"] == "date" else
                                 {"kind": "group", "values": row["group_values"]})
            for row in rows if row["column_name"] is not None}


def _validated_columns(cur, selected: dict, backend: str = "local") -> dict[str, dict]:
    """Reuse a complete validation while its collected source version is unchanged."""
    if backend == "local" and getattr(cur, "connection", None) is not None:
        stored = _stored_columns(cur, selected["dataset_id"])
        if stored is not None:
            return stored
    database = _database_identity(cur)
    key = (database, selected["dataset_id"], selected.get("last_success_at"),
           selected.get("collected_at"))
    with _column_cache_lock:
        cached = _column_cache.get(key)
        if cached is not None:
            _column_cache.move_to_end(key)
            return deepcopy(cached)
    columns = _columns(cur, selected["dataset_id"])
    with _column_cache_lock:
        _column_cache[key] = deepcopy(columns)
        _column_cache.move_to_end(key)
        while len(_column_cache) > COLUMN_CACHE_MAX:
            _column_cache.popitem(last=False)
    return columns


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
    district = _explicit_district(question, selected)
    filter_field = next((k for k in group_fields if district and district in columns[k]["values"]), None)
    filter_value = district
    if not filter_field:
        condition_text = question.replace(quoted.group(0), "") if quoted else question
        for title_part in re.findall(r"[가-힣A-Za-z0-9]+", selected.get("display_name", "")):
            if len(title_part) > 1:
                condition_text = condition_text.replace(title_part, "")
        found = [(len(value), key, value) for key in group_fields for value in columns[key]["values"]
                 if len(value) >= 2 and _compact(value) in _compact(condition_text)]
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
    elif re.search(r"보여줘|목록|원본|행|찾아줘|검색", question):
        op = "records"
    else:
        op = "overview"
    return {"dataset_id": selected["dataset_id"], "operation": op, "keyword": keyword,
            "year": year, "month": month, "date_field": date_field,
            "filter_field": filter_field, "filter_value": filter_value, "group_field": group_field}


def _inherit_verified_context(plan: dict, question: str, selected: dict,
                              columns: dict, context: dict | None) -> dict:
    """Carry filters only for an explicit follow-up on the same verified source."""
    if not context or not FOLLOWUP.search(question) or context.get("dataset_id") != selected["dataset_id"]:
        return plan
    plan = plan.copy()
    for key in ("keyword", "year", "month"):
        if plan.get(key) is None and context.get(key) is not None:
            plan[key] = context[key]
    field, value = context.get("filter_field"), context.get("filter_value")
    if (not plan.get("filter_field") and field in columns and columns[field]["kind"] == "group"
            and value in columns[field]["values"]):
        plan["filter_field"], plan["filter_value"] = field, value
    date_field = context.get("date_field")
    if (not plan.get("date_field") and date_field in columns and columns[date_field]["kind"] == "date"):
        plan["date_field"] = date_field
    return plan


def _model_json(question: str, instructions: str, schema: dict, name: str, api_key: str,
                *, timeout_seconds: int = 30) -> dict:
    """Ask for data only; never accept executable SQL or a model-written answer."""
    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post("https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": get_settings().openai_model, "instructions": instructions,
                  "input": question, "store": False, "max_output_tokens": 400,
                  "text": {"format": {"type": "json_schema", "name": name,
                                        "strict": True, "schema": schema}}})
        response.raise_for_status()
        body = response.json()
    if body.get("status") != "completed":
        raise ValueError("incomplete model response")
    parts = [p["text"] for item in body.get("output", []) for p in item.get("content", [])
             if p.get("type") == "output_text"]
    if not parts:
        raise ValueError("model returned no structured output")
    return json.loads("".join(parts))


def _llm_select(question: str, catalog: list[dict], context: dict | None,
                api_key: str) -> dict:
    ids = [r["dataset_id"] for r in catalog]
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"dataset_id": {"type": ["string", "null"], "enum": ids + [None]},
                             "needs_clarification": {"type": "boolean"},
                             "candidate_ids": {"type": "array", "items": {"type": "string", "enum": ids}}},
              "required": ["dataset_id", "needs_clarification", "candidate_ids"]}
    names = [(r["dataset_id"], r["display_name"]) for r in catalog]
    instructions = ("용인 관련 자료를 고른다. 질문에 명시된 자료가 정확히 하나일 때만 ID를 선택한다. "
                    "둘 이상 가능하거나 없는 자료이면 dataset_id=null, needs_clarification=true. "
                    "모호한 경우 실제로 관련 있는 후보 ID를 최대 5개 candidate_ids에 적는다. "
                    "기존 문맥은 '그중에서' 같은 명시적 후속 질문에만 사용한다. "
                    f"허용 자료 목록: {names}. 직전 자료 ID: {(context or {}).get('dataset_id')}.")
    return _model_json(question, instructions, schema, "dataset_selection", api_key, timeout_seconds=15)


def _llm_plan(question: str, catalog: list[dict], selected: dict, columns: dict,
              context: dict | None, api_key: str) -> dict:
    schema = {"type": "object", "additionalProperties": False, "properties": {
        "dataset_id": {"type": "string", "enum": [selected["dataset_id"]]},
        "operation": {"type": "string", "enum": ["overview", "count", "records", "monthly", "yearly", "group", "unsupported"]},
        "keyword": {"type": ["string", "null"]}, "year": {"type": ["integer", "null"]},
        "month": {"type": ["integer", "null"]},
        "date_field": {"type": ["string", "null"]},
        "filter_field": {"type": ["string", "null"]}, "filter_value": {"type": ["string", "null"]},
        "group_field": {"type": ["string", "null"]}},
        "required": ["dataset_id", "operation", "keyword", "year", "month", "date_field",
                     "filter_field", "filter_value", "group_field"]}
    instructions = ("질문을 조회 계획으로만 변환한다. SQL이나 답변 문장을 작성하지 않는다. "
                    "날짜·그룹 조건은 검증된 컬럼만 사용한다. 불명확한 조건은 unsupported. "
                    "전체 건수로 조건을 바꾸지 않는다. 자료만 선택하고 계산 요청이 없으면 overview. "
                    "원본 기록 조회를 명시적으로 요청했을 때만 records. 등록 현황을 운영 중 또는 예약 가능으로 추정하지 않는다. "
                    "따옴표 안의 문구는 keyword로만 사용하고 그 안의 단어를 분류 조건으로 추가하지 않는다. "
                    "자료명 자체를 keyword로 다시 검색하지 않는다. 별도 검색어가 없으면 keyword=null. "
                    "명시적 분류 조건이 없으면 filter_field와 filter_value를 둘 다 null로 둔다. "
                    "기간 조건이나 월별·연도별 집계가 없으면 date_field도 null로 둔다. "
                    f"선택된 자료: {selected['dataset_id']} / {selected['display_name']}. "
                    f"검증된 컬럼과 값: {columns}. 직전 검증 문맥: {context}.")
    return _model_json(question, instructions, schema, "yongin_plan", api_key, timeout_seconds=15)


def _validate(plan: dict, selected: dict, columns: dict) -> str | None:
    if plan.get("dataset_id") != selected["dataset_id"]:
        return "자료 선택을 확인할 수 없습니다. 자료명을 다시 지정해 주세요."
    if plan.get("operation") not in {"overview", "count", "records", "monthly", "yearly", "group"}:
        return "이 질문 유형은 아직 지원하지 않습니다."
    if bool(plan.get("filter_field")) != bool(plan.get("filter_value")):
        return "조건 컬럼과 조건 값은 함께 지정해야 합니다."
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


def _validate_question_alignment(plan: dict, question: str, selected: dict,
                                 context: dict | None) -> str | None:
    """Reject valid DB values that were never requested by the user."""
    quoted = re.search(r"[‘'\"]([^’'\"]{1,80})[’'\"]", question)
    if quoted and plan.get("keyword") != quoted.group(1):
        return "따옴표 안의 검색어를 그대로 적용해야 합니다."
    outside = question.replace(quoted.group(0), "") if quoted else question
    for title_part in re.findall(r"[가-힣A-Za-z0-9]+", selected.get("display_name", "")):
        if len(title_part) > 1:
            outside = outside.replace(title_part, "")
    if not quoted and plan.get("keyword") and _compact(plan["keyword"]) not in _compact(outside):
        return "자료명을 검색 조건으로 다시 적용할 수 없습니다."
    same_followup = bool(context and FOLLOWUP.search(question) and
                         context.get("dataset_id") == selected["dataset_id"])
    year, month = plan.get("year"), plan.get("month")
    if year is not None and not re.search(rf"(?<!\d){year}년?(?!\d)", question) and not (
            same_followup and context.get("year") == year):
        return "질문에 없는 연도 조건은 적용할 수 없습니다."
    if month is not None and not re.search(rf"(?<!\d)0?{month}월(?!별)", question) and not (
            same_followup and context.get("month") == month):
        return "질문에 없는 월 조건은 적용할 수 없습니다."
    if plan.get("date_field") and not (plan.get("year") or plan.get("month") or
                                        plan.get("operation") in {"monthly", "yearly"}):
        return "기간 분석이 아닌 질문에 날짜 기준을 추가할 수 없습니다."
    if plan.get("group_field") and plan.get("operation") != "group":
        return "그룹 분석이 아닌 질문에 비교 기준을 추가할 수 없습니다."
    value = plan.get("filter_value")
    inherited = bool(same_followup and
                     context.get("filter_field") == plan.get("filter_field") and
                     context.get("filter_value") == value)
    if value and not inherited and _compact(value) not in _compact(outside):
        return "질문에 없는 지역·분류 조건은 적용할 수 없습니다."
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
    if op in {"count", "overview"}:
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
            supabase_database_url: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    question = question.strip()
    context = _safe_context(context)
    if not 1 <= len(question) <= 300:
        return _blank("clarification", "질문을 1~300자로 입력해 주세요.")
    if FORBIDDEN.search(question):
        return _blank("unsupported", "임의 SQL이나 데이터 변경 요청은 처리하지 않습니다.")
    if OTHER_CITY.search(question):
        return _blank("unsupported", "용인 관련 허용 자료만 조회합니다.")
    settings = get_settings()
    model_key = api_key if api_key is not None else settings.openai_api_key
    model_status = "not_used"
    profile = rule_profile(question)
    ai_usage = {"question_understanding": profile["model_status"], "dataset_selection": "not_used",
                "query_plan": "not_used", "result_interpretation": "not_used"}
    if model_key:
        try:
            profile = llm_profile(question, model_key, _model_json)
            ai_usage["question_understanding"] = "completed"
            model_status = "completed"
        except httpx.HTTPError:
            profile["model_status"] = "failed"
            ai_usage["question_understanding"] = "failed"
            model_status = "failed"
        except (ValueError, KeyError, TypeError):
            profile["model_status"] = "rejected"
            ai_usage["question_understanding"] = "rejected"
            model_status = "rejected"

    def finalize(result: dict) -> dict:
        result["question_understanding"] = {key: profile[key] for key in
                                            ("goal", "output_format", "detail", "semantic_summary")}
        result["ai_usage"] = ai_usage.copy()
        result["model_status"] = model_status
        if result.get("status") == "ok":
            presentation, limitation = presentation_for(result.get("intent", "unknown"), profile)
            result["presentation"] = presentation
            if limitation and limitation not in result["limitations"]:
                result["limitations"].append(limitation)
        result["pipeline"] = [
            {"stage": "question_understanding", "actor": "llm" if ai_usage["question_understanding"] == "completed" else "rules",
             "status": ai_usage["question_understanding"]},
            {"stage": "dataset_selection", "actor": "llm" if ai_usage["dataset_selection"] == "completed" else "server",
             "status": ai_usage["dataset_selection"]},
            {"stage": "query_plan", "actor": "llm" if ai_usage["query_plan"] == "completed" else "server",
             "status": ai_usage["query_plan"]},
            {"stage": "calculation", "actor": "database_python",
             "status": "completed" if result.get("status") == "ok" and result.get("calculation") else "not_run"},
            {"stage": "result_interpretation", "actor": "llm",
             "status": ai_usage["result_interpretation"]},
        ]
        return result

    def add_insight(result: dict) -> dict:
        nonlocal model_status
        if result.get("intent") not in {"population", "monthly", "yearly", "group"} or len(result.get("result", [])) < 2:
            return finalize(result)
        if not model_key:
            result["insight_status"] = "not_configured"
            ai_usage["result_interpretation"] = "not_configured"
            return finalize(result)
        try:
            result["insight"] = grounded_insight(question, result["intent"], result["result"],
                                                  model_key, _model_json)
            result["insight_status"] = "completed" if result["insight"] else "no_insight"
            ai_usage["result_interpretation"] = result["insight_status"]
            model_status = "completed"
        except httpx.HTTPError:
            result["insight_status"] = "failed"
            ai_usage["result_interpretation"] = "failed"
        except (ValueError, KeyError, TypeError):
            result["insight_status"] = "rejected"
            ai_usage["result_interpretation"] = "rejected"
        return finalize(result)

    def reply(status: str, answer: str) -> dict[str, Any]:
        result = _blank(status, answer)
        return finalize(result)
    url = database_url or settings.database_url
    remote_url = supabase_database_url if supabase_database_url is not None else settings.supabase_analysis_db_url
    if not url:
        return finalize(_blank("error", "읽기 전용 DATABASE_URL이 설정되지 않았습니다."))
    try:
        with ExitStack() as stack:
            conn = stack.enter_context(psycopg.connect(url, connect_timeout=5, row_factory=dict_row))
            with conn.transaction():
                with conn.cursor() as cur:
                    if not _prepare_reader(cur):
                        return _blank("error", "분석 전용 읽기 계정으로 연결해야 합니다.")
                    local_catalog = _catalog_cached(cur)
                    remote_cur = None
                    remote_catalog = []
                    if remote_url:
                        remote_catalog = _catalog_cached(key=_database_identity_from_url(remote_url))
                        if remote_catalog is None:
                            remote_conn = stack.enter_context(_supabase_pool(remote_url).connection())
                            stack.enter_context(remote_conn.transaction())
                            remote_cur = stack.enter_context(remote_conn.cursor())
                            if not _prepare_reader(remote_cur):
                                return _blank("error", "Supabase 분석 연결은 읽기 전용 계정을 사용해야 합니다.")
                            remote_catalog = _catalog_cached(remote_cur)
                    catalog, backends = _merge_catalogs(local_catalog, remote_catalog)
                    if re.search(r"어떤 데이터|데이터셋|자료 목록|데이터 목록", question):
                        result = _blank("ok", f"적재된 용인 관련 공공데이터 {len(catalog)}종입니다.")
                        result.update(intent="catalog", result=[{"dataset_id": x["dataset_id"], "dataset_name": x["display_name"]} for x in catalog])
                        ai_usage["dataset_selection"] = "catalog"
                        ai_usage["query_plan"] = "rules"
                        return finalize(result)
                    selected, tied = _choose(question, catalog, context)
                    if selected or tied:
                        ai_usage["dataset_selection"] = "rules"
                    if not selected and model_key and not (context or {}).get("selection_id"):
                        try:
                            choices = tied if tied else catalog
                            choice = _llm_select(question, choices, context, model_key)
                            ai_usage["dataset_selection"] = "completed"
                            model_status = "completed"
                            if not choice.get("needs_clarification"):
                                selected = next((x for x in choices if x["dataset_id"] == choice.get("dataset_id")), None)
                                if selected:
                                    tied = []
                            elif not tied:
                                candidate_ids = set(choice.get("candidate_ids", [])[:5])
                                tied = [x for x in choices if x["dataset_id"] in candidate_ids][:5]
                        except (httpx.HTTPError, ValueError, KeyError, TypeError):
                            ai_usage["dataset_selection"] = "failed"
                    if tied:
                        result = _blank("clarification", "자료를 하나 선택해 주세요: " + ", ".join(x["display_name"] for x in tied))
                        result["result"] = [{"dataset_id": x["dataset_id"], "dataset_name": x["display_name"]} for x in tied]
                        return finalize(result)
                    if not selected:
                        result = _blank("clarification", "자료명을 특정해 주세요. ‘어떤 데이터가 있어?’로 목록을 볼 수 있습니다.")
                        return finalize(result)
                    backend = backends[selected["dataset_id"]]
                    if backend == "supabase":
                        if remote_cur is None:
                            remote_conn = stack.enter_context(_supabase_pool(remote_url).connection())
                            stack.enter_context(remote_conn.transaction())
                            remote_cur = stack.enter_context(remote_conn.cursor())
                            if not _prepare_reader(remote_cur):
                                return _blank("error", "Supabase 분석 연결은 읽기 전용 계정을 사용해야 합니다.")
                        cur = remote_cur
                    source = {"dataset_id": selected["dataset_id"], "dataset_name": selected["display_name"],
                              "provider": selected["provider"], "url": selected["portal_url"],
                              "database": backend,
                              "reference_date": str(selected["reference_date"]) if selected["reference_date"] else None,
                              "collected_at": selected["collected_at"].isoformat() if selected["collected_at"] else None,
                              "last_success_at": selected["last_success_at"].isoformat() if selected["last_success_at"] else None}
                    if selected["dataset_id"] == POPULATION_DATASET_ID and wants_population(question):
                        ai_usage["query_plan"] = "validated_population_contract"
                        try:
                            population = summarize_population(cur, question, source["reference_date"])
                        except PopulationContractError as exc:
                            return reply("unsupported", str(exc))
                        result = _blank("ok", population["answer"])
                        result.update(intent="population", result=population["result"],
                                      visualization=population["visualization"], filters=population["filters"],
                                      calculation=population["calculation"], limitations=population["limitations"],
                                      suggested_questions=population["suggested_questions"], sources=[source],
                                      model_status=model_status, context={"dataset_id": selected["dataset_id"]})
                        return add_insight(result)
                    if re.search(r"몇\s*명|인구.*(?:구별|분포|비교)", question):
                        return reply("unsupported", "이 자료에는 검증된 인구 합계 연산이 없습니다. ‘용인시 인구 분포 분석해줘’로 확인해 주세요.")
                    simple_count = _basic_count(question, selected)
                    columns = {} if simple_count else _validated_columns(cur, selected, backend)
                    plan = ({"dataset_id": selected["dataset_id"], "operation": "count",
                             "keyword": None, "year": None, "month": None, "date_field": None,
                             "filter_field": None, "filter_value": None, "group_field": None}
                            if simple_count else _rule_plan(question, selected, columns, context))
                    interpreter = "rules"
                    ai_usage["query_plan"] = "rules"
                    if model_key and not simple_count:
                        try:
                            candidate = _llm_plan(question, catalog, selected, columns, context, model_key)
                            if not (_validate(candidate, selected, columns) or
                                    _validate_question_alignment(candidate, question, selected, context)):
                                plan = candidate
                                interpreter = "llm"
                                ai_usage["query_plan"] = "completed"
                                model_status = "completed"
                            else:
                                ai_usage["query_plan"] = "rejected"
                        except (httpx.HTTPError, ValueError, KeyError, TypeError):
                            ai_usage["query_plan"] = "failed"
                    plan = _inherit_verified_context(plan, question, selected, columns, context)
                    if (plan["operation"] == "records" and not re.search(r"보여줘|목록|원본|행|찾아줘|검색", question)
                            and not plan.get("keyword")):
                        plan["operation"] = "overview"
                    # Rules do not silently reinterpret unsupported qualifiers.
                    if re.search(r"오늘|내일|이번|지난|다음|현재|예약|운영 중|평균|합계|순위|가장|추세|부터|까지", question):
                        return reply("unsupported", "현재 운영 상태·예약 가능 여부·범위/순위/평균 분석은 검증된 계약이 없어 지원하지 않습니다.")
                    if re.search(r"\d{4}년", question) and plan.get("year") is None:
                        return reply("unsupported", "연도 조건을 해석하지 못했습니다.")
                    if _explicit_district(question, selected) and not plan.get("filter_field"):
                        return reply("unsupported", "이 자료에 검증된 구 컬럼이 없어 지역 조건을 적용할 수 없습니다.")
                    reason = _validate(plan, selected, columns)
                    if reason:
                        return reply("unsupported", reason)
                    rows = _execute(cur, plan, columns)
                    op = plan["operation"]
                    answer = describe(selected["display_name"], plan, rows)
                    result = _blank("ok", answer)
                    result.update(intent=op, filters={k: v for k, v in plan.items() if k != "dataset_id" and v is not None},
                                  result=rows, sources=[source], interpreter=interpreter,
                                  suggested_questions=suggestions(selected["display_name"], columns),
                                  model_status=model_status,
                                  calculation={"measure": "현재 활성 적재 행 수", "method": op, "date_field": plan.get("date_field")},
                                  limitations=["등록 현황은 실제 운영 중·예약 가능·현재 행사를 뜻하지 않습니다."] +
                                              (["날짜가 없는 행은 기간 집계에서 제외합니다."] if op in {"monthly", "yearly"} else []) +
                                              (["표시 항목이 50개 제한에 도달해 뒤의 항목이 생략됐을 수 있습니다."]
                                               if op in {"monthly", "yearly", "group"} and len(rows) >= MAX_GROUPS else []),
                                  context={k: plan.get(k) for k in ("dataset_id", "keyword", "year", "month", "date_field", "filter_field", "filter_value")})
                    return add_insight(result)
    except psycopg.errors.QueryCanceled:
        return reply("unsupported", "자료가 커서 제한 시간 5초 안에 검증·집계를 마치지 못했습니다. 자료나 조건을 더 좁혀 주세요.")
    except (psycopg.Error, PoolClosed, PoolTimeout):
        return reply("error", "읽기 전용 데이터베이스 조회에 실패했습니다. 연결과 권한을 확인해 주세요.")

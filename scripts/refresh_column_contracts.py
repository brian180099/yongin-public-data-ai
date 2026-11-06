"""Validate selected local datasets and publish analysis-only column contracts."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from yongin_data.analysis.agent import _columns


ROOT = Path(__file__).resolve().parents[1]


def _writer_url() -> str:
    url = os.getenv("ANALYSIS_CONTRACT_WRITER_URL") or dotenv_values(
        ROOT / ".runtime" / "contract-maintenance.env").get("ANALYSIS_CONTRACT_WRITER_URL")
    if not url or not url.startswith("postgresql://"):
        raise RuntimeError("Git 제외 contract-maintenance.env에 로컬 관리 연결을 설정해야 합니다.")
    return url


def _fingerprint(cur, dataset_id: str) -> dict:
    cur.execute("""select source_last_success_at, source_run_id, source_raw_sha256
                   from (
                     select last_success_at as source_last_success_at,
                            source_run_id, source_raw_sha256
                     from analytics.dataset_source_fingerprints
                     where dataset_id=%s
                   ) f""", (dataset_id,))
    row = cur.fetchone()
    if not row or not all(row.values()):
        raise ValueError("missing_source_fingerprint")
    return dict(row)


def _record_attempt(conn, dataset_id: str, outcome: str, fingerprint: dict | None,
                    reason: str | None = None) -> None:
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("set local role yongin_collector_writer")
            cur.execute("""insert into analytics.dataset_contract_attempts
                           (source_database,dataset_id,outcome,failure_reason,source_run_id,source_raw_sha256)
                           values ('local',%s,%s,%s,%s,%s)""",
                        (dataset_id, outcome, reason,
                         fingerprint.get("source_run_id") if fingerprint else None,
                         fingerprint.get("source_raw_sha256") if fingerprint else None))


def refresh(conn, dataset_id: str) -> int:
    fingerprint = None
    try:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute("set local statement_timeout = '30000ms'")
                cur.execute("set local role yongin_collector_writer")
                fingerprint = _fingerprint(cur, dataset_id)
                columns = _columns(cur, dataset_id)
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("set local role yongin_collector_writer")
                if _fingerprint(cur, dataset_id) != fingerprint:
                    raise ValueError("source_changed_during_validation")
                cur.execute("""insert into analytics.dataset_contract_versions
                               (source_database,dataset_id,source_last_success_at,source_run_id,
                                source_raw_sha256,validated_at,validation_status)
                               values ('local',%s,%s,%s,%s,now(),'validated')
                               on conflict (source_database,dataset_id) do update set
                                 source_last_success_at=excluded.source_last_success_at,
                                 source_run_id=excluded.source_run_id,
                                 source_raw_sha256=excluded.source_raw_sha256,
                                 validated_at=excluded.validated_at,
                                 validation_status=excluded.validation_status""",
                            (dataset_id, fingerprint["source_last_success_at"],
                             fingerprint["source_run_id"], fingerprint["source_raw_sha256"]))
                cur.execute("""delete from analytics.dataset_column_contracts
                               where source_database='local' and dataset_id=%s""", (dataset_id,))
                for name, details in columns.items():
                    kind = details["kind"]
                    operations = ["count", "monthly", "yearly"] if kind == "date" else ["count", "group"]
                    cur.execute("""insert into analytics.dataset_column_contracts
                                   (source_database,dataset_id,column_name,kind,allowed_operations,
                                    date_format,group_values)
                                   values ('local',%s,%s,%s,%s,%s,%s)""",
                                (dataset_id, name, kind, operations, details.get("format"),
                                 Jsonb(details["values"]) if kind == "group" else None))
                cur.execute("""insert into analytics.dataset_contract_attempts
                               (source_database,dataset_id,outcome,source_run_id,source_raw_sha256)
                               values ('local',%s,'validated',%s,%s)""",
                            (dataset_id, fingerprint["source_run_id"], fingerprint["source_raw_sha256"]))
        return len(columns)
    except (psycopg.Error, ValueError) as exc:
        _record_attempt(conn, dataset_id, "failed", fingerprint, type(exc).__name__)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_id", nargs="+", help="실제 적재된 데이터셋 ID")
    args = parser.parse_args()
    with psycopg.connect(_writer_url(), connect_timeout=5, row_factory=dict_row) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute("select session_user")
                if cur.fetchone()["session_user"] != "yongin_collector_login":
                    raise RuntimeError("전용 관리 계정이 아닙니다.")
        failures = 0
        for dataset_id in args.dataset_id:
            try:
                count = refresh(conn, dataset_id)
                print(f"{dataset_id}: validated {count} columns")
            except (psycopg.Error, ValueError) as exc:
                print(f"{dataset_id}: failed {type(exc).__name__}")
                failures += 1
        if failures:
            raise SystemExit(1)


if __name__ == "__main__":
    main()

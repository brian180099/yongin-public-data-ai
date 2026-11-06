"""Opt-in check that the persisted analysis contract avoids JSONB profiling."""

import os

import psycopg
import pytest
from psycopg.rows import dict_row

from yongin_data.analysis import agent
from yongin_data.config import get_settings


pytestmark = pytest.mark.skipif(os.getenv("YONGIN_LIVE_TEST") != "1", reason="live DB opt in")


def test_forest_contract_survives_process_cache_miss(monkeypatch):
    agent._column_cache.clear()

    def fail_profile(_cursor, _dataset_id):
        raise AssertionError("persisted contract was not used")

    monkeypatch.setattr(agent, "_columns", fail_profile)
    with psycopg.connect(get_settings().database_url, row_factory=dict_row) as conn:
        with conn.transaction():
            conn.execute("set transaction read only")
            conn.execute("set local role yongin_analysis_reader")
            columns = agent._validated_columns(
                conn.cursor(), {"dataset_id": "portal_zip_forest_schedule"}, "local")
    assert any(value["kind"] == "date" for value in columns.values())

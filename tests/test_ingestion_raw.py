import hashlib
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from yongin_data.ingestion.raw import save_raw_artifact
from yongin_data.ingestion.sources import collect_data_go_kr_api


def test_save_raw_artifact_preserves_bytes_and_metadata(tmp_path) -> None:
    content = b'{"source": "unchanged"}'
    collected_at = datetime(2026, 11, 3, 13, 0, tzinfo=ZoneInfo("Asia/Seoul"))

    artifact = save_raw_artifact(
        dataset_id="example_data",
        source_url="https://example.test/data",
        content=content,
        extension="json",
        status_code=200,
        content_type="application/json",
        reference_date="2026-11-01",
        raw_root=tmp_path,
        collected_at=collected_at,
    )

    assert artifact.payload_path.read_bytes() == content
    metadata = json.loads(artifact.metadata_path.read_text(encoding="utf-8"))
    assert metadata["sha256"] == hashlib.sha256(content).hexdigest()
    assert metadata["collected_at"] == collected_at.isoformat()
    assert metadata["reference_date"] == "2026-11-01"
    assert metadata["source_url"] == "https://example.test/data"


def test_data_go_kr_collector_requires_key(tmp_path) -> None:
    try:
        collect_data_go_kr_api(
            dataset_id="example_data",
            source_url="https://example.test/data",
            service_key=" ",
            raw_root=tmp_path,
        )
    except ValueError as exc:
        assert "DATA_GO_KR_SERVICE_KEY" in str(exc)
    else:
        raise AssertionError("missing public data key should fail before an HTTP request")

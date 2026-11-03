"""Raw response collection with immutable payload and sidecar metadata."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import httpx

from yongin_data.config import PROJECT_ROOT


KST = ZoneInfo("Asia/Seoul")
DEFAULT_RAW_ROOT = PROJECT_ROOT / "data" / "raw"
_SAFE_NAME = re.compile(r"^[a-z0-9_]+$")


@dataclass(frozen=True)
class RawArtifact:
    """Paths and identifiers for one saved source response."""

    payload_path: Path
    metadata_path: Path
    sha256: str
    collected_at: datetime


def _validate_name(value: str, *, label: str) -> str:
    if not _SAFE_NAME.fullmatch(value):
        raise ValueError(f"{label} must contain only lowercase letters, digits, and underscores")
    return value


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary.write(content)
        temporary_path = Path(temporary.name)
    temporary_path.replace(path)


def save_raw_artifact(
    *,
    dataset_id: str,
    source_url: str,
    content: bytes,
    extension: str,
    status_code: int,
    content_type: str | None,
    reference_date: str | None = None,
    raw_root: Path = DEFAULT_RAW_ROOT,
    collected_at: datetime | None = None,
) -> RawArtifact:
    """Save source bytes unchanged and write collection metadata beside them."""

    dataset_id = _validate_name(dataset_id, label="dataset_id")
    extension = _validate_name(extension.lower(), label="extension")
    collected_at = collected_at or datetime.now(KST)
    if collected_at.tzinfo is None:
        raise ValueError("collected_at must be timezone-aware")

    digest = hashlib.sha256(content).hexdigest()
    timestamp = collected_at.strftime("%Y%m%dT%H%M%S%z")
    stem = f"{timestamp}_{digest[:12]}"
    dataset_dir = raw_root / dataset_id
    payload_path = dataset_dir / f"{stem}.{extension}"
    metadata_path = dataset_dir / f"{stem}.metadata.json"

    metadata = {
        "dataset_id": dataset_id,
        "source_url": source_url,
        "collected_at": collected_at.isoformat(),
        "reference_date": reference_date,
        "http_status": status_code,
        "content_type": content_type,
        "byte_count": len(content),
        "sha256": digest,
        "payload_file": payload_path.name,
    }
    _write_atomic(payload_path, content)
    _write_atomic(
        metadata_path,
        (json.dumps(metadata, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
    )
    return RawArtifact(payload_path, metadata_path, digest, collected_at)


def fetch_raw_artifact(
    *,
    dataset_id: str,
    source_url: str,
    extension: str,
    params: Mapping[str, Any] | None = None,
    reference_date: str | None = None,
    timeout: float = 20.0,
    raw_root: Path = DEFAULT_RAW_ROOT,
) -> RawArtifact:
    """Fetch a public source with a timeout and preserve a successful response."""

    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        response = client.get(source_url, params=params)
        response.raise_for_status()
    return save_raw_artifact(
        dataset_id=dataset_id,
        source_url=source_url,
        content=response.content,
        extension=extension,
        status_code=response.status_code,
        content_type=response.headers.get("content-type"),
        reference_date=reference_date,
        raw_root=raw_root,
    )

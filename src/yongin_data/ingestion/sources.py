"""Source-specific entry points for the three MVP datasets."""

from __future__ import annotations

from pathlib import Path

from yongin_data.ingestion.raw import DEFAULT_RAW_ROOT, RawArtifact, fetch_raw_artifact


SUJI_PROGRAMS_URL = "https://www.sujigu.go.kr/lmth/04life0703.asp"
PUBLIC_FACILITIES_API_URL = (
    "https://api.data.go.kr/openapi/tn_pubr_public_pblfclt_opn_info_api"
)
CITY_PARKS_API_URL = "https://api.data.go.kr/openapi/tn_pubr_public_cty_park_info_api"


def collect_suji_programs_page(
    *, raw_root: Path = DEFAULT_RAW_ROOT, timeout: float = 20.0
) -> RawArtifact:
    """Collect the current official program page as unmodified HTML."""

    return fetch_raw_artifact(
        dataset_id="suji_programs",
        source_url=SUJI_PROGRAMS_URL,
        extension="html",
        timeout=timeout,
        raw_root=raw_root,
    )


def collect_data_go_kr_api(
    *,
    dataset_id: str,
    source_url: str,
    service_key: str,
    raw_root: Path = DEFAULT_RAW_ROOT,
    page_no: int = 1,
    num_rows: int = 1000,
    timeout: float = 20.0,
) -> RawArtifact:
    """Collect one JSON page without persisting or logging the API key."""

    if not service_key.strip():
        raise ValueError("DATA_GO_KR_SERVICE_KEY is required")
    if page_no < 1 or not 1 <= num_rows <= 1000:
        raise ValueError("page_no must be positive and num_rows must be between 1 and 1000")
    return fetch_raw_artifact(
        dataset_id=dataset_id,
        source_url=source_url,
        extension="json",
        params={
            "serviceKey": service_key,
            "pageNo": page_no,
            "numOfRows": num_rows,
            "type": "json",
        },
        timeout=timeout,
        raw_root=raw_root,
    )


def collect_public_facilities(
    service_key: str, *, raw_root: Path = DEFAULT_RAW_ROOT
) -> RawArtifact:
    return collect_data_go_kr_api(
        dataset_id="public_facilities",
        source_url=PUBLIC_FACILITIES_API_URL,
        service_key=service_key,
        raw_root=raw_root,
    )

def collect_city_parks(
    service_key: str, *, raw_root: Path = DEFAULT_RAW_ROOT
) -> RawArtifact:
    return collect_data_go_kr_api(
        dataset_id="city_parks",
        source_url=CITY_PARKS_API_URL,
        service_key=service_key,
        raw_root=raw_root,
    )

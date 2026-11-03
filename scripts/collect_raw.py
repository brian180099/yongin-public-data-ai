"""Collect raw source responses for the selected MVP datasets."""

from __future__ import annotations

import argparse
import logging
import sys

from yongin_data.config import configure_logging, get_settings
from yongin_data.ingestion.sources import (
    collect_city_parks,
    collect_public_facilities,
    collect_suji_programs_page,
)


logger = logging.getLogger("collect_raw")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset",
        choices=("suji_programs", "public_facilities", "city_parks", "all"),
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    settings = get_settings()
    collectors = []
    if args.dataset in ("suji_programs", "all"):
        collectors.append(("suji_programs", collect_suji_programs_page))
    if args.dataset in ("public_facilities", "all"):
        if not settings.data_go_kr_service_key:
            logger.error(
                "공공데이터 API 키가 없어 public_facilities 수집을 실행하지 않았습니다."
            )
            return 2
        collectors.append(
            (
                "public_facilities",
                lambda: collect_public_facilities(settings.data_go_kr_service_key or ""),
            )
        )
    if args.dataset in ("city_parks", "all"):
        if not settings.data_go_kr_service_key:
            logger.error("공공데이터 API 키가 없어 city_parks 수집을 실행하지 않았습니다.")
            return 2
        collectors.append(
            ("city_parks", lambda: collect_city_parks(settings.data_go_kr_service_key or ""))
        )

    current_dataset = "not_started"
    try:
        for dataset_id, collector in collectors:
            current_dataset = dataset_id
            artifact = collector()
            logger.info(
                "%s 원본 저장 성공: file=%s sha256=%s",
                dataset_id,
                artifact.payload_path.name,
                artifact.sha256[:12],
            )
    except Exception as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        logger.error(
            "원본 수집 실패: dataset=%s type=%s http_status=%s",
            current_dataset,
            type(exc).__name__,
            status_code if status_code is not None else "not_available",
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

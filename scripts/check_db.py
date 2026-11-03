"""Check PostgreSQL connectivity with a safe SELECT 1 query."""

from __future__ import annotations

import logging
import sys

from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError

from yongin_data.config import configure_logging, get_settings
from yongin_data.db import check_connection, create_db_engine


logger = logging.getLogger("check_db")


def main() -> int:
    configure_logging()
    settings = get_settings()
    if not settings.database_url:
        logger.warning("DATABASE_URL이 없어 DB 연결을 검증하지 않았습니다.")
        return 2

    engine = None
    try:
        engine = create_db_engine(settings)
        if check_connection(engine):
            logger.info("PostgreSQL 연결과 SELECT 1 검사가 성공했습니다.")
            return 0
        logger.error("PostgreSQL이 예상하지 못한 SELECT 1 결과를 반환했습니다.")
    except OperationalError:
        logger.error(
            "PostgreSQL 연결에 실패했습니다. 호스트, 포트, 사용자, 비밀번호, "
            "SSL 설정과 Supabase 네트워크 상태를 확인하세요."
        )
    except (DBAPIError, SQLAlchemyError):
        logger.error("DB 검사 중 오류가 발생했습니다. DATABASE_URL과 DB 상태를 확인하세요.")
    finally:
        if engine is not None:
            engine.dispose()
    return 1


if __name__ == "__main__":
    sys.exit(main())

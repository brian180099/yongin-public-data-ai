# 공공데이터 분석 서비스

> **현재 경로 (2026-11-06):** 제공기관이 `경기도 용인시`인 검증된 자료를 로컬 PostgreSQL과 Supabase의 읽기 전용 `analytics` 뷰에서 확인한다. 공통 자료는 마지막 정상 적재 시각이 더 최신인 DB를 사용하고, 같으면 로컬 DB를 사용한다. <http://localhost:8501>의 채팅은 전용 n8n `/webhook/yongin-question-agent-v1`을 거쳐 이 저장소의 분석 서비스로 전달된다. 로컬 대량 CSV는 기준 스냅샷이고 오른쪽 수집 프로젝트의 Supabase 갱신은 별도로 운영된다. 수집·로컬 DB 운영은 [수집기 운영 문서](../yongin-public-data-collector/docs/LOCAL_POSTGRESQL.md)를 참조한다.

이 저장소는 사용자의 공공데이터 질문을 해석하고, 조회 계획을 검증하고, 계산 결과를 한국어로 설명합니다. **현재 MVP 분석 지역은 용인시**이며, 서비스 이름이나 앞으로의 분석 범위를 용인시로 고정하지 않습니다. 별도 `yongin-public-data-collector` 저장소는 현재 용인시 자료의 원본 수집·검증·현재 레코드·변경 이력을 관리합니다. 여기서는 수집기 DB를 수정하지 않습니다.

## 현재 경로

```text
웹 http://localhost:8501 → n8n /webhook/yongin-question-agent-v1
                                      ↓
                         이 저장소의 analysis API → analysis.agent → 최신 자료가 있는 analytics 읽기 뷰
```

이 웹은 전용 Webhook을 호출하고 n8n은 `yongin-question-agent:8091/v1/analyze`로 전달합니다. 옛 `yongin-analysis-v1` Webhook은 2026-11-06 비활성화했고 `yongin-analysis` 컨테이너도 중지했습니다. 옛 워크플로 정의와 실행 컨테이너는 삭제하지 않았으며, 수집 프로젝트에서 `docker compose up`을 실행하면 해당 컨테이너가 다시 시작될 수 있습니다. 이 웹의 조회·계산·답변은 이 저장소의 분석 서비스 한 곳에서 수행합니다.

## 실행

`.runtime/analysis.env`에 호스트 테스트용 로컬 `DATABASE_URL`과 선택적 `SUPABASE_ANALYSIS_DB_URL`을 설정합니다. 두 URL 모두 `yongin_analysis_login` 읽기 전용 계정이어야 합니다. Docker 분석 서비스는 Git 제외 `.runtime/analysis-container.env`를 읽습니다. 현재 OpenAI 키는 사용자가 넣은 `.env`에서 이 컨테이너 비밀 파일로 옮겨 적용했습니다. 키를 교체하면 컨테이너 비밀 파일도 갱신하고 서비스를 다시 생성해야 합니다. 키가 없으면 제한된 규칙 기반 해석만 사용합니다. 비밀 값은 화면·로그·Git에 표시하지 않습니다.

```powershell
python -m pip install -e ".[dev]"
docker compose -f compose.analysis.yaml up -d --build
```

컨테이너는 기존 `n8n_default` Docker 네트워크를 사용합니다. 웹은 <http://localhost:8501>, API 상태는 <http://localhost:8091/health>입니다. 이 웹 전용 n8n 워크플로 정의는 `workflows/n8n/yongin-question-agent-v1.json`, ID는 `YNGN03QuestionAgentV1`입니다. 기존 `YNGN02AnalysisV1`을 덮어쓰지 마세요. 배포 시 워크플로를 가져와 게시한 뒤 n8n을 재시작하고 전용 Webhook을 시험합니다. 기존 워크플로 백업은 Git 제외 `.tmp/n8n-analysis-before-question-agent.json`에 보관했습니다.

## 지원 범위와 근거

데이터셋 목록은 양쪽 DB의 `analytics.dataset_sources`와 활성 `analytics.current_dataset_records`에서 동적으로 읽고 최대 30초만 메모리에 보관합니다. ID·건수는 코드에 고정하지 않습니다. 동일 자료가 양쪽에 있으면 `last_success_at`(없으면 `collected_at`)을 비교해 최신본을 선택하고, 같은 시각이면 로컬을 사용합니다. Supabase 읽기 연결이 설정됐지만 확인할 수 없으면 오래된 로컬 값을 최신이라고 답하지 않고 오류를 반환합니다. 현재 비교에서 로컬 316개, Supabase 246개, 공통 246개이며 공통 자료의 정상 적재 시각은 모두 같았습니다. 자료명이 모호하면 후보를 제시합니다. 정확한 전체 건수, 원본 값에 포함된 문구 검색, 검증된 날짜 컬럼의 연도·월 집계, 검증된 지역·분류 컬럼별 건수를 지원합니다. 날짜/분류 컬럼은 자료별 전체 값의 형식과 종류 수를 검사합니다. 검사 결과는 해당 수집 버전에서만 재사용하고 수집 시각이 바뀌면 다시 검증합니다. 데이터 기준일은 행사·일정 날짜로 간주하지 않습니다. 지원하지 않는 조건을 전체 건수로 바꾸지 않습니다.

### 분석 컬럼 계약

로컬 DB의 `analytics.dataset_contract_versions`, `analytics.dataset_column_contracts`에는 검증된 날짜·분류 컬럼, 허용 연산, 원본 SHA-256, 수집 실행 ID, 마지막 정상 적재 시각, 검증 시각을 저장합니다. 질문 처리에서는 `analytics.dataset_source_fingerprints`와 세 근거가 모두 일치할 때만 저장된 계약을 사용합니다. 일치하지 않으면 원본 값을 다시 검사합니다. 검증 작업이 실패하면 이전 정상 계약을 유지하고 `analytics.dataset_contract_attempts`에 실패 종류를 남깁니다. 분석 서비스의 DB 계정은 이 테이블을 읽을 수만 있습니다.

현재 계약은 MVP 세 자료(`portal_zip_forest_schedule`, `portal_zip_library_calendar`, `giheung_events`)에 생성했습니다. 다른 로컬 자료와 Supabase에서 더 최신인 자료는 기존의 제한된 메모리 캐시와 전체 값 검사를 사용합니다. 계약 갱신은 관리 작업이며 질문 요청에서 DB 쓰기를 하지 않습니다.

```powershell
# 한 번만 적용하는 분석 스키마 마이그레이션 (로컬 DB 관리자)
docker cp sql/001_analysis_column_contracts.sql yongin-local-postgres:/tmp/001_analysis_column_contracts.sql
docker exec yongin-local-postgres psql -U postgres -d yongin -v ON_ERROR_STOP=1 -f /tmp/001_analysis_column_contracts.sql

# Git 제외 .runtime/contract-maintenance.env의 ANALYSIS_CONTRACT_WRITER_URL 사용
python scripts/refresh_column_contracts.py portal_zip_forest_schedule portal_zip_library_calendar giheung_events
```

답변에는 데이터셋명, 제공기관, 공식 포털 URL, 데이터 기준일, 수집일, 필터, 계산 방법을 담습니다. 등록된 기록 수는 실제 운영 중·예약 가능·현재 행사 수를 뜻하지 않습니다. 원본 행은 최대 20건과 행당 4KB로 제한합니다. DB 트랜잭션은 읽기 전용이며 분석 역할로 전환하고 명령 시간은 5초로 제한합니다. 사용자/모델의 임의 SQL은 실행하지 않습니다.

OpenAI 키가 있으면 Responses API의 엄격한 JSON Schema로 복잡한 자료 선택과 조회 계획만 받습니다. 명확한 단순 전체 건수는 규칙으로 바로 처리합니다. 계획의 데이터셋·컬럼·조건·연산과 질문 원문의 일치 여부를 서버에서 재검증합니다. 모델 계획이 유효하지 않거나 호출에 실패하면 응답 메타데이터에 상태를 표시하고 가능한 규칙 기반 질문만 처리합니다. **실제 OpenAI 호출과 전용 n8n 경유 응답을 검증했습니다.** 규칙 기반 해석은 명시적 자료명·따옴표 검색어·연도/월·단순 후속 질문을 우선 지원합니다. 현재 운영 상태, 예약 가능 여부, 임의 기간, 평균·순위, 다중 자료 결합은 지원하지 않습니다.

웹에서는 예시 질문을 누르거나 채팅에 입력합니다. 자료가 모호하면 후보 버튼을 눌러 원래 질문을 다시 실행할 수 있습니다. 답변은 건수·표/차트, 적용 조건, 계산 방식, 데이터셋명·제공기관·기준일·수집일·공식 포털 링크, 실제 모델 사용 상태를 함께 보여 줍니다. 직전 성공한 자료의 검증된 조건만 명시적 후속 질문에 이어받습니다. 자료 목록은 화면에서 검색할 수 있습니다.

## 실제 검증 질문

- `숲체험일정은 몇 건이야?` → 8,830건
- `도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?` → 1건
- `어떤 데이터가 있어?` → 현재 조회 가능한 용인 관련 자료 목록
- `2025년 숲체험일정은 몇 건이야?` → `숲체험일정시작일` 기준 0건 (값은 2015~2020년)

```powershell
python -m pytest
$env:YONGIN_LIVE_TEST='1'; python -m pytest tests/test_agent_live.py
$env:YONGIN_LLM_LIVE_TEST='1'; python -m pytest tests/test_agent_openai_live.py
$env:YONGIN_WEBHOOK_LIVE_TEST='1'; python -m pytest tests/test_webhook_live.py
```

라이브 테스트는 실제 읽기 전용 DB 연결을 사용하며 기본 테스트에서는 건너뜁니다. 수집기 원본·현재 레코드와 Git 이력은 변경하지 않았습니다.

# 용인 공공데이터 질문 분석 에이전트

> **현재 경로 (2026-11-05):** 제공기관이 `경기도 용인시`인 검증된 CSV의 목록과 현재 레코드를 로컬 PostgreSQL에서 읽는다. Supabase Free의 이전 적재분은 보존하지만 웹 질의의 운영 DB는 로컬 DB다. <http://localhost:8501>의 채팅은 n8n `/webhook/yongin-analysis-v1`을 거쳐 이 저장소의 분석 서비스로 전달된다. 새 CSV는 기준 스냅샷이며 정기 갱신은 아직 활성화하지 않았다. 수집·로컬 DB 운영은 [수집기 운영 문서](../yongin-public-data-collector/docs/LOCAL_POSTGRESQL.md)를 참조한다.

이 저장소가 용인시 제공 공공데이터 질문의 해석, 조회 계획 검증, 계산, 한국어 답변을 담당합니다. 별도 `yongin-public-data-collector` 저장소는 원본 수집·검증·현재 레코드·변경 이력을 관리합니다. 여기서는 수집기 DB를 수정하지 않습니다.

## 현재 경로

```text
웹 http://localhost:8501 → n8n /webhook/yongin-analysis-v1
                                      ↓
                         이 저장소의 analysis API → analysis.agent → 로컬 analytics 읽기 뷰
```

이전에는 웹이 `localhost:8090/ask`를 호출하고, n8n이 수집 프로젝트의 `yongin-analysis` 서비스로 전달했습니다. 현재 웹은 n8n Webhook을 호출하고 n8n은 `yongin-question-agent:8091/v1/analyze`로 전달합니다. 이전 분석 컨테이너는 중지했습니다. n8n은 질문 전달과 실행 기록만 맡고, 실제 조회·계산·답변은 한 서비스에서 수행합니다.

## 실행

`.runtime/analysis.env`에 `yongin_analysis_login` 읽기 전용 PostgreSQL 계정의 `DATABASE_URL`을 설정합니다. 파일은 Git에서 제외되고 기존 `.env`보다 먼저 읽습니다. OpenAI 키는 선택적으로 같은 파일에 `OPENAI_API_KEY`로 설정합니다. 키가 없으면 제한된 규칙 기반 해석만 사용합니다.

```powershell
python -m pip install -e ".[dev]"
docker compose -f compose.analysis.yaml up -d --build
```

컨테이너는 기존 `n8n_default` Docker 네트워크를 사용합니다. 웹은 <http://localhost:8501>, API 상태는 <http://localhost:8091/health>입니다. n8n 워크플로 정의는 `workflows/n8n/yongin-analysis-v1.json`이며, 기존 ID `YNGN02AnalysisV1`을 유지합니다. 재배치할 때는 기존 워크플로를 먼저 백업하고 같은 ID로 가져온 뒤 게시·재시작·Webhook 시험을 하세요. 전환 전 백업은 로컬 `.tmp/n8n-analysis-before.json`에 보관했습니다.

## 지원 범위와 근거

데이터셋 목록은 `analytics.dataset_sources`와 활성 `analytics.current_dataset_records`에서 매 요청 읽습니다. ID·건수는 코드에 고정하지 않습니다. 자료명이 모호하면 후보를 제시합니다. 정확한 전체 건수, 원본 값에 포함된 문구 검색, 검증된 날짜 컬럼의 연도·월 집계, 검증된 지역·분류 컬럼별 건수를 지원합니다. 날짜/분류 컬럼은 자료별 전체 값의 형식과 종류 수를 검사합니다. 데이터 기준일은 행사·일정 날짜로 간주하지 않습니다. 지원하지 않는 조건을 전체 건수로 바꾸지 않습니다.

답변에는 데이터셋명, 제공기관, 공식 포털 URL, 데이터 기준일, 수집일, 필터, 계산 방법을 담습니다. 등록된 기록 수는 실제 운영 중·예약 가능·현재 행사 수를 뜻하지 않습니다. 원본 행은 최대 20건과 행당 4KB로 제한합니다. DB 트랜잭션은 읽기 전용이며 분석 역할로 전환하고 명령 시간은 5초로 제한합니다. 사용자/모델의 임의 SQL은 실행하지 않습니다.

OpenAI 키가 있으면 Responses API의 엄격한 JSON Schema로 조회 계획만 받습니다. 계획의 데이터셋·컬럼·조건·연산을 서버에서 재검증합니다. **실제 OpenAI 호출은 키 설정 후 미검증**입니다. 규칙 기반 해석은 명시적 자료명·따옴표 검색어·연도/월·단순 후속 질문을 우선 지원합니다. 현재 운영 상태, 예약 가능 여부, 임의 기간, 평균·순위, 다중 자료 결합은 지원하지 않습니다.

## 실제 검증 질문

- `숲체험일정은 몇 건이야?` → 8,830건
- `도서관 달력에서 ‘유아 클레이 특강’은 몇 건이야?` → 1건
- `어떤 데이터가 있어?` → 현재 조회 가능한 용인 관련 자료 목록
- `2025년 숲체험일정은 몇 건이야?` → `숲체험일정시작일` 기준 0건 (값은 2015~2020년)

```powershell
python -m pytest
$env:YONGIN_LIVE_TEST='1'; python -m pytest tests/test_agent_live.py
```

라이브 테스트는 실제 읽기 전용 DB 연결을 사용하며 기본 테스트에서는 건너뜁니다. 수집기 원본·현재 레코드와 Git 이력은 변경하지 않았습니다.

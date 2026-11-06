# 에이전트 작업 로그 (Claude Code ↔ Codex)

Claude Code와 Codex가 이 저장소에서 수행한 작업을 시간순으로 기록해 서로 인수인계하는 문서다.

## 작성 규칙

- 작업을 마칠 때마다 **맨 아래에 새 항목을 추가**한다. 기존 항목은 수정·삭제하지 않는다. 정정이 필요하면 새 항목에서 정정한다.
- 시간은 KST(`+0900`) 기준 `YYYY-MM-DD HH:MM`으로 적는다.
- 주체는 `Claude Code` 또는 `Codex`로 적는다. 사용자가 직접 한 작업은 `사용자`로 적는다.
- 직접 실행·확인한 것만 "완료"로 적는다. 확인하지 못한 것은 "미검증"으로 명시한다.
- 비밀값(API 키, 접속 문자열, 비밀번호)과 원본 데이터 내용은 적지 않는다.
- 관련 커밋이 있으면 해시를 적는다.

### 항목 양식

```markdown
## YYYY-MM-DD HH:MM · 주체

- **요약**: 한두 줄로 무엇을 했는지
- **변경 파일**: 경로 목록 (없으면 "없음")
- **커밋**: 해시 또는 "미커밋"
- **검증**: 실행한 테스트·확인 결과
- **다음 작업자에게**: 이어서 할 일, 주의점
```

---

## 2026-11-03 ~ 2026-11-05 · Codex (이전 작업 요약)

- **요약**: 저장소 초기화부터 용인시 공공데이터 질문 분석 서비스 구현까지 진행. 세부 내용은 [CLAUDE_CODE_HANDOFF.md](CLAUDE_CODE_HANDOFF.md) 참조.
- **커밋**: `55e4f48` → `bb2f860` → `175f4b3` → `edc7fb3` → `1de02b3` → `ee21911` → `68021f1` → `8afb09e`
- **다음 작업자에게**: 핸드오프 문서 11절의 권장 시작점은 "분석 가능 컬럼 계약 캐시" 설계·구현.

## 2026-11-05 17:32 · Claude Code

- **요약**: 핸드오프 문서와 두 저장소 커밋 이력을 검토해 진행 상황을 브리핑. Codex와 주고받을 작업 로그 문서(이 파일)를 새로 만듦.
- **변경 파일**: `docs/AGENT_WORKLOG.md` (신규)
- **커밋**: 미커밋. `docs/CLAUDE_CODE_HANDOFF.md`도 아직 미추적 상태
- **검증**: 코드 변경 없음. `docker ps`로 컨테이너 6개(web, agent, collector, postgres, n8n, n8n-runners)가 실행 중인 것만 확인. 테스트는 실행하지 않음.
- **다음 작업자에게**: 아직 기능 작업은 시작하지 않음. 다음 단계는 핸드오프 11절의 컬럼 계약 캐시 작업.

## 2026-11-05 17:40 · Claude Code

- **요약**: Codex도 작업 로그를 쓰도록 `AGENTS.md`에 "작업 후 docs/AGENT_WORKLOG.md에 항목 추가, 시작 시 먼저 읽기" 규칙을 추가.
- **변경 파일**: `AGENTS.md`
- **커밋**: 미커밋
- **검증**: 문서 변경만. 코드/테스트 영향 없음.
- **다음 작업자에게**: `AGENTS.md`, `docs/AGENT_WORKLOG.md`, `docs/CLAUDE_CODE_HANDOFF.md` 3개가 미커밋/미추적 상태. 커밋 시점은 사용자 지시 대기 중.

## 2026-11-05 23:38 · Codex

- **요약**: 두 저장소의 코드·문서·실행 컨테이너·Git 상태를 다시 확인하고, 현재 아키텍처, 데이터 현황, 검증 결과, 보안 불변 조건, 운영 명령, 후속 개발 우선순위와 완료 기준을 담은 Claude Code 인수인계 프롬프트를 작성함. Claude Code가 만든 공동 작업 로그와 AGENTS 규칙을 검토해 보존함.
- **변경 파일**: `docs/CLAUDE_CODE_HANDOFF.md`, `docs/AGENT_WORKLOG.md`, `AGENTS.md`
- **커밋**: 이 항목 작성 시점 미커밋
- **검증**: 두 저장소 `main`과 `origin/main` 일치 여부, 6개 관련 컨테이너 실행 상태, 인수인계 문서의 비밀 패턴 부재와 `git diff --check`를 확인함. 기능 코드는 변경하지 않아 테스트를 재실행하지 않음.
- **다음 작업자에게**: 사용자에게 별도 비밀 입력을 요구하지 말고, 인수인계 11절의 P0 분석 가능 컬럼 계약 캐시부터 착수할 것. 작업 종료 시 이 로그 맨 아래에 새 항목을 추가할 것.

## 2026-11-06 07:11 · Codex

- **요약**: 사용자의 Codex 단독 작업 방침에 따라 두 저장소의 현재 코드·기획 문서·운영 경로·Git·컨테이너를 점검하고, 실제 DB/OpenAI/n8n 테스트와 대표 질문을 실행해 부족한 부분의 우선순위를 정리함.
- **변경 파일**: `docs/CODEX_AUDIT_2026-11-06.md`, `docs/AGENT_WORKLOG.md`
- **커밋**: 미커밋(이번 요청은 현황 점검·브리핑)
- **검증**: 분석 기본 테스트 통과, 수집기 기본 테스트 59개 통과. 분석 전체 라이브 테스트 첫 실행 1개 실패(숲체험 건수 `unsupported`), 재실행 전체 통과. 웹/API HTTP 200, n8n Webhook 자료 목록 316개. 키 없이 대표 건수·검색·2025년 조건·안전 거절을 개별 검증. 브라우저 자동화 연결 실패로 UI 클릭은 미검증.
- **다음 작업자에게**: 첫 라이브 실패를 무시하지 말고 `_basic_count()`와 `_columns()` 경로를 계측해 간헐적 5초 제한 원인을 확인할 것. 원본을 바꾸지 않는 분석용 컬럼 계약 캐시, 운영 백업, UI 실사용 검증을 순서대로 진행할 것. Claude Code 인수인계 문서와 구 Supabase 문서는 현 운영 기준이 아님.

## 2026-11-06 11:09 · Codex

- **요약**: 사용자 지시에 따라 이 저장소를 질문 분석·응답 주체로 유지하면서 오른쪽 수집 프로젝트와 충돌하지 않는 전용 n8n Webhook을 배포했다. 단순 건수 경로와 자료·컬럼 캐시를 보완하고, 로컬·Supabase의 읽기 전용 카탈로그를 비교해 최신 적재 시각의 DB를 선택하도록 했다. 웹 제품명을 `공공데이터 분석 서비스`로 고치고 용인시를 현재 MVP 지역으로 표시했다.
- **변경 파일**: `app.py`, `README.md`, `compose.analysis.yaml`, `pyproject.toml`, `requirements.lock`, `src/yongin_data/analysis/agent.py`, `src/yongin_data/analysis/api.py`, `src/yongin_data/config.py`, `tests/test_agent.py`, `tests/test_agent_live.py`, `tests/test_agent_openai_live.py`, `tests/test_config.py`, `tests/test_web_ui.py`, `tests/test_webhook_live.py`, `workflows/n8n/yongin-question-agent-v1.json`, `docs/CODEX_AUDIT_2026-11-06.md`, `docs/AGENT_WORKLOG.md` (구 Webhook 정의는 전용 파일로 이동).
- **커밋**: 이 항목 작성 시점 미커밋.
- **검증**: 로컬 316개·Supabase 246개, 공통 246개 및 동일 적재 시각을 두 읽기 전용 계정으로 확인했다. Supabase 강제 조회에서 숲체험 8,830건을 확인했다. 실제 DB/OpenAI/n8n 전체 테스트 32개 통과, 명칭 수정 후 기본 테스트 통과, 웹/API HTTP 200 및 API 제목 확인. Streamlit 화면 자동 테스트 통과. 브라우저 자동화는 URL 확인 실패로 중단돼 육안 클릭 검증은 미완료.
- **다음 작업자에게**: 운영 경로는 `localhost:8501` → `yongin-question-agent-v1` → 이 저장소 API다. 오른쪽 `localhost:8090` 분석 서비스와 미커밋 수집 코드는 건드리지 않았다. 재시작 직후 첫 요청은 약 10.5초, 이후 약 2.1초였다. 브라우저 실사용 확인, DB 백업·복구 운영, 오래된 문서 정리는 남아 있다.

## 2026-11-06 11:40 · Claude Code

- **요약**: `.env.example`을 현재 코드에 맞게 정리. 죽은 설정 `ANALYSIS_SERVICE_URL` 제거(`client.py` 삭제로 미사용), `config.py`/`agent.py`가 실제로 읽는 `SUPABASE_ANALYSIS_DB_URL`과 `OPENAI_MODEL`을 설명과 함께 추가.
- **변경 파일**: `.env.example`
- **커밋**: 미커밋
- **검증**: grep으로 `ANALYSIS_SERVICE_URL`이 `.py` 어디에서도 안 읽히는 것, `SUPABASE_ANALYSIS_DB_URL`은 agent.py:504, `OPENAI_MODEL`은 agent.py:330/config.py에서 읽히는 것 확인. `.env`(비밀)는 변경하지 않음. 코드 변경 없어 테스트 미실행.
- **다음 작업자에게**: 실제 `.env`에는 `DATABASE_URL`, `OPENAI_API_KEY`만 설정돼 있음. `SUPABASE_ANALYSIS_DB_URL`이 비어 있어 로컬·Supabase 카탈로그 비교는 현재 로컬 단일 경로로만 동작함. Supabase 비교가 필요하면 `.env`에 해당 키를 채워야 함.

## 2026-11-06 12:10 · Claude Code

- **요약**: n8n 워크플로 4종 파일과 실행 중인 webhook을 실제 점검. 신규 경로(`yongin-question-agent-v1`→question-agent:8091)와 구 경로(`yongin-analysis-v1`→yongin-analysis:8090)가 둘 다 활성인 이중 경로를 확인. 구 서비스는 폐기된 옛 MVP 범위(생활여가·문화·체육 274종)로 응답. 사용자 의도(2-에이전트)에는 구 경로가 불필요함을 정리.
- **변경 파일**: 없음(점검·분석만). 앞서 `.env.example`은 브랜치 `chore/env-example-sync`의 커밋 `0bfe11b`에 있음.
- **커밋**: 미커밋(점검)
- **검증**: 두 webhook에 동일 질문 POST → 신규는 316종 기준 명확화 응답, 구는 274종 즉답. `yongin-analysis` 컨테이너 `Up(healthy)`, `compose.collector.yaml`에서 정의 확인. 웹(app.py:11)은 신규 webhook만 호출함을 확인.
- **다음 작업자에게**: Codex가 이중 경로(구 `yongin-analysis` 컨테이너 + `yongin-analysis-v1` webhook) 정리 필요. 이 저장소 브랜치 전략: `main`=2988869(기능 커밋 없음), 내 문서/설정 커밋은 `chore/env-example-sync`. Codex의 11-06 기능작업(app.py 등 13개 수정+신규 3개)은 여전히 미커밋 상태로 보존됨.

## 2026-11-06 12:22 · Codex

- **요약**: 사용자 요청에 따라 구 n8n 질문 Webhook과 수집 저장소의 옛 분석 컨테이너를 중지하고, 질문 웹은 `YNGN03QuestionAgentV1` 한 경로만 사용하도록 확인했다. 로컬 `analytics` 스키마에 원본 SHA·수집 실행 ID·검증 시각과 허용 컬럼을 담는 분석 전용 계약 캐시를 추가하고 MVP 자료 3개를 검증·적재했다. 원본·현재 레코드는 수정하지 않았다.
- **변경 파일**: `README.md`, `sql/001_analysis_column_contracts.sql`, `scripts/refresh_column_contracts.py`, `src/yongin_data/analysis/agent.py`, `tests/test_contract_cache_live.py`, `docs/AGENT_WORKLOG.md`; 앞선 미커밋 기능 변경과 Claude Code의 `0bfe11b` 설정 커밋도 현재 브랜치에 보존돼 있다.
- **커밋**: 이 항목 작성 시점 미커밋.
- **검증**: 분석 전체 라이브 테스트 33개 통과. 구 Webhook HTTP 404, 새 Webhook HTTP 200·숲체험일정 8,830건. 컬럼 계약 3개 데이터셋·7개 컬럼, 실행 ID·SHA·검증 시각 존재, 분석 역할의 캐시 쓰기 권한 없음. 실패 시도 기록과 이전 정상 계약 유지 확인. 실행 컨테이너 재빌드 완료.
- **다음 작업자에게**: 현재 계약은 로컬 MVP 3개만 영구 캐시한다. 다른 로컬 자료와 Supabase 최신본은 제한된 메모리 캐시/전체 값 검사를 사용한다. 운영 백업·복구와 브라우저 육안 확인, 날짜 범위·수치 집계 확장은 남아 있다. 수집 저장소의 구 분석 서비스는 다시 실행하지 말 것.

## 2026-11-06 12:54 · Codex

- **요약**: 모호한 자료 선택 뒤 원본 JSON 20행을 기본 출력하던 흐름을 자료 개요·적재 건수·후속 질문으로 변경했다. 명시적 원본 조회는 CSV 필드를 표의 열로 펴고, 검증된 월·연도·분류 집계는 차트와 집계표로 표시한다. 답변의 숫자와 최다 항목은 DB 결과만으로 작성하며 OpenAI는 검증된 자료 선택·조회 계획에 사용한다. 자료명에 포함된 구 이름을 행 필터로 오인하는 경우도 수정했다.
- **변경 파일**: `README.md`, `app.py`, `src/yongin_data/analysis/agent.py`, `src/yongin_data/analysis/presentation.py`, `tests/test_agent_live.py`, `tests/test_presentation.py`, `tests/test_web_ui.py`, `docs/AGENT_WORKLOG.md`.
- **커밋**: 기능 `7936ac8`; 이 기록은 별도 커밋.
- **검증**: 실제 DB·OpenAI·n8n을 포함한 전체 테스트 39개 통과. 구조화 모델 경로에서 검색 건수·월별 집계·자료 개요를 실제 호출해 `completed/llm`을 확인. 컨테이너 재빌드 후 웹 HTTP 200, API `llm_enabled=true`, n8n 자료 개요 응답 781건을 확인. Streamlit 화면은 AppTest로 답변·원본 표·차트 구성 요소를 검증했고 브라우저 육안 클릭 검증은 미실시.
- **다음 작업자에게**: 현재 시각화는 건수 분포 차트이며 다중 자료 결합, 임의 날짜 범위, 수치 합계·평균·순위는 아직 지원하지 않는다. 답변 문장은 DB 계산값 기반 템플릿으로 생성한다. 일반 대화형 자유 분석까지 확장하려면 먼저 자료별 수치 컬럼 계약과 안전한 연산을 추가할 것.

## 2026-11-06 14:08 · Codex

- **요약**: 사용자의 용인시 인구 분포 질문에 대해 읽기 전용 DB의 `portal_csv_15135861`을 직접 분석했다. 기준일 2026-09-08, 행정동 39행, 3개 구의 청년·고령자·생산가능인구 필드를 확인하고 구별 합계를 계산했다. 성별 합계와 전체 연령대 값이 39행의 6개 연령대에서 일치했다. 연령대 중첩과 빈 구간 때문에 여섯 연령대의 합을 전체 인구로 쓰지 않는 제한을 확인했다. 웹의 범용 인구 분포 질문은 현재 개요 39행으로 응답하고 구별 인구 합계 질문은 미지원임을 실제 호출로 확인했다.
- **변경 파일**: `docs/AGENT_WORKLOG.md`만 변경. 원본·운영 DB 변경 없음.
- **커밋**: 이 기록 작성 시점 미커밋.
- **검증**: 읽기 전용 `analytics.current_dataset_records` 39행 전수, 공식 포털의 39행·컬럼 정보, 현 서비스 실제 OpenAI 경로의 개요/미지원 응답을 확인했다.
- **다음 작업자에게**: 인구 분포를 웹에서 지원하려면 검증된 숫자 컬럼의 합계와 구별 그룹 집계가 필요하다. 행 수를 인구 수로 표현하지 말고, 2024년 인구·세대 자료와 2026년 연령별 자료를 같은 시점으로 합치지 말 것.

## 2026-11-06 14:24 · Codex

- **요약**: `portal_csv_15135861` 인구 자료에 한해 모든 행의 행정동·기준일·숫자 형식·남녀 합계를 검증하고 3개 구의 연령대별 인구를 안전하게 합산하는 읽기 전용 분석 경로를 추가했다. 웹에서 청년·고령자 구별 차트와 전체 연령대 집계표를 표시한다. 전체 인구 수·연령대 합산·시계열·행정동별·비율 질문은 근거 없는 숫자를 만들지 않도록 거절한다.
- **변경 파일**: `src/yongin_data/analysis/population.py`, `src/yongin_data/analysis/agent.py`, `app.py`, `README.md`, `tests/test_population.py`, `tests/test_agent_live.py`, `tests/test_web_ui.py`, `tests/test_webhook_live.py`, `docs/AGENT_WORKLOG.md`.
- **커밋**: 기능 `2ecd60b`; 이 기록은 별도 커밋.
- **검증**: 실제 로컬 DB·OpenAI·n8n Webhook을 포함한 전체 테스트 46개 통과. 컨테이너 재빌드 후 웹 HTTP 200, Webhook 청년 인구 합계 208,775명 및 인구 차트 메타데이터를 확인했다. 범용 인구 분포 질문에서 청년 208,775명·고령자 192,052명을 3개 구로 반환했다. Streamlit AppTest로 인구 차트·표 표시 요소를 검증했다. Chrome 창이 최소화돼 브라우저 육안 클릭 검증은 미실시.
- **다음 작업자에게**: 현재 인구 수 합계는 이 자료의 단일 기준일과 검증된 컬럼에만 허용한다. 수집본 변경 시 전수 검증 실패를 답변으로 노출하고 기존 값을 임의로 사용하지 않는다. 연령 구간 누락·중첩 때문에 전체 인구나 연령 비율 산출은 추가 계약 전까지 열지 말 것.

# 용인 생활여가 공공데이터 AI 분석 서비스

용인시 생활여가·문화·체육 공공데이터를 수집·정제·갱신하고, 자연어 질문에 실제 조회·결합·계산 결과와 출처를 제공하기 위한 2~3일 MVP 프로젝트입니다. 계산은 SQL·Python이 담당하고 LLM은 추후 질문 해석과 결과 설명에 연결합니다.

현재 단계는 실행 가능한 초기 골격입니다. PostgreSQL 연결 경로는 검증했지만,
실제 공공데이터 3종의 수집·정제·적재와 검색·분석 기능은 아직 연결되지 않았습니다.

## 로컬 실행

PowerShell 기준입니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

검증한 버전을 그대로 재현하려면 `python -m pip install -r requirements.lock`을 먼저 실행한 뒤 `python -m pip install -e . --no-deps`를 실행합니다.

`.env`에는 필요한 값만 입력합니다. 키가 없어도 초기 화면과 테스트는 실행됩니다. 비밀정보가 든 `.env`는 커밋하지 않습니다.

```powershell
streamlit run app.py
```

## DB 연결 확인

Supabase의 PostgreSQL 직접 연결 문자열을 `.env`의 `DATABASE_URL`에 설정한 뒤 실행합니다.

```powershell
python scripts/check_db.py
```

검사는 연결 시간 제한을 적용한 읽기 전용 `SELECT 1`만 수행합니다. 접속 문자열과 비밀번호는 로그에 출력하지 않습니다.

## 원본 수집

선정 데이터와 질문은 `docs/DATASET_SELECTION.md`에 기록되어 있습니다. 키 없이 확인할 수 있는 수지구 생활체육 프로그램 페이지는 다음처럼 원본 HTML과 메타데이터를 저장합니다.

```powershell
python scripts/collect_raw.py suji_programs
```

`DATA_GO_KR_SERVICE_KEY` 설정 후 공공시설·도시공원 API 원본을 수집할 수 있습니다.

```powershell
python scripts/collect_raw.py public_facilities
python scripts/collect_raw.py city_parks
```

원본은 `data/raw/<dataset_id>/`에 저장되며 Git에는 포함되지 않습니다. 각 원본에는 수집시각, 출처 URL, HTTP 상태, 크기, SHA-256을 기록한 메타데이터가 따라갑니다.

## 검증

```powershell
python -m compileall app.py src scripts tests
pytest
```

## 디렉터리

- `src/yongin_data/`: 설정, DB, 수집, 분석 코드
- `data/raw/`: 수집한 원본(내용은 Git 제외)
- `data/processed/`: 정제 결과(내용은 Git 제외)
- `sql/`: 검증된 SQL
- `workflows/n8n/`: 자동 갱신 워크플로
- `docs/PROJECT_STATUS.md`: 현재 상태와 다음 작업

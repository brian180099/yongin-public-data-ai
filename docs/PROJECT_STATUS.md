# 프로젝트 상태

기준일: 2026-11-03

## 확정 사항

- 범위: 용인시 생활여가·문화·체육
- 일정: 2~3일 MVP
- 초기 데이터: Open API를 포함한 3개 데이터셋, CSV·엑셀 최소 1개
- 화면: Streamlit
- 운영 DB: Supabase PostgreSQL 직접 연결
- 계산: SQL·Python, 설명: 추후 LLM
- 자동 갱신: n8n이 Python 수집·갱신 작업 실행

## 완료 작업

- Python `src` 구조와 Streamlit 초기 화면 작성
- 프로젝트 전용 `.venv` 구성 및 검증 환경의 정확한 패키지 버전 기록
- 환경변수 로딩·검증, 기본 로그 설정
- SQLAlchemy/psycopg 연결 함수와 안전한 `SELECT 1` 확인 스크립트 작성
- 로컬 `.env`에 설정된 PostgreSQL에 대해 `SELECT 1` 연결 검사 성공
- 비밀정보·수집 데이터 제외 규칙 작성
- 최소 단위 테스트 작성
- Python 문법 검사와 단위 테스트 4개 통과
- 비밀정보 없이 Streamlit 서버 실행 및 HTTP 200 응답 확인
- VS Code에서 프로젝트 폴더 열기 완료
- private GitHub 저장소 생성, `origin` 연결 및 `main` 최초 push 완료
- 공식 출처를 확인해 MVP 데이터셋 3종과 대표 질문 3개 선정
- 질문별 필수 필드, 계산 방식, 출처 및 데이터 한계를 `docs/DATASET_SELECTION.md`에 기록

## 미확인 사항

- OpenAI 및 data.go.kr 키 미설정
- 공공데이터포털 API 활용키 미설정으로 Open API 2종 실제 응답 미검증
- 생활체육프로그램 CSV의 최신 다운로드 방식과 실제 스키마 미검증
- n8n 실행 환경과 배포 방식 미확정

## 다음 작업

1. 데이터셋별 원본 저장과 수집 메타데이터 기록을 구현한다.
2. Open API 키가 설정되면 API 2종의 실제 응답과 용인 레코드 건수를 검증한다.
3. CSV의 최신 다운로드 방식과 실제 컬럼을 확인해 원본을 수집한다.
4. 정제 스키마·필수값·건수 검증과 운영 DB 반영 절차를 구현한다.
5. 대표 질문 SQL·Python과 Streamlit 화면을 연결한다.
6. 갱신 실패 시 이전 정상 데이터를 유지하는 n8n 흐름을 구성한다.

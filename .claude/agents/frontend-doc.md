# Frontend & Documentation Developer

Streamlit 프론트엔드 및 프로젝트 문서 전문 에이전트.

## 전용 MCP 서버
**context7** 을 활용하여:
- Streamlit API 문서 조회 (resolve-library-id → query-docs)
- boto3 API 문서 조회
- requests 라이브러리 참조

## 담당 범위

### 프론트엔드
- frontend/app.py (Streamlit 챗봇 UI)
- frontend/requirements.txt (streamlit, requests)
- frontend/summary.md (Streamlit 및 챗봇 UI 개념 학습 요약)

### 문서
- CLAUDE.md (프로젝트 가이드, 한국어)
- README.md (사용자 문서, 한국어)

### 샘플 데이터
- sampledata/amazon-bedrock-faq.txt (RAG 테스트용 샘플 문서)
  - 참조: `workshop/data/bedrock_faqs.py` (47개 Q&A 쌍)

## 워크숍 참조 코드
반드시 아래 워크숍 코드를 읽고 패턴을 따르세요:
- `workshop/completed/rag_chatbot/rag_chatbot_app.py` — Streamlit 챗봇 UI 패턴
- `workshop/completed/rag_chatbot/rag_chatbot_lib.py` — 대화 이력 관리 패턴

## Streamlit 구현 상세

### frontend/app.py
- API Gateway 엔드포인트 URL 입력 사이드바
- 엔드포인트 선택: `/query` (관리형) 또는 `/converse` (워크숍 패턴)
- 대화형 채팅 UI (st.chat_message, st.chat_input, st.container)
- 세션 상태로 대화 이력 관리 (st.session_state.chat_history)
- st.spinner("Working...") + st.expander("See search results")
- requests로 API Gateway POST 호출
- 응답에서 answer + citations 추출하여 표시
- 에러 처리 (API 연결 실패, 타임아웃 등)

## 문서 규칙
- 모든 문서는 한국어로 작성
- CLAUDE.md 포함 내용:
  - 프로젝트 개요 및 아키텍처
  - 스택 의존성 순서 (S3 → S3Vectors → BedrockKB → API, 4개 스택)
  - CDK 명령어 (synth, deploy, destroy)
  - 설정값 참조 (lib/config.ts)
  - 비용 안내 (S3 Vectors 사용량 기반, Nova Lite 저렴)
  - 에이전트 팀 구성 설명
- README.md 포함 내용:
  - 사전 준비사항 (AWS CLI, Node.js, CDK v2.238+, Bedrock 모델 액세스)
  - 설치 및 배포 가이드
  - API 테스트 예시 (curl: /query + /converse 모두)
  - Streamlit 로컬 실행 방법
  - 정리 가이드 (cdk destroy)

## 샘플 데이터
- `workshop/data/bedrock_faqs.py`의 47개 Q&A 쌍 활용
- Amazon Bedrock FAQ 형태의 Q&A 문서
- 한국어 + 영어 혼합
- RAG 검색 테스트에 적합한 분량 (2-3 페이지)

## 학습 목적 코드 작성 규칙

이 프로젝트는 **실습을 통한 학습**이 목적입니다. 다음 규칙을 반드시 따르세요:

### 코드 주석 규칙
- frontend/app.py 상단에 "이 앱이 무엇을 하는지" 한국어 docstring 작성
- Streamlit 위젯마다 "이 위젯의 역할과 사용자 경험" 주석
- API 호출 부분에 "요청/응답 흐름" 주석
- 세션 상태 관리에 "왜 세션 상태가 필요한지" 주석
- 예시:
  ```python
  # [학습] st.session_state는 Streamlit의 상태 관리 메커니즘입니다.
  # Streamlit은 사용자 상호작용마다 전체 스크립트를 재실행하므로,
  # 대화 이력을 유지하려면 session_state에 저장해야 합니다.
  if 'chat_history' not in st.session_state:
      st.session_state.chat_history = []
  ```

### summary.md 작성
`frontend/summary.md` 파일을 생성하여 다음 내용을 정리:
- Streamlit의 실행 모델 (스크립트 재실행 방식)과 session_state의 필요성
- 챗봇 UI 패턴 (chat_input, chat_message, container)
- REST API 호출 흐름 (프론트엔드 → API Gateway → Lambda → Bedrock)
- /query vs /converse 두 엔드포인트의 차이와 각각의 사용 사례
- RAG 응답에서 인용(citation)의 의미와 표시 방법

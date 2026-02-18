# Streamlit 프론트엔드 학습 정리

이 문서는 `frontend/` 폴더의 Streamlit 챗봇 앱이 다루는 UI 패턴, REST API 흐름, 상태 관리를 정리합니다.

---

## 1. Streamlit이란?

Streamlit은 Python으로 데이터 앱과 웹 UI를 빠르게 만들 수 있는 프레임워크입니다. HTML/CSS/JavaScript 없이 Python 코드만으로 대화형 UI를 구현할 수 있어, 데이터 과학자와 ML 엔지니어가 프로토타입을 빠르게 만드는 데 적합합니다.

### 이 프로젝트에서 Streamlit을 선택한 이유

| 대안 | 장점 | 단점 (실습 관점) |
|------|------|-----------------|
| React/Next.js | 프로덕션 수준 UI | 프론트엔드 학습 비용 높음, 빌드/배포 복잡 |
| Flask/FastAPI | 백엔드 친화적 | HTML 템플릿 직접 작성 필요 |
| **Streamlit** | **Python만으로 UI 완성** | **프로덕션 배포에는 부적합** |
| Gradio | ML 데모 특화 | 채팅 UI 커스터마이징 제한적 |

실습 프로젝트에서는 인프라와 RAG 백엔드 학습이 핵심이므로, 프론트엔드는 최소한의 코드로 기능을 구현할 수 있는 Streamlit이 적합합니다.

### 왜 프론트엔드를 AWS에 배포하지 않는가?

Streamlit을 AWS에 배포하려면 추가 인프라(ECS/Fargate, ALB, Route53 등)가 필요하고, Free Tier 범위를 벗어날 수 있습니다. 로컬 실행으로 충분히 전체 파이프라인을 테스트할 수 있으므로, 프론트엔드는 로컬에서 실행합니다.

---

## 2. Streamlit 실행 모델

### 스크립트 재실행 방식

Streamlit의 가장 중요한 특성은 **사용자 상호작용마다 전체 Python 스크립트가 위에서 아래로 재실행**된다는 점입니다:

```
사용자가 버튼 클릭/텍스트 입력
        ↓
app.py 전체 스크립트가 처음부터 다시 실행
        ↓
모든 UI 요소가 처음부터 다시 렌더링
        ↓
화면에 표시
```

이 방식의 결과:
- **변수가 유지되지 않음**: 스크립트 재실행 시 모든 지역 변수가 초기화됨
- **`st.session_state` 필수**: 대화 이력 등 지속해야 할 데이터는 session_state에 저장
- **조건부 렌더링**: 매번 전체 스크립트가 실행되므로, 이전 대화를 다시 그려야 함

### session_state — 상태 관리

```python
# 최초 실행 시만 초기화 (재실행 시에는 기존 값 유지)
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []         # UI 표시용 대화 기록
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = [] # API 전달용 대화 기록
```

**두 가지 이력을 별도로 관리하는 이유:**

| 이력 | 용도 | 포함 내용 |
|------|------|----------|
| `chat_history` | Streamlit UI에 대화 표시 | role, content, citations(출처 정보) |
| `conversation_history` | `/converse` API에 전달 | role, content만 (API 형식에 맞춤) |

`chat_history`는 인용 정보 등 UI 전용 데이터를 포함하고, `conversation_history`는 API가 요구하는 최소한의 데이터만 포함합니다.

---

## 3. 챗봇 UI 패턴

### 워크숍 원본과 이 프로젝트의 비교

| 요소 | 워크숍 (`rag_chatbot_app.py`) | 이 프로젝트 (`frontend/app.py`) |
|------|------------------------------|-------------------------------|
| LLM 호출 | 로컬 Python 직접 호출 | API Gateway HTTP 호출 |
| 대화 관리 | `ChatMessage` 클래스 | dict 기반 session_state |
| 엔드포인트 | 없음 (로컬) | `/query`, `/converse` 선택 가능 |
| 인용 표시 | 없음 | `st.expander`로 검색 결과 표시 |

### UI 구성 요소

```python
# 1. 페이지 설정
st.set_page_config(page_title="Bedrock RAG Chatbot", page_icon="...")
st.title("Bedrock RAG Chatbot")

# 2. 사이드바: 설정 옵션
with st.sidebar:
    api_endpoint = st.text_input("API Gateway 엔드포인트 URL")
    endpoint_mode = st.radio("RAG 엔드포인트 선택", ["/converse", "/query"])

# 3. 채팅 컨테이너: 대화 메시지 표시 영역
chat_container = st.container()

# 4. 채팅 입력: 화면 하단 고정
user_input = st.chat_input("질문을 입력하세요")
```

**Streamlit 채팅 컴포넌트:**

| 컴포넌트 | 용도 |
|---------|------|
| `st.chat_input()` | 화면 하단에 고정된 입력창. 엔터 시 값 반환 |
| `st.chat_message("user")` | 사용자 메시지 버블 (왼쪽 아바타) |
| `st.chat_message("assistant")` | AI 응답 버블 (오른쪽 아바타) |
| `st.spinner("Working...")` | API 호출 중 로딩 표시 |
| `st.expander("검색 결과 보기")` | 접을 수 있는 상세 정보 영역 |

### 대화 렌더링 흐름

스크립트가 재실행될 때마다 이전 대화를 다시 그립니다:

```python
# 저장된 모든 대화를 순서대로 렌더링
for message in st.session_state.chat_history:
    with chat_container.chat_message(message["role"]):
        st.markdown(message["content"])
        # 인용 정보가 있으면 접을 수 있는 영역으로 표시
        if "citations" in message and message["citations"]:
            with st.expander("검색 결과 보기"):
                for i, citation in enumerate(message["citations"], 1):
                    st.markdown(f"**[출처 {i}]** {citation}")
```

---

## 4. REST API 호출 흐름

### 전체 흐름

```
Streamlit (로컬)                API Gateway                  Lambda
     │                              │                          │
     ├── POST /converse ──────────→ │ ──────────────────────→ │
     │   {query, conversation_      │                          │
     │    history}                   │                          │
     │                              │                          │
     │ ←─────────────────────────── │ ←────────────────────── │
     │   {answer, contexts}         │                          │
     │                              │                          │
     ├── POST /query ─────────────→ │ ──────────────────────→ │
     │   {query}                    │                          │
     │                              │                          │
     │ ←─────────────────────────── │ ←────────────────────── │
     │   {answer, citations}        │                          │
```

### 엔드포인트별 요청/응답 형식

**`/converse` (워크숍 패턴)**
```python
# 요청
payload = {
    "query": "Amazon Bedrock이란?",
    "conversation_history": [
        {"role": "user", "content": "이전 질문"},
        {"role": "assistant", "content": "이전 답변"},
    ]
}

# 응답
{
    "answer": "Amazon Bedrock은...",
    "contexts": ["관련 문서 청크 1", "관련 문서 청크 2"]
}
```

**`/query` (관리형)**
```python
# 요청
payload = {"query": "Amazon Bedrock이란?"}

# 응답
{
    "answer": "Amazon Bedrock은...",
    "citations": [
        {"text": "원본 문서 텍스트", "location": {"s3Location": {...}}}
    ]
}
```

### 인용 표시 통합

두 엔드포인트의 응답 형식이 다르므로, 프론트엔드에서 통합 처리합니다:

```python
citations = data.get("citations", [])   # /query 응답
contexts = data.get("contexts", [])      # /converse 응답
display_sources = []

if citations:
    # /query: citations 배열에서 text 필드 추출
    display_sources = [c.get("text", "") for c in citations if c.get("text")]
elif contexts:
    # /converse: contexts 배열을 그대로 사용
    display_sources = contexts
```

---

## 5. 에러 핸들링 패턴

Streamlit에서 API 호출 시 발생할 수 있는 오류를 분류하여 처리합니다:

```python
try:
    response = requests.post(url, json=payload, timeout=30)
    response.raise_for_status()
except requests.exceptions.ConnectionError:
    st.error("API 서버에 연결할 수 없습니다.")     # URL 오류 또는 서버 다운
except requests.exceptions.Timeout:
    st.error("요청 시간이 초과되었습니다.")          # Lambda 30초 타임아웃
except requests.exceptions.HTTPError as e:
    st.error(f"API 오류: {e.response.status_code}")  # 4xx/5xx 에러
except Exception as e:
    st.error(f"오류가 발생했습니다: {str(e)}")       # 기타 예외
```

| 에러 유형 | 원인 | 대응 |
|----------|------|------|
| `ConnectionError` | 잘못된 URL, 네트워크 차단 | URL 확인 안내 |
| `Timeout` | Lambda 실행 시간 초과 (30초) | 재시도 안내 |
| `HTTPError 400` | 잘못된 요청 (query 누락 등) | 요청 형식 확인 |
| `HTTPError 500` | Lambda 내부 오류 | CloudWatch 로그 확인 안내 |

---

## 6. RAG 인용(Citation)의 의미와 표시

인용은 RAG 답변이 어떤 원본 문서를 참조했는지 보여주는 핵심 기능입니다:

| 가치 | 설명 |
|------|------|
| **투명성** | 사용자가 답변의 근거를 직접 확인 가능 |
| **신뢰성** | LLM의 할루시네이션을 검증할 수 있음 |
| **추적성** | 문서 업데이트가 답변에 미치는 영향 추적 |

두 엔드포인트의 인용 방식 차이:
- **`/query`**: Bedrock이 자동 생성한 `citations` (원본 문서 위치 포함)
- **`/converse`**: `retrieve()` 결과의 `contexts` (텍스트 청크만)

```python
# 인용을 접을 수 있는 영역으로 표시
with st.expander("검색 결과 보기"):
    for i, source in enumerate(display_sources, 1):
        st.markdown(f"**[출처 {i}]** {source}")
```

---

## 7. 로컬 실행 방법

```bash
# 1. 의존성 설치
cd frontend
pip install -r requirements.txt   # streamlit, requests

# 2. 실행
streamlit run app.py

# 3. 브라우저에서 http://localhost:8501 접속
# 4. 사이드바에서 API Gateway 엔드포인트 URL 입력
# 5. 질문 입력 후 엔터
```

---

## 8. 워크숍 코드 참조

이 프론트엔드는 워크숍의 `rag_chatbot_app.py` 패턴을 기반으로 합니다:

| 워크숍 코드 | 이 프로젝트에서의 적용 |
|-----------|---------------------|
| `st.set_page_config()` | 동일하게 사용 |
| `st.chat_input()` + `st.chat_message()` | 동일하게 사용 |
| `ChatMessage` 클래스 | dict 기반으로 단순화 |
| `st.session_state.chat_history` | 동일한 패턴 사용 |
| 로컬 `rag_chatbot_lib.py` 직접 호출 | REST API(`requests.post`) 호출로 변경 |
| 단일 RAG 방식 | `/query`와 `/converse` 두 방식 선택 가능 |

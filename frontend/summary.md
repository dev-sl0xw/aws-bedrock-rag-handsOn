# 프론트엔드 학습 요약

## Streamlit 실행 모델

Streamlit은 일반적인 웹 프레임워크(React, Flask 등)와 다른 독특한 실행 모델을 가집니다:

### 스크립트 재실행 방식
- 사용자가 버튼을 클릭하거나 입력을 제출하면 **전체 Python 스크립트가 처음부터 다시 실행**됩니다
- 이는 단순하지만, 상태 관리에 주의가 필요합니다
- 변수에 저장한 값은 재실행 시 초기화됩니다

### session_state의 필요성
```python
# 재실행해도 유지되는 상태 저장소
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
```

`st.session_state`는 사용자 세션 동안 데이터를 유지하는 딕셔너리입니다. 채팅 이력, API 설정 등을 여기에 저장하면 스크립트 재실행 후에도 값이 유지됩니다.

## 챗봇 UI 패턴

Streamlit은 채팅 UI 전용 위젯을 제공합니다:

### st.chat_input
화면 하단에 고정된 채팅 입력창을 표시합니다.
```python
user_input = st.chat_input("질문을 입력하세요")
```

### st.chat_message
사용자/어시스턴트 역할에 맞는 채팅 말풍선을 렌더링합니다.
```python
with st.chat_message("user"):
    st.markdown(user_input)
with st.chat_message("assistant"):
    st.markdown(answer)
```

### st.container
채팅 메시지가 표시되는 스크롤 가능한 영역을 정의합니다.

### st.spinner / st.expander
```python
with st.spinner("Working..."):   # API 호출 중 로딩 표시
    response = requests.post(...)
with st.expander("검색 결과 보기"):  # 접을 수 있는 영역
    st.markdown(citation_text)
```

## REST API 호출 흐름

```
사용자 입력
    ↓
Streamlit (frontend/app.py)
    ↓ requests.post()
API Gateway (REST API)
    ↓ Lambda 프록시 통합
Lambda 함수
    ↓ boto3
Bedrock (Knowledge Base + LLM)
    ↓
Lambda 응답 (JSON)
    ↓
API Gateway 응답 (HTTP)
    ↓
Streamlit 표시 (st.chat_message)
```

## /query vs /converse 차이

| 항목 | /query | /converse |
|------|--------|-----------|
| **API** | retrieve_and_generate | retrieve + converse |
| **대화 이력** | 미지원 | 지원 (conversation_history) |
| **프롬프트 제어** | 불가 | 자유로운 커스터마이징 |
| **요청 형식** | `{"query": "..."}` | `{"query": "...", "conversation_history": [...]}` |
| **응답 형식** | `{"answer": "...", "citations": [...]}` | `{"answer": "...", "contexts": [...]}` |
| **사용 사례** | 단일 질문 FAQ | 멀티턴 대화, 복잡한 질의 |

## RAG 인용(Citation)의 의미와 표시

인용은 RAG 답변이 어떤 원본 문서를 참조했는지 보여줍니다:

- **투명성**: 사용자가 답변의 근거를 직접 확인 가능
- **신뢰성**: LLM의 환각(hallucination)을 검증할 수 있음
- **추적성**: 문서 업데이트가 답변에 미치는 영향 추적

표시 방법:
```python
with st.expander("검색 결과 보기"):
    for i, citation in enumerate(citations, 1):
        st.markdown(f"**[출처 {i}]** {citation}")
```

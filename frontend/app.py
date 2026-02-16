"""
[학습] Bedrock RAG 챗봇 - Streamlit 프론트엔드

이 앱은 AWS Bedrock RAG 파이프라인의 프론트엔드입니다.
사용자의 질문을 API Gateway를 통해 Lambda로 전달하고,
RAG 기반 답변을 대화형 UI로 표시합니다.

두 가지 RAG 엔드포인트를 선택할 수 있습니다:
- /query: 관리형 retrieve_and_generate (간단하지만 대화 이력 미지원)
- /converse: 워크숍 패턴 retrieve + converse (대화 이력 지원, 프롬프트 커스터마이징 가능)

참조: workshop/completed/rag_chatbot/rag_chatbot_app.py
"""
import streamlit as st
import requests
import json

# [학습] Streamlit 페이지 설정
# page_title: 브라우저 탭에 표시되는 제목
# page_icon: 브라우저 탭의 아이콘
st.set_page_config(page_title="Bedrock RAG Chatbot", page_icon="🤖")
st.title("Bedrock RAG Chatbot")

# [학습] 사이드바 설정
# Streamlit 사이드바는 앱의 설정/옵션을 배치하기에 적합합니다.
with st.sidebar:
    st.header("설정")

    # [학습] API Gateway 엔드포인트 URL 입력
    # CDK 배포 후 출력되는 URL을 여기에 입력합니다.
    # 예: https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod
    api_endpoint = st.text_input(
        "API Gateway 엔드포인트 URL",
        placeholder="https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/prod",
        help="CDK 배포 후 출력되는 API 엔드포인트 URL을 입력하세요.",
    )

    # [학습] 엔드포인트 선택
    # /query: 관리형 방식 - 간단하지만 대화 이력을 지원하지 않음
    # /converse: 워크숍 패턴 - 대화 이력을 지원하며 프롬프트를 커스터마이징 가능
    endpoint_mode = st.radio(
        "RAG 엔드포인트 선택",
        options=["/converse", "/query"],
        captions=[
            "워크숍 패턴 (대화 이력 지원, retrieve + converse)",
            "관리형 (간단, retrieve_and_generate)",
        ],
    )

    if st.button("대화 초기화"):
        st.session_state.chat_history = []
        st.session_state.conversation_history = []
        st.rerun()

# [학습] st.session_state는 Streamlit의 상태 관리 메커니즘입니다.
# Streamlit은 사용자 상호작용마다 전체 스크립트를 재실행하므로,
# 대화 이력을 유지하려면 session_state에 저장해야 합니다.
# chat_history: UI 표시용 대화 기록
# conversation_history: /converse API에 전달할 대화 기록
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# [학습] 채팅 컨테이너: 대화 메시지가 표시되는 영역
chat_container = st.container()

# [학습] 기존 대화 이력 렌더링
# Streamlit은 스크립트 재실행 시 UI를 처음부터 다시 그리므로,
# session_state에 저장된 이전 대화를 다시 표시해야 합니다.
for message in st.session_state.chat_history:
    with chat_container.chat_message(message["role"]):
        st.markdown(message["content"])
        if "citations" in message and message["citations"]:
            with st.expander("검색 결과 보기"):
                for i, citation in enumerate(message["citations"], 1):
                    st.markdown(f"**[출처 {i}]** {citation}")

# [학습] st.chat_input: 채팅 입력창을 화면 하단에 고정 표시합니다.
# 사용자가 엔터를 치면 입력값이 반환됩니다.
user_input = st.chat_input("질문을 입력하세요")

if user_input:
    if not api_endpoint:
        st.error("사이드바에서 API Gateway 엔드포인트 URL을 입력해주세요.")
    else:
        # [학습] 사용자 메시지 표시
        with chat_container.chat_message("user"):
            st.markdown(user_input)
        st.session_state.chat_history.append({"role": "user", "content": user_input})

        # [학습] st.spinner: API 호출 중 로딩 표시
        with chat_container.chat_message("assistant"):
            with st.spinner("Working..."):
                try:
                    # [학습] 엔드포인트에 따라 다른 요청 형식 사용
                    url = f"{api_endpoint.rstrip('/')}{endpoint_mode}"

                    if endpoint_mode == "/converse":
                        # /converse: 대화 이력을 함께 전송
                        payload = {
                            "query": user_input,
                            "conversation_history": st.session_state.conversation_history,
                        }
                    else:
                        # /query: 단일 질문만 전송
                        payload = {"query": user_input}

                    # [학습] requests.post로 API Gateway 호출
                    # timeout: 30초 후 타임아웃 (Lambda 실행 시간 고려)
                    response = requests.post(
                        url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30,
                    )
                    response.raise_for_status()
                    data = response.json()

                    answer = data.get("answer", "답변을 받지 못했습니다.")
                    st.markdown(answer)

                    # [학습] 인용/검색 결과 표시
                    # /query 응답: citations 필드
                    # /converse 응답: contexts 필드
                    citations = data.get("citations", [])
                    contexts = data.get("contexts", [])
                    display_sources = []

                    if citations:
                        display_sources = [c.get("text", "") for c in citations if c.get("text")]
                    elif contexts:
                        display_sources = contexts

                    if display_sources:
                        with st.expander("검색 결과 보기"):
                            for i, source in enumerate(display_sources, 1):
                                st.markdown(f"**[출처 {i}]** {source}")

                    # [학습] 대화 이력 업데이트
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": answer,
                        "citations": display_sources,
                    })

                    # /converse 모드일 때 API 전달용 이력도 업데이트
                    if endpoint_mode == "/converse":
                        st.session_state.conversation_history.append(
                            {"role": "user", "content": user_input}
                        )
                        st.session_state.conversation_history.append(
                            {"role": "assistant", "content": answer}
                        )

                except requests.exceptions.ConnectionError:
                    st.error("API 서버에 연결할 수 없습니다. 엔드포인트 URL을 확인해주세요.")
                except requests.exceptions.Timeout:
                    st.error("요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
                except requests.exceptions.HTTPError as e:
                    st.error(f"API 오류: {e.response.status_code} - {e.response.text}")
                except Exception as e:
                    st.error(f"오류가 발생했습니다: {str(e)}")

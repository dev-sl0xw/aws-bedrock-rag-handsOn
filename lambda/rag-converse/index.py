"""
[학습] Converse API Lambda - retrieve() + converse() 워크숍 패턴

이 Lambda는 RAG 파이프라인을 두 단계로 분리하여 직접 제어합니다:
1단계: retrieve() - Knowledge Base에서 관련 문서만 검색
2단계: converse() - 검색된 컨텍스트와 질문을 LLM에 직접 전달

이 방식은 관리형 retrieve_and_generate()와 달리:
- 프롬프트를 자유롭게 커스터마이징할 수 있습니다
- 대화 이력(conversation history)을 직접 관리할 수 있습니다
- 검색 결과를 중간에서 가공/필터링할 수 있습니다

워크숍 원본 코드: workshop/completed/rag/rag_lib.py
대화 이력 패턴: workshop/completed/rag_chatbot/rag_chatbot_lib.py

환경변수:
- KNOWLEDGE_BASE_ID: Bedrock Knowledge Base ID
- GENERATION_MODEL_ID: Converse API에 사용할 LLM 모델 ID
"""
import json
import os
import boto3

# [학습] 두 개의 서로 다른 Bedrock 클라이언트를 사용합니다:
# - bedrock-agent-runtime: Knowledge Base 검색(retrieve) 전용
# - bedrock-runtime: LLM 모델 직접 호출(converse) 전용
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')
bedrock_runtime = boto3.client('bedrock-runtime')

KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
GENERATION_MODEL_ID = os.environ.get('GENERATION_MODEL_ID', '')

# [학습] 워크숍 chatbot_lib.py 패턴: 대화 이력 최대 메시지 수
# 메모리와 토큰 제한을 고려하여 오래된 대화를 자동으로 삭제합니다.
MAX_MESSAGES = 20


def handler(event, context):
    """
    [학습] API Gateway 프록시 통합 핸들러
    요청 body: {"query": "사용자 질문", "conversation_history": [...]}
    conversation_history는 [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}] 형태
    """
    print(f"Event: {json.dumps(event)}")

    try:
        body = json.loads(event.get('body', '{}'))
        query = body.get('query', '')
        conversation_history = body.get('conversation_history', [])

        if not query:
            return build_response(400, {'error': 'query 파라미터가 필요합니다.'})

        # [학습] 1단계: retrieve() - Knowledge Base에서 관련 문서 검색
        # retrieve_and_generate()와 달리 검색만 수행하고 LLM 호출은 하지 않습니다.
        # numberOfResults로 반환할 검색 결과 수를 제어합니다.
        retrieve_response = bedrock_agent_runtime.retrieve(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            retrievalQuery={'text': query},
            retrievalConfiguration={
                'vectorSearchConfiguration': {
                    'numberOfResults': 4,
                },
            },
        )

        # [학습] 검색 결과에서 텍스트 컨텍스트 추출
        # 각 결과의 content.text에 원본 문서 청크가 들어있습니다.
        contexts = []
        for result in retrieve_response.get('retrievalResults', []):
            text = result.get('content', {}).get('text', '')
            if text:
                contexts.append(text)

        rag_content = '\n\n'.join(contexts)

        # [학습] 2단계: converse() - LLM 직접 호출
        # 워크숍 rag_lib.py 패턴: 메시지 content 배열에 [컨텍스트, 지시문, 질문]을 순서대로 배치합니다.
        # 이렇게 하면 LLM이 컨텍스트를 참조하여 질문에 답변합니다.
        user_message = {
            'role': 'user',
            'content': [
                {'text': rag_content},
                {'text': 'Based on the content above, please answer the following question:'},
                {'text': query},
            ],
        }

        # [학습] 대화 이력 관리 (워크숍 chatbot_lib.py 패턴)
        # conversation_history를 Converse API 메시지 형식으로 변환합니다.
        messages = []
        for msg in conversation_history:
            messages.append({
                'role': msg['role'],
                'content': [{'text': msg['content']}],
            })

        messages.append(user_message)

        # [학습] MAX_MESSAGES 초과 시 오래된 메시지를 삭제합니다.
        # user+assistant 쌍 단위로 삭제하여 대화 흐름이 깨지지 않도록 합니다.
        if len(messages) > MAX_MESSAGES:
            excess = len(messages) - MAX_MESSAGES
            del messages[0:excess]

        # [학습] converse() API 호출
        # 워크숍 rag_lib.py의 inferenceConfig 기본값을 사용합니다:
        # - maxTokens: 생성할 최대 토큰 수
        # - temperature: 0이면 결정적(항상 같은 답변), 높을수록 창의적
        # - topP: 누적 확률 기반 토큰 선택 (0.9 = 상위 90% 확률 토큰 중 선택)
        converse_response = bedrock_runtime.converse(
            modelId=GENERATION_MODEL_ID,
            messages=messages,
            inferenceConfig={
                'maxTokens': 2000,
                'temperature': 0,
                'topP': 0.9,
                'stopSequences': [],
            },
        )

        # [학습] converse() 응답에서 답변 텍스트 추출
        answer = converse_response['output']['message']['content'][0]['text']

        return build_response(200, {
            'answer': answer,
            'contexts': contexts,
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return build_response(500, {'error': str(e)})


def build_response(status_code, body):
    """
    [학습] API Gateway 프록시 통합 응답 포맷
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST',
        },
        'body': json.dumps(body, ensure_ascii=False),
    }

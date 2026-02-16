"""
[학습] RAG 쿼리 Lambda - retrieve_and_generate 관리형 방식

이 Lambda는 Bedrock의 관리형 RAG API인 retrieve_and_generate()를 호출합니다.
사용자 질문이 들어오면:
1. Knowledge Base에서 관련 문서를 벡터 검색하고
2. 검색된 컨텍스트와 질문을 LLM에 전달하여
3. 답변을 생성합니다.

이 모든 과정이 하나의 API 호출로 처리되는 것이 '관리형' 방식의 장점입니다.
반면 retrieve() + converse() 방식(rag-converse Lambda)은 각 단계를 직접 제어할 수 있어
프롬프트 커스터마이징이나 대화 이력 관리에 더 유연합니다.

환경변수:
- KNOWLEDGE_BASE_ID: Bedrock Knowledge Base ID
- MODEL_ARN: 응답 생성에 사용할 LLM 모델 ARN
"""
import json
import os
import boto3

# [학습] bedrock-agent-runtime 클라이언트는 Knowledge Base 관련 API를 제공합니다.
# bedrock-runtime(모델 직접 호출)과는 다른 서비스 엔드포인트입니다.
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

# [학습] 환경변수로 설정값을 주입받아 하드코딩을 방지합니다.
# CDK에서 Lambda 생성 시 environment 속성으로 전달됩니다.
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
MODEL_ARN = os.environ.get('MODEL_ARN', '')


def handler(event, context):
    """
    [학습] API Gateway 프록시 통합 핸들러
    API Gateway에서 POST 요청을 받아 처리합니다.
    요청 body: {"query": "사용자 질문"}
    """
    print(f"Event: {json.dumps(event)}")

    try:
        body = json.loads(event.get('body', '{}'))
        query = body.get('query', '')

        if not query:
            return build_response(400, {'error': 'query 파라미터가 필요합니다.'})

        # [학습] retrieve_and_generate() API 호출
        # 이 API는 한 번의 호출로 다음을 수행합니다:
        # 1. Knowledge Base에서 질문과 관련된 문서 청크를 벡터 검색
        # 2. 검색된 컨텍스트와 질문을 LLM에 전달
        # 3. LLM이 컨텍스트를 기반으로 답변 생성
        # 4. 답변과 함께 인용(citation) 정보 반환
        response = bedrock_agent_runtime.retrieve_and_generate(
            input={'text': query},
            retrieveAndGenerateConfiguration={
                'type': 'KNOWLEDGE_BASE',
                'knowledgeBaseConfiguration': {
                    'knowledgeBaseId': KNOWLEDGE_BASE_ID,
                    'modelArn': MODEL_ARN,
                },
            },
        )

        # [학습] 응답에서 답변 텍스트 추출
        answer = response.get('output', {}).get('text', '')

        # [학습] 인용(citations) 추출
        # 인용은 답변이 어떤 원본 문서를 참조했는지 보여줍니다.
        # RAG의 핵심 가치 중 하나는 답변의 출처를 추적할 수 있다는 것입니다.
        citations = []
        for citation in response.get('citations', []):
            for ref in citation.get('retrievedReferences', []):
                citations.append({
                    'text': ref.get('content', {}).get('text', ''),
                    'location': ref.get('location', {}),
                })

        return build_response(200, {
            'answer': answer,
            'citations': citations,
        })

    except Exception as e:
        print(f"Error: {str(e)}")
        return build_response(500, {'error': str(e)})


def build_response(status_code, body):
    """
    [학습] API Gateway 프록시 통합 응답 포맷
    API Gateway는 Lambda의 응답을 HTTP 응답으로 변환합니다.
    반드시 statusCode, headers, body 구조를 따라야 합니다.
    CORS 헤더를 포함해야 브라우저(Streamlit 등)에서 호출 가능합니다.
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

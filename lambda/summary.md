# Lambda 및 Bedrock API 학습 요약

## RAG(Retrieval-Augmented Generation)란?

RAG는 LLM의 답변 품질을 향상시키는 기법으로, 다음 과정을 거칩니다:

1. **검색(Retrieval)**: 사용자 질문과 관련된 문서를 벡터 검색으로 찾음
2. **증강(Augmentation)**: 검색된 문서를 LLM 프롬프트에 컨텍스트로 추가
3. **생성(Generation)**: LLM이 컨텍스트를 기반으로 답변 생성

### 왜 RAG가 필요한가?
- LLM은 학습 데이터에 없는 최신 정보나 사내 문서에 대해 답변하지 못함
- RAG를 사용하면 LLM을 재학습하지 않고도 최신/사내 정보 기반 답변 가능
- 답변의 출처(인용)를 추적할 수 있어 신뢰성 향상

## 두 가지 RAG 방식 비교

### 1. retrieve_and_generate (관리형)

```python
response = bedrock_agent.retrieve_and_generate(
    input={'text': query},
    retrieveAndGenerateConfiguration={
        'type': 'KNOWLEDGE_BASE',
        'knowledgeBaseConfiguration': {
            'knowledgeBaseId': kb_id,
            'modelArn': model_arn,
        }
    }
)
```

**장점**: 한 번의 API 호출로 검색+생성 완료, 구현이 간단
**단점**: 프롬프트 커스터마이징 불가, 대화 이력 미지원

### 2. retrieve + converse (워크숍 패턴)

```python
# 1단계: 검색만
results = bedrock_agent.retrieve(
    knowledgeBaseId=kb_id,
    retrievalQuery={'text': question},
)

# 2단계: LLM 직접 호출
response = bedrock.converse(
    modelId='us.amazon.nova-lite-v1:0',
    messages=[{
        'role': 'user',
        'content': [
            {'text': rag_content},     # 검색 결과
            {'text': 'Based on the content above...'},
            {'text': question},        # 사용자 질문
        ]
    }],
    inferenceConfig={'maxTokens': 2000, 'temperature': 0},
)
```

**장점**: 프롬프트 자유 구성, 대화 이력 지원, 검색 결과 중간 가공 가능
**단점**: 두 번의 API 호출 필요, 구현이 복잡

## Bedrock Converse API

Converse API는 다양한 LLM 모델을 통일된 인터페이스로 호출하는 API입니다.

### 메시지 포맷
```python
messages = [
    {
        'role': 'user',       # 'user' 또는 'assistant'
        'content': [
            {'text': '텍스트 내용'},  # 여러 content 블록 가능
        ]
    }
]
```

### inferenceConfig
- `maxTokens`: 생성할 최대 토큰 수 (2000)
- `temperature`: 0=결정적, 1=최대 창의적
- `topP`: 누적 확률 기반 토큰 선택 (0.9)

## 임베딩과 벡터 검색

### 임베딩이란?
텍스트를 고정 길이의 숫자 벡터로 변환하는 과정입니다. 의미가 유사한 텍스트는 벡터 공간에서 가까운 위치에 배치됩니다.

- **모델**: Titan Text Embeddings V2
- **차원**: 1024 (각 텍스트가 1024개의 숫자로 표현)
- **유사도 측정**: 코사인 유사도 (벡터 간 각도)

### 벡터 검색 흐름
1. 사용자 질문 → Titan V2로 임베딩 (1024차원 벡터)
2. S3 Vectors에서 코사인 유사도로 가장 유사한 벡터 검색
3. 유사한 벡터에 매핑된 원본 텍스트 청크 반환

## Knowledge Base 데이터 수집 파이프라인

```
S3 문서 → 청킹(512토큰, 20%오버랩) → Titan V2 임베딩 → S3 Vectors 저장
```

- **청킹**: 긴 문서를 검색에 적합한 크기로 분할
- **오버랩**: 인접 청크 간 20% 겹침으로 경계 정보 손실 방지
- **start_ingestion_job()**: 이 파이프라인을 비동기로 실행

## Lambda 환경변수 패턴

Lambda 함수에 설정값을 주입하는 표준 방법:
- CDK에서 `environment` 속성으로 설정
- Lambda 코드에서 `os.environ.get()`으로 읽기
- 하드코딩 없이 환경별(dev/staging/prod) 설정 변경 가능

## API Gateway 프록시 통합과 CORS

### 프록시 통합
API Gateway가 HTTP 요청을 그대로 Lambda에 전달하고, Lambda 응답을 그대로 HTTP 응답으로 반환하는 방식입니다.

Lambda 응답 포맷:
```python
{
    'statusCode': 200,
    'headers': {'Access-Control-Allow-Origin': '*'},
    'body': json.dumps({'answer': '...'})
}
```

### CORS
브라우저의 동일 출처 정책(Same-Origin Policy)을 완화하여 다른 도메인에서 API를 호출할 수 있게 합니다. Streamlit(localhost)에서 API Gateway(amazonaws.com)를 호출하려면 CORS 설정이 필수입니다.

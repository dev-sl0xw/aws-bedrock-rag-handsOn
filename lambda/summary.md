# Lambda 함수 및 RAG 이론 학습 정리

이 문서는 `lambda/` 폴더의 3개 Lambda 함수가 다루는 RAG 이론, Bedrock API, 임베딩/벡터 검색 원리를 정리합니다.

---

## 1. RAG (Retrieval-Augmented Generation) 이론

### RAG란?

RAG는 LLM이 학습하지 못한 최신 정보나 사내 문서를 기반으로 답변을 생성하는 기법입니다. "검색(Retrieval)"으로 관련 문서를 찾고, "생성(Generation)"으로 답변을 만듭니다.

```
[기존 LLM]
질문 → LLM → 답변 (학습 데이터에만 의존, 할루시네이션 위험)

[RAG]
질문 → 벡터 검색 → 관련 문서 발견 → 문서 + 질문 → LLM → 근거 있는 답변
```

### RAG의 장점

| 문제 | RAG의 해결 방법 |
|------|---------------|
| **할루시네이션** | 실제 문서를 기반으로 답변하므로 근거 제시 가능 |
| **최신 정보 부재** | 문서를 업데이트하면 즉시 반영 (모델 재학습 불필요) |
| **사내 데이터 활용** | 공개되지 않은 사내 문서도 검색 가능 |
| **비용** | Fine-tuning 대비 저비용 (문서 저장/검색만 필요) |

### RAG 파이프라인 전체 흐름

```
[데이터 수집 파이프라인]
  원본 문서(S3)
       ↓
  청킹 (512 토큰, 20% 오버랩)
       ↓
  임베딩 (Titan Embeddings V2 → 1024차원 벡터)
       ↓
  벡터 저장 (S3 Vectors)

[쿼리 처리 파이프라인]
  사용자 질문
       ↓
  질문 임베딩 (Titan Embeddings V2 → 1024차원 벡터)
       ↓
  벡터 유사도 검색 (코사인 유사도로 Top-K 청크 반환)
       ↓
  컨텍스트 조합 (검색된 청크들을 프롬프트에 삽입)
       ↓
  LLM 응답 생성 (Nova Lite)
       ↓
  인용 포함 답변 반환
```

---

## 2. 임베딩과 벡터 검색 원리

### 임베딩(Embedding)이란?

텍스트를 고정 길이의 숫자 배열(벡터)로 변환하는 과정입니다. 의미가 비슷한 텍스트는 비슷한 벡터로 변환됩니다.

```
"Amazon Bedrock은 AI 서비스입니다" → [0.12, -0.45, 0.78, ..., 0.33]  (1024개 숫자)
"AWS의 인공지능 플랫폼"            → [0.11, -0.43, 0.79, ..., 0.31]  (유사한 벡터)
"오늘 날씨가 좋습니다"              → [0.89, 0.12, -0.56, ..., -0.67] (전혀 다른 벡터)
```

### 코사인 유사도(Cosine Similarity)

두 벡터의 방향이 얼마나 비슷한지 측정합니다:
- **1.0**: 완전히 같은 방향 (매우 유사)
- **0.0**: 직교 (관련 없음)
- **-1.0**: 반대 방향 (반대 의미)

이 프로젝트에서 S3 Vectors의 `distanceMetric: 'cosine'`이 이 방식을 사용합니다.

### 청킹(Chunking) 전략

문서를 작은 조각으로 나누는 이유와 방법:

```
전체 문서 (10,000 토큰)
├── 청크 1: [0 ~ 512 토큰]
├── 청크 2: [410 ~ 922 토큰]  ← 20% 오버랩 (102 토큰 겹침)
├── 청크 3: [820 ~ 1332 토큰] ← 20% 오버랩
└── ...
```

| 설정 | 값 | 의미 |
|------|-----|------|
| `chunkingStrategy` | `FIXED_SIZE` | 고정 크기로 분할 (가장 단순하고 예측 가능) |
| `maxTokens` | 512 | 각 청크의 최대 크기. 너무 크면 검색 정밀도 저하, 너무 작으면 문맥 손실 |
| `overlapPercentage` | 20 | 인접 청크의 20%가 겹침. 청크 경계에서 잘린 문장도 검색 가능 |

---

## 3. Bedrock API — 두 가지 RAG 방식

이 프로젝트는 동일한 RAG 기능을 두 가지 다른 API로 구현하여, 각 방식의 장단점을 비교 학습합니다.

### 방식 1: `retrieve_and_generate()` — 관리형 (`rag-query/index.py`)

```python
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
answer = response['output']['text']
citations = response['citations']
```

**하나의 API 호출로 검색 + 생성을 모두 처리합니다.**

| 장점 | 단점 |
|------|------|
| 코드가 간단 (API 1회 호출) | 프롬프트 커스터마이징 불가 |
| 인용(citation) 자동 생성 | 대화 이력 관리 불가 |
| Bedrock이 최적화된 프롬프트 사용 | 검색 결과 중간 가공 불가 |

### 방식 2: `retrieve()` + `converse()` — 워크숍 패턴 (`rag-converse/index.py`)

```python
# 1단계: 벡터 검색만 수행
retrieve_response = bedrock_agent_runtime.retrieve(
    knowledgeBaseId=KNOWLEDGE_BASE_ID,
    retrievalQuery={'text': query},
    retrievalConfiguration={'vectorSearchConfiguration': {'numberOfResults': 4}},
)
contexts = [r['content']['text'] for r in retrieve_response['retrievalResults']]

# 2단계: 검색된 컨텍스트로 LLM 직접 호출
converse_response = bedrock_runtime.converse(
    modelId=GENERATION_MODEL_ID,
    messages=[{
        'role': 'user',
        'content': [
            {'text': '\n\n'.join(contexts)},
            {'text': 'Based on the content above, please answer the following question:'},
            {'text': query},
        ],
    }],
    inferenceConfig={'maxTokens': 2000, 'temperature': 0, 'topP': 0.9},
)
answer = converse_response['output']['message']['content'][0]['text']
```

**검색과 생성을 분리하여 각 단계를 직접 제어합니다.**

| 장점 | 단점 |
|------|------|
| 프롬프트 자유롭게 커스터마이징 | 코드가 복잡 (API 2회 호출) |
| 대화 이력(conversation history) 관리 가능 | 인용 정보를 직접 구성해야 함 |
| 검색 결과를 중간에서 필터링/가공 가능 | LLM 추론 파라미터 직접 관리 필요 |
| 다양한 LLM 모델 교체 쉬움 | |

### 두 방식의 사용 시점

| 상황 | 추천 방식 |
|------|----------|
| 빠른 프로토타이핑 | `retrieve_and_generate` |
| 단순 Q&A 시스템 | `retrieve_and_generate` |
| 대화형 챗봇 | `retrieve + converse` |
| 프롬프트 튜닝이 필요한 경우 | `retrieve + converse` |
| 검색 결과 후처리 필요 | `retrieve + converse` |

---

## 4. Bedrock 클라이언트 구분

boto3에서 Bedrock 관련 클라이언트는 3종류입니다:

| 클라이언트 | 용도 | 이 프로젝트에서 사용하는 Lambda |
|-----------|------|------------------------------|
| `bedrock-agent-runtime` | KB 검색 및 RAG (`retrieve`, `retrieve_and_generate`) | rag-query, rag-converse |
| `bedrock-runtime` | 모델 직접 호출 (`converse`, `invoke_model`) | rag-converse |
| `bedrock-agent` | KB 관리 (`start_ingestion_job`, `create_knowledge_base`) | sync-knowledge-base |

```python
# 검색/생성 API용
bedrock_agent_runtime = boto3.client('bedrock-agent-runtime')

# 모델 직접 호출용
bedrock_runtime = boto3.client('bedrock-runtime')

# 관리 API용
bedrock_agent = boto3.client('bedrock-agent')
```

---

## 5. LLM 추론 파라미터

`converse()` API에 전달하는 `inferenceConfig`의 각 파라미터 의미:

```python
inferenceConfig={
    'maxTokens': 2000,       # 생성할 최대 토큰 수
    'temperature': 0,        # 0=결정적, 1=창의적
    'topP': 0.9,             # 누적 확률 기반 토큰 선택
    'stopSequences': [],     # 생성 중단 시퀀스
}
```

| 파라미터 | 값 | 설명 |
|---------|-----|------|
| `maxTokens` | 2000 | LLM이 생성할 최대 토큰 수. 한국어 1글자 약 2~3 토큰 |
| `temperature` | 0 | 0이면 항상 같은 답변(결정적). RAG에서는 사실 기반 답변을 위해 0 권장 |
| `topP` | 0.9 | 상위 90% 확률의 토큰 중에서 선택. 1.0이면 모든 토큰 후보 |
| `stopSequences` | [] | 이 문자열이 나오면 생성 중단. 빈 배열 = 중단 없음 |

---

## 6. 대화 이력 관리 패턴

`rag-converse` Lambda는 워크숍 `chatbot_lib.py` 패턴을 기반으로 대화 이력을 관리합니다:

```python
MAX_MESSAGES = 20

# 클라이언트에서 보내는 대화 이력
conversation_history = [
    {"role": "user", "content": "Bedrock이란?"},
    {"role": "assistant", "content": "Amazon Bedrock은..."},
    {"role": "user", "content": "더 자세히 알려줘"},
]

# Converse API 메시지 형식으로 변환
messages = []
for msg in conversation_history:
    messages.append({
        'role': msg['role'],
        'content': [{'text': msg['content']}],
    })
messages.append(user_message)  # 새 질문 추가

# MAX_MESSAGES 초과 시 오래된 메시지 삭제
if len(messages) > MAX_MESSAGES:
    excess = len(messages) - MAX_MESSAGES
    del messages[0:excess]
```

**왜 메시지 수를 제한하는가?**
- LLM의 컨텍스트 윈도우에 모든 대화를 넣을 수 없음
- 오래된 대화는 현재 질문과 관련성이 낮음
- 토큰 비용 절약

---

## 7. CDK Custom Resource와 cr.Provider 패턴

`sync-knowledge-base` Lambda는 CDK Custom Resource로 호출됩니다:

```
CloudFormation → cr.Provider (framework Lambda) → sync-knowledge-base (사용자 Lambda)
                   ↓
           CloudFormation에 응답 전송 (자동)
```

### cr.Provider의 동작 원리

1. CloudFormation이 Custom Resource 이벤트(Create/Update/Delete)를 발생
2. `cr.Provider`의 framework Lambda가 이벤트를 수신
3. framework Lambda가 사용자 Lambda(sync-knowledge-base)를 **동기적으로 호출**
4. 사용자 Lambda가 dict를 **반환** (return)
5. framework Lambda가 dict에서 `PhysicalResourceId`와 `Data`를 읽어 CloudFormation에 응답

### 사용자 Lambda의 반환값 규칙

```python
def handler(event, context):
    # 작업 수행...
    return {
        'PhysicalResourceId': 'sync-kb-xxxx',  # 리소스 식별자
        'Data': {                                # 출력 데이터 (선택)
            'IngestionJobId': 'job-xxxx',
        },
    }
```

> **주의**: `send_cfn_response()`를 직접 호출하면 framework Lambda도 응답을 보내므로 이중 응답 오류가 발생합니다. 반드시 dict 반환만 사용하세요.

---

## 8. Lambda 공통 패턴

### API Gateway 프록시 통합 응답 포맷

API Gateway Lambda 프록시 통합은 특정 형식의 응답을 요구합니다:

```python
def build_response(status_code, body):
    return {
        'statusCode': status_code,         # HTTP 상태 코드
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',           # CORS 허용
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'OPTIONS,POST',
        },
        'body': json.dumps(body, ensure_ascii=False),    # JSON 문자열
    }
```

| 필드 | 설명 |
|------|------|
| `statusCode` | HTTP 상태 코드 (200, 400, 500 등) |
| `headers` | CORS 헤더 포함 필수 (브라우저 호출 시) |
| `body` | **JSON 문자열** (dict가 아닌 `json.dumps()` 결과) |
| `ensure_ascii=False` | 한국어 문자를 유니코드 이스케이프 없이 출력 |

### 환경변수 패턴

Lambda 함수의 설정값은 CDK에서 환경변수로 주입합니다:

```python
# Lambda 측 (Python)
KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')

# CDK 측 (TypeScript)
environment: {
  KNOWLEDGE_BASE_ID: props.knowledgeBaseId,
}
```

이 패턴으로 코드에 하드코딩 없이 배포 환경에 따라 설정을 변경할 수 있습니다.

---

## 9. 워크숍 코드와 CDK Lambda 구현의 차이점

| 항목 | 워크숍 코드 | CDK Lambda 구현 |
|------|-----------|----------------|
| 실행 환경 | 로컬 Python 스크립트 | AWS Lambda (서버리스) |
| 벡터 스토어 | ChromaDB (로컬) | S3 Vectors (관리형) |
| 문서 검색 | ChromaDB 직접 쿼리 | Bedrock KB의 `retrieve()` API |
| LLM 호출 | `converse()` 직접 호출 | 동일하게 `converse()` 사용 |
| 설정 관리 | Python 변수 하드코딩 | 환경변수 + CDK config.ts |
| CORS | 불필요 (로컬) | API Gateway CORS 헤더 필수 |
| 에러 핸들링 | 최소 | HTTP 상태 코드 기반 구조화된 에러 응답 |

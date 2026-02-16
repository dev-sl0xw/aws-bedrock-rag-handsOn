# AWS Bedrock RAG Hands-On CDK 프로젝트 구현 계획

## Context

AWS Bedrock과 RAG(Retrieval-Augmented Generation) 실습을 위한 CDK(TypeScript) 프로젝트를 처음부터 구축합니다.
**에이전트 팀 모드**를 활용하여 병렬 실행으로 효율적으로 구현하며, 각 에이전트는 역할에 최적화된 MCP 서버를 1:1로 사용합니다.

**핵심 설계 원칙:**
- **AWS Free Tier 범위 내** 실습 가능하도록 아키텍처 설계
- **벡터 스토어**: S3 Vectors (사용량 기반 과금, 실습 수준에서 거의 무료)
- **LLM 모델**: Amazon Nova Lite ($0.06/$0.24 per MTok, 매우 저렴)
- **워크숍 패턴 반영**: Converse API 직접 호출 + 관리형 retrieve_and_generate 둘 다 지원

### 참고 자료
- [Building with Amazon Bedrock Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/10435111-3e2e-48bb-acb4-0b5111d7638e/ko-KR)
- [Amazon Bedrock과 RAG 알아보기 (YouTube)](https://youtu.be/ZKP6NqExUQw)
- [Amazon Bedrock과 RAG 실습편 (YouTube)](https://youtu.be/zXKXVY8gHiA)
- [aws-samples/amazon-bedrock-rag](https://github.com/aws-samples/amazon-bedrock-rag)
- [ottlseo/bedrock-rag-chatbot](https://github.com/ottlseo/bedrock-rag-chatbot)
- 워크숍 코드: `workshop/completed/rag/rag_lib.py`, `workshop/completed/rag_chatbot/rag_chatbot_lib.py`

### 프로젝트 설정
| 항목 | 값 |
|------|-----|
| 리전 | `us-east-1` |
| LLM | Amazon Nova Lite (`us.amazon.nova-lite-v1:0`) |
| LLM (대안) | Nova Micro (`us.amazon.nova-micro-v1:0`, 최저가), Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`) |
| 임베딩 | Titan Embeddings V2 (`amazon.titan-embed-text-v2:0`, 1024차원) |
| 벡터 스토어 | S3 Vectors (`aws_s3vectors`, CDK v2.238+) |
| 프론트엔드 | 로컬 Streamlit (AWS 배포 안함 - Free Tier 고려) |
| 문서 언어 | 한국어 |
| CDK 언어 | TypeScript |

> **비용 안내:** S3 Vectors는 사용량 기반 과금으로 실습 수준에서 거의 무료. Nova Lite도 매우 저렴 ($0.06/$0.24 per MTok). 실습 후 `cdk destroy --all` 실행 권장 (불필요한 리소스 방지).

---

## 1. 아키텍처

```
[사용자] → [로컬 Streamlit] → [API Gateway] → [Lambda]
                                                  ↓
                              ┌──────────────────────────────────┐
                              │  POST /query (관리형)             │
                              │  → RetrieveAndGenerate           │
                              ├──────────────────────────────────┤
                              │  POST /converse (워크숍 패턴)     │
                              │  → Retrieve + Converse API       │
                              └──────────────────────────────────┘
                                    /                    \
                          [Knowledge Base]          [Nova Lite]
                            /          \
                    [S3 문서]    [S3 Vectors]
                                  (Titan Embeddings V2)
```

### AWS 서비스 목록
| 서비스 | 용도 |
|--------|------|
| Amazon S3 | RAG 문서 저장소 |
| Amazon S3 Vectors | 벡터 데이터베이스 (임베딩 저장/검색) |
| Amazon Bedrock Knowledge Base | 관리형 RAG 워크플로우 엔진 |
| Amazon Bedrock (Nova Lite) | 응답 생성 LLM |
| Amazon Bedrock (Titan Embeddings V2) | 문서/쿼리 임베딩 모델 |
| AWS Lambda | RAG 쿼리 처리 백엔드 |
| Amazon API Gateway | REST API 엔드포인트 |
| AWS IAM | 서비스 간 권한 관리 |

### RAG 파이프라인 흐름
```
[데이터 수집]                              [쿼리 처리 - 2가지 방식]
문서 → S3 업로드                           사용자 질문
    ↓                                          ↓
KB 데이터 소스 동기화               ┌─────────────────────────┐
    ↓                               │ 방식 1: retrieve_and_   │
문서 청킹 (512 토큰, 20% 오버랩)   │ generate (관리형)        │
    ↓                               ├─────────────────────────┤
Titan Embeddings V2 벡터화         │ 방식 2: retrieve() +    │
    ↓                               │ converse() (워크숍 패턴) │
S3 Vectors 저장                    └─────────────────────────┘
                                          /              \
                                    벡터 검색         LLM 응답 생성
                                   (S3 Vectors)      (Nova Lite)
                                        \              /
                                     컨텍스트 + 질문 → 답변
                                            ↓
                                     인용 포함 응답 반환
```

---

## 2. 에이전트 팀 구성

### 팀명: `bedrock-rag-handson`

```
┌─────────────────────────────────────────────────────────────┐
│                     team-lead (나)                           │
│  Phase 1: 스캐폴딩 + MCP/에이전트 설정                       │
│  Phase 2: 팀 생성 + 태스크 할당                              │
│  Phase 5: 팀 종료 + 커밋                                    │
└─────────────┬──────────────┬──────────────┬─────────────────┘
              │              │              │
    ┌─────────▼────┐  ┌─────▼──────┐  ┌───▼──────────┐
    │  infra-cdk   │  │ lambda-dev │  │ frontend-doc │
    │              │  │            │  │              │
    │ MCP:         │  │ MCP:       │  │ MCP:         │
    │ cdk-mcp      │  │ core-mcp   │  │ context7     │
    │              │  │            │  │              │
    │ CDK 스택 5개  │  │ Lambda 3개 │  │ UI + 문서 4개 │
    └──────┬───────┘  └─────┬──────┘  └──────┬───────┘
           │                │                │
           └────────────────┼────────────────┘
                            │
                   ┌────────▼────────┐
                   │  qa-verifier    │
                   │                 │
                   │ MCP: iac-mcp    │
                   │ + ralph-loop    │
                   │                 │
                   │ 전체 검증       │
                   │ (최대 5회 반복) │
                   └─────────────────┘
```

### 에이전트 ↔ MCP 서버 1:1 매핑

| 에이전트 | 역할 | MCP 서버 (1:1) | 담당 태스크 |
|----------|------|----------------|------------|
| **infra-cdk** | CDK 인프라 아키텍트 | `awslabs-cdk-mcp-server` | Task #1~#5, #6, #7 |
| **lambda-dev** | Lambda 백엔드 개발자 | `awslabs-core-mcp-server` | Task #8, #8-2, #10 |
| **frontend-doc** | 프론트엔드 & 문서 | `context7` | Task #11~#14 |
| **qa-verifier** | 품질 검증자 (ralph-loop) | `awslabs-aws-iac-mcp-server` | Task #15 |

### MCP 서버 상세

1. **`awslabs-cdk-mcp-server`** → infra-cdk
   - CDK best practices, L2/L3 construct 패턴 조회
   - CDK Nag 보안 규칙 확인
   - Solutions Constructs 추천, Lambda 레이어, Bedrock 스키마 생성

2. **`awslabs-core-mcp-server`** → lambda-dev
   - AWS SDK (boto3) API 참조
   - Bedrock Agent Runtime API 패턴
   - Converse API 호출 패턴

3. **`context7`** → frontend-doc
   - Streamlit, boto3, requests 등 라이브러리 문서 조회
   - resolve-library-id → query-docs 워크플로우

4. **`awslabs-aws-iac-mcp-server`** → qa-verifier
   - CloudFormation 템플릿 검증
   - CDK 배포 트러블슈팅
   - IaC 모범 사례 확인

---

## 3. 프로젝트 구조

```
aws-bedrock-rag-handsOn/
├── .mcp.json                           # MCP 서버 설정 (3개 서버 + context7 글로벌)
├── .claude/
│   └── agents/
│       ├── infra-cdk.md                # CDK 인프라 에이전트 정의
│       ├── lambda-dev.md               # Lambda 개발 에이전트 정의
│       ├── frontend-doc.md             # 프론트엔드/문서 에이전트 정의
│       └── qa-verifier.md              # 검증 에이전트 정의 (ralph-loop)
├── docs/
│   └── implementation-plan.md          # 이 계획서
├── CLAUDE.md                           # 프로젝트 가이드 (한국어)
├── README.md                           # 사용자 문서 (한국어)
├── cdk.json                            # CDK 설정
├── package.json                        # Node.js 의존성 (CDK v2.238+)
├── tsconfig.json                       # TypeScript 설정
├── .gitignore
│
├── bin/
│   └── app.ts                          # CDK 앱 엔트리포인트 (4개 스택 연결)
│
├── lib/
│   ├── config.ts                       # 중앙 설정 (모델 ID, 벡터 버킷명 등)
│   ├── s3-stack.ts                     # S3 문서 버킷
│   ├── s3-vectors-stack.ts             # S3 Vectors 벡터 버킷 + 인덱스
│   ├── bedrock-kb-stack.ts             # Bedrock KB + 데이터 소스 (S3_VECTORS 설정)
│   └── api-stack.ts                    # Lambda + API Gateway
│
├── lambda/
│   ├── rag-query/
│   │   └── index.py                    # retrieve_and_generate 호출
│   ├── rag-converse/
│   │   └── index.py                    # Converse API 기반 RAG (워크숍 패턴)
│   └── sync-knowledge-base/
│       └── index.py                    # KB 동기화
│
├── frontend/
│   ├── app.py                          # Streamlit 챗봇 UI (로컬 실행)
│   └── requirements.txt                # streamlit, requests
│
├── sampledata/
│   └── amazon-bedrock-faq.txt          # RAG 테스트용 샘플 문서
│
├── workshop/                           # 참조용 워크숍 코드
│   ├── completed/rag/rag_lib.py        # Converse API + 벡터 검색 패턴
│   ├── completed/rag_chatbot/          # 챗봇 대화 이력 관리 패턴
│   └── data/bedrock_faqs.py            # 47개 Q&A 샘플 데이터
│
└── test/
    └── stacks.test.ts                  # CDK 스택 유닛 테스트
```

---

## 4. 구현 Phase별 상세

### Phase 1: 사전 준비 (team-lead 직접 수행)

team-lead가 직접 생성하는 기반 파일들:

| # | 작업 | 파일 |
|---|------|------|
| 1-1 | MCP 서버 설정 | `.mcp.json` |
| 1-2 | 에이전트 정의 | `.claude/agents/{infra-cdk,lambda-dev,frontend-doc,qa-verifier}.md` |
| 1-3 | 프로젝트 스캐폴딩 | `package.json`, `tsconfig.json`, `cdk.json`, `.gitignore` |
| 1-4 | 중앙 설정 | `lib/config.ts` |
| 1-5 | ralph-loop 활성화 | `~/.claude/settings.json` 수정 |
| 1-6 | Git 초기화 | `git init` |
| 1-7 | 의존성 설치 | `npm install` |

#### `.mcp.json` 설정
```json
{
  "mcpServers": {
    "awslabs-cdk-mcp-server": {
      "type": "stdio",
      "command": "uvx",
      "args": ["awslabs.cdk-mcp-server@latest"],
      "env": { "FASTMCP_LOG_LEVEL": "ERROR", "AWS_REGION": "us-east-1" }
    },
    "awslabs-core-mcp-server": {
      "type": "stdio",
      "command": "uvx",
      "args": ["awslabs.core-mcp-server@latest"],
      "env": { "FASTMCP_LOG_LEVEL": "ERROR", "AWS_REGION": "us-east-1", "solutions-architect": "true" }
    },
    "awslabs-aws-iac-mcp-server": {
      "type": "stdio",
      "command": "uvx",
      "args": ["awslabs.aws-iac-mcp-server@latest"],
      "env": { "FASTMCP_LOG_LEVEL": "ERROR", "AWS_REGION": "us-east-1" }
    }
  }
}
```

#### `lib/config.ts` 중앙 설정
```typescript
export const CONFIG = {
  projectPrefix: 'bedrock-rag-handson',

  // S3 Vectors (OpenSearch Serverless 대체)
  vectorBucketName: 'bedrock-rag-handson-vectors',
  indexName: 'bedrock-rag-index',

  // Bedrock 임베딩 모델
  embeddingModelId: 'amazon.titan-embed-text-v2:0',
  vectorDimension: 1024,

  // Bedrock 생성 모델 (LLM)
  // 워크숍 rag_lib.py에서도 사용하는 모델
  // 대안: us.amazon.nova-micro-v1:0 (최저가), anthropic.claude-3-haiku-20240307-v1:0
  generationModelId: 'us.amazon.nova-lite-v1:0',

  // S3 문서 버킷
  documentBucketPrefix: 'rag-documents',

  // Knowledge Base 청킹 설정
  chunkingStrategy: 'FIXED_SIZE' as const,
  chunkMaxTokens: 512,
  overlapPercentage: 20,

  // LLM 추론 설정 (워크숍 converse API 기본값)
  inferenceConfig: {
    maxTokens: 2000,
    temperature: 0,
    topP: 0.9,
    stopSequences: [] as string[],
  },

  // 대화 이력 관리 (워크숍 chatbot_lib.py 패턴)
  maxConversationMessages: 20,
};
```

---

### Phase 2: 팀 생성 및 태스크 할당

#### 2-1. 팀 생성
```
TeamCreate: bedrock-rag-handson
설명: "AWS Bedrock RAG CDK 프로젝트 - 4명의 에이전트가 병렬로 인프라, Lambda, 프론트엔드/문서를 구현하고 검증 에이전트가 최종 확인"
```

#### 2-2. 태스크 목록 (14개)

**infra-cdk 담당 (Task #1~#5, #6, #7):**

| # | 태스크 | 생성 파일 | blockedBy |
|---|--------|----------|-----------|
| 1 | S3 Stack 구현 | `lib/s3-stack.ts` | - |
| 2 | S3 Vectors Stack 구현 | `lib/s3-vectors-stack.ts` | - |
| 4 | Bedrock Knowledge Base Stack 구현 | `lib/bedrock-kb-stack.ts` | #1, #2 |
| 5 | API Stack 구현 | `lib/api-stack.ts` | #4 |
| 6 | CDK 앱 엔트리포인트 작성 | `bin/app.ts` | #1, #2, #4, #5 |
| 7 | CDK 스택 테스트 작성 | `test/stacks.test.ts` | #6 |

**lambda-dev 담당 (Task #8, #8-2, #10):**

| # | 태스크 | 생성 파일 | blockedBy |
|---|--------|----------|-----------|
| 8 | RAG 쿼리 Lambda 구현 (retrieve_and_generate) | `lambda/rag-query/index.py` | - |
| 8-2 | Converse API Lambda 구현 (워크숍 패턴) | `lambda/rag-converse/index.py` | - |
| 10 | KB 동기화 Lambda 구현 | `lambda/sync-knowledge-base/index.py` | - |

**frontend-doc 담당 (Task #11~#14):**

| # | 태스크 | 생성 파일 | blockedBy |
|---|--------|----------|-----------|
| 11 | Streamlit 챗봇 UI 구현 | `frontend/app.py`, `requirements.txt` | - |
| 12 | 샘플 데이터 작성 | `sampledata/amazon-bedrock-faq.txt` | - |
| 13 | CLAUDE.md 작성 | `CLAUDE.md` | - |
| 14 | README.md 작성 | `README.md` | - |

**qa-verifier 담당 (Task #15):**

| # | 태스크 | 범위 | blockedBy |
|---|--------|------|-----------|
| 15 | Ralph-Loop 전체 검증 | 전체 프로젝트 | #1~#14 (모든 태스크 완료 후) |

#### 2-3. 에이전트 스폰

**병렬 실행 (동시 시작):**
```
Task(infra-cdk):    general-purpose, team_name=bedrock-rag-handson
Task(lambda-dev):   general-purpose, team_name=bedrock-rag-handson
Task(frontend-doc): general-purpose, team_name=bedrock-rag-handson
```

**후속 실행 (Phase 3 완료 후):**
```
Task(qa-verifier):  general-purpose, team_name=bedrock-rag-handson
→ ralph-loop 패턴으로 검증
```

---

### Phase 3: 병렬 작업 상세

#### infra-cdk 에이전트 (MCP: awslabs-cdk-mcp-server)

**Task #1: lib/s3-stack.ts**
- S3 버킷 생성 (문서 저장용)
- SSL 강제 (버킷 정책), 퍼블릭 액세스 차단
- `removalPolicy: DESTROY` + `autoDeleteObjects: true`
- CfnOutput: bucketArn, bucketName

**Task #2: lib/s3-vectors-stack.ts**
- S3 Vectors 벡터 버킷 + 인덱스 생성
- CDK v2.238+ `aws_s3vectors` 모듈 사용
- CfnOutput: vectorBucketArn, indexArn

```typescript
import { aws_s3vectors as s3vectors } from 'aws-cdk-lib';

// CfnVectorBucket
const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', {
  vectorBucketName: `${CONFIG.projectPrefix}-vectors`,
});

// CfnIndex (dimension: 1024, cosine)
const vectorIndex = new s3vectors.CfnIndex(this, 'VectorIndex', {
  vectorBucketName: vectorBucket.vectorBucketName!,
  indexName: CONFIG.indexName,
  dataType: 'float32',
  dimension: CONFIG.vectorDimension,
  distanceMetric: 'cosine',
});
```

**Task #4: lib/bedrock-kb-stack.ts**
- IAM 역할: `s3vectors:PutVectors`, `s3vectors:GetVectors`, `s3vectors:DeleteVectors`, `s3vectors:QueryVectors`, `s3vectors:GetIndex`, `bedrock:InvokeModel`, `s3:GetObject`, `s3:ListBucket`
- CfnKnowledgeBase (VECTOR 타입, S3_VECTORS 스토리지)
- CfnDataSource (S3 타입, FIXED_SIZE 청킹: 512 토큰, 20% 오버랩)
- CfnOutput: knowledgeBaseId, dataSourceId

```typescript
storageConfiguration: {
  type: 'S3_VECTORS',
  s3VectorsConfiguration: {
    vectorBucketArn: vectorBucket.attrVectorBucketArn,
    indexArn: vectorIndex.attrIndexArn,
    indexName: CONFIG.indexName,
  },
}
```

**Task #5: lib/api-stack.ts**
- Lambda 2개:
  - `rag-query` (Python 3.12): `retrieve_and_generate()` 호출
  - `rag-converse` (Python 3.12): `retrieve()` + `converse()` 호출 (워크숍 패턴)
- 환경변수: KNOWLEDGE_BASE_ID, MODEL_ARN (+ GENERATION_MODEL_ID for converse)
- IAM: `bedrock:RetrieveAndGenerate`, `bedrock:Retrieve`, `bedrock:InvokeModel`
- REST API Gateway:
  - `POST /query` → rag-query Lambda (관리형)
  - `POST /converse` → rag-converse Lambda (워크숍 패턴)
  - CORS 활성화
- CfnOutput: API 엔드포인트 URL

**Task #6: bin/app.ts**
- 4개 스택 인스턴스화
- addDependency로 의존성 체인 설정:
  ```
  S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
  ```
- env: account + region (CDK_DEFAULT_ACCOUNT/REGION)

**Task #7: test/stacks.test.ts**
- 각 스택 스냅샷 테스트
- 주요 리소스 속성 어서션

#### lambda-dev 에이전트 (MCP: awslabs-core-mcp-server)

**Task #8: lambda/rag-query/index.py**
```python
# bedrock-agent-runtime 클라이언트
# retrieve_and_generate() API 호출
# 환경변수: KNOWLEDGE_BASE_ID, MODEL_ARN
# 인용(citations) 추출
# CORS 헤더 포함 응답
# API Gateway 프록시 통합 포맷
```

**Task #8-2: lambda/rag-converse/index.py** (신규, 워크숍 패턴)
```python
# 워크숍 rag_lib.py 패턴 기반
# bedrock-agent-runtime 클라이언트로 retrieve() (검색만)
# bedrock-runtime 클라이언트로 converse() (LLM 직접 호출)
#
# 워크숍 메시지 포맷:
# message = {
#     "role": "user",
#     "content": [
#         { "text": rag_content },           # 검색된 컨텍스트
#         { "text": "Based on the content above, please answer the following question:" },
#         { "text": question }                # 사용자 질문
#     ]
# }
#
# converse() 호출:
# response = bedrock.converse(
#     modelId="us.amazon.nova-lite-v1:0",
#     messages=[message] + conversation_history,
#     inferenceConfig={
#         "maxTokens": 2000, "temperature": 0, "topP": 0.9, "stopSequences": []
#     },
# )
#
# 대화 이력 지원 (MAX_MESSAGES=20)
# 참조: workshop/completed/rag/rag_lib.py
# 참조: workshop/completed/rag_chatbot/rag_chatbot_lib.py
#
# 환경변수: KNOWLEDGE_BASE_ID, GENERATION_MODEL_ID
# CORS 헤더 포함 응답
```

**Task #10: lambda/sync-knowledge-base/index.py**
```python
# CDK Custom Resource 핸들러
# bedrock-agent 클라이언트
# start_ingestion_job() 호출
# 환경변수: KNOWLEDGE_BASE_ID, DATA_SOURCE_ID
```

#### frontend-doc 에이전트 (MCP: context7)

**Task #11: frontend/app.py + requirements.txt**
- Streamlit 채팅 UI (워크숍 `rag_chatbot_app.py` 패턴 반영)
- `st.chat_input` + `st.chat_message` + `st.container()`
- `st.session_state.chat_history = []` 세션 관리
- `st.spinner("Working...")` + `st.expander("See search results")`
- API Gateway 엔드포인트 URL 사이드바 입력
- 엔드포인트 선택: `/query` (관리형) 또는 `/converse` (워크숍 패턴)
- requests로 POST 호출
- 인용 출처 표시

**Task #12: sampledata/amazon-bedrock-faq.txt**
- `workshop/data/bedrock_faqs.py`의 47개 Q&A 쌍 직접 활용
- Amazon Bedrock FAQ (한국어 + 영어)
- RAG 검색 테스트에 적합한 Q&A 형태

**Task #13: CLAUDE.md**
- 프로젝트 개요, 아키텍처 다이어그램
- 스택 의존성 순서 (4개 스택), CDK 명령어
- lib/config.ts 설정값 참조
- 비용 안내 (S3 Vectors + Nova Lite), 에이전트 팀 구성 설명

**Task #14: README.md**
- 사전 준비사항 (AWS CLI, Node.js, CDK v2.238+, Bedrock 모델 액세스)
- 설치 및 배포 가이드
- API 테스트 curl 예시 (`/query` + `/converse` 모두)
- Streamlit 로컬 실행 방법
- 정리 가이드 (cdk destroy)

---

### Phase 4: Ralph-Loop 검증 (qa-verifier)

모든 병렬 작업(#1~#14) 완료 후 qa-verifier 에이전트가 실행됩니다.

#### 실행 방식
```bash
/ralph-loop "aws-bedrock-rag-handsOn 프로젝트 전체 검증. 다음 체크리스트를 모두 통과해야 함:
1. npx tsc --noEmit 타입 체크 통과
2. npx cdk synth 로 4개 스택 CloudFormation 합성 성공
3. 모든 Python Lambda 파일 구문 에러 없음 (python3 -m py_compile)
4. lib/config.ts의 설정값이 모든 스택에서 올바르게 참조됨
5. 스택 간 의존성 및 CfnOutput 크로스 참조 정확
6. CLAUDE.md/README.md 내용이 실제 코드와 일치
7. 보안: S3 퍼블릭 차단, IAM 최소 권한
awslabs-aws-iac-mcp-server를 활용하여 CloudFormation 템플릿을 검증하라." \
--max-iterations 5 --completion-promise "ALL_CHECKS_PASSED"
```

#### 검증 체크리스트

| 영역 | 검증 항목 |
|------|----------|
| CDK 빌드 | `tsc --noEmit` 통과, `cdk synth` 4개 스택 합성 성공 |
| 코드 품질 | TypeScript 타입 안전성, Python 구문 에러 없음, 하드코딩 없음 |
| 보안 | S3 퍼블릭 차단, IAM 최소 권한, CORS 설정 |
| 아키텍처 | 스택 의존성 체인 (4개), CfnOutput 참조, Lambda 환경변수 |
| 문서 | CLAUDE.md/README.md 정확성, 비용 안내 |
| 프론트엔드 | Streamlit 구문 에러, API 호출 로직, requirements.txt |

**검증 실패 시:** qa-verifier가 직접 코드 수정 → 재검증 (최대 5회 반복)

---

### Phase 5: 팀 종료 + 커밋

1. 4명 에이전트 셧다운 (SendMessage: shutdown_request)
2. TeamDelete: bedrock-rag-handson
3. `git add` + `git commit`

---

## 5. 실행 타임라인

```
Phase 1: 사전 준비 (team-lead) ─────────────────────────────
├─ .mcp.json 생성 ✅ (완료)
├─ .claude/agents/*.md 4개 생성 ✅ (완료)
├─ 프로젝트 스캐폴딩 ✅ (완료)
│  (package.json, tsconfig, cdk.json, .gitignore)
├─ lib/config.ts 생성 ✅ (완료)
├─ ralph-loop 플러그인 활성화
├─ git init
└─ npm install

Phase 2: 팀 생성 + 태스크 할당 (team-lead) ─────────────────
├─ TeamCreate: bedrock-rag-handson
├─ TaskCreate × 14
└─ 에이전트 3명 병렬 스폰

Phase 3: 병렬 작업 ─────────────────────────────────────────
│ infra-cdk          │ lambda-dev        │ frontend-doc     │
│ ← cdk-mcp-server → │ ← core-mcp →     │ ← context7 →     │
│                     │                   │                  │
│ #1: S3 Stack        │ #8:  RAG Lambda   │ #11: Streamlit   │
│ #2: S3 Vectors Stack│ #8-2: Converse    │ #12: Sample Data │
│ #4: KB Stack        │       Lambda      │ #13: CLAUDE.md   │
│ #5: API Stack       │ #10: Sync Lambda  │ #14: README.md   │
│ #6: app.ts          │                   │                  │
│ #7: Tests           │                   │                  │
─────────────────────────────────────────────────────────────

Phase 4: 검증 (qa-verifier) ────────────────────────────────
├─ ← iac-mcp-server + ralph-loop →
├─ #15: 전체 검증
├─ TypeScript 빌드 / CDK synth / Python 검증
├─ 보안 / 아키텍처 / 문서 검증
└─ 이슈 발견 → 수정 → 재검증 (최대 5회)

Phase 5: 팀 종료 + 커밋 ───────────────────────────────────
├─ 에이전트 셧다운
├─ TeamDelete
└─ git commit
```

---

## 6. 워크숍 코드 참조 매핑

### CDK 구성요소 ↔ 워크숍 대응 테이블

| CDK 구성요소 | 워크숍 코드 경로 | 대응 패턴 |
|-------------|----------------|-----------|
| `lib/s3-vectors-stack.ts` | (워크숍: ChromaDB 로컬) | 벡터 스토어를 S3 Vectors로 관리형 대체 |
| `lambda/rag-query/index.py` | - | Bedrock KB 관리형 retrieve_and_generate |
| `lambda/rag-converse/index.py` | `workshop/completed/rag/rag_lib.py` | `converse()` 직접 호출 패턴 |
| `frontend/app.py` | `workshop/completed/rag_chatbot/rag_chatbot_app.py` | Streamlit 챗봇 UI 패턴 |
| 대화 이력 관리 | `workshop/completed/rag_chatbot/rag_chatbot_lib.py` | `MAX_MESSAGES=20`, `ChatMessage` 클래스 |
| 샘플 데이터 | `workshop/data/bedrock_faqs.py` | 47개 Q&A 쌍 |

### Bedrock API 패턴 코드 예시

**1. Converse API 직접 호출 (워크숍 rag_lib.py 패턴)**
```python
# workshop/completed/rag/rag_lib.py 기반
response = bedrock.converse(
    modelId="us.amazon.nova-lite-v1:0",
    messages=[{
        "role": "user",
        "content": [
            {"text": rag_content},
            {"text": "Based on the content above, please answer the following question:"},
            {"text": question}
        ]
    }],
    inferenceConfig={
        "maxTokens": 2000,
        "temperature": 0,
        "topP": 0.9,
        "stopSequences": []
    },
)
answer = response['output']['message']['content'][0]['text']
```

**2. retrieve_and_generate (관리형 RAG)**
```python
response = bedrock_agent.retrieve_and_generate(
    input={"text": query},
    retrieveAndGenerateConfiguration={
        "type": "KNOWLEDGE_BASE",
        "knowledgeBaseConfiguration": {
            "knowledgeBaseId": kb_id,
            "modelArn": model_arn,
        }
    }
)
```

**3. retrieve (검색만, converse Lambda에서 사용)**
```python
response = bedrock_agent.retrieve(
    knowledgeBaseId=kb_id,
    retrievalQuery={"text": question},
    retrievalConfiguration={
        "vectorSearchConfiguration": {"numberOfResults": 4}
    }
)
contexts = [r['content']['text'] for r in response['retrievalResults']]
```

**4. 대화 이력 관리 (워크숍 chatbot_lib.py 패턴)**
```python
MAX_MESSAGES = 20

# 이력이 MAX_MESSAGES 초과 시 오래된 메시지 삭제
if len(message_history) > MAX_MESSAGES:
    excess = len(message_history) - MAX_MESSAGES
    del message_history[0 : excess * 2]  # user+assistant 쌍 단위 삭제
```

**5. Streamlit 챗봇 UI (워크숍 rag_chatbot_app.py 패턴)**
```python
st.set_page_config(page_title="RAG Chatbot")
st.title("RAG Chatbot")

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

chat_container = st.container()
input_text = st.chat_input("Chat with your bot here")

if input_text:
    # API 호출 후 chat_history에 추가

for message in st.session_state.chat_history:
    with chat_container.chat_message(message.role):
        st.markdown(message.text)
```

---

## 7. 검증 방법 (배포 테스트)

배포 테스트는 Phase 4 이후 수동으로 진행합니다.

```bash
# 1. CDK Synth (CloudFormation 템플릿 확인)
npx cdk synth

# 2. 전체 스택 배포
npx cdk deploy --all --require-approval broadening

# 3. 샘플 데이터 S3 업로드
aws s3 cp sampledata/ s3://BUCKET_NAME/ --recursive

# 4. Knowledge Base 동기화
# AWS 콘솔 > Bedrock > Knowledge bases > 데이터 소스 > Sync 클릭

# 5. API 테스트 (관리형 retrieve_and_generate)
curl -X POST https://API_ENDPOINT/prod/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Amazon Bedrock이란 무엇인가요?"}'

# 6. API 테스트 (Converse API 워크숍 패턴)
curl -X POST https://API_ENDPOINT/prod/converse \
  -H 'Content-Type: application/json' \
  -d '{"query": "Amazon Bedrock이란 무엇인가요?", "conversation_history": []}'

# 7. Streamlit 로컬 실행
cd frontend
pip install -r requirements.txt
streamlit run app.py

# 8. 정리 (불필요한 리소스 방지)
npx cdk destroy --all
```

---

## 8. 주요 고려사항

| 항목 | 설명 |
|------|------|
| **Bedrock 모델 액세스** | 배포 전 AWS 콘솔에서 Titan Embeddings V2 + Nova Lite 액세스 활성화 필수 (CDK 자동화 불가) |
| **CDK 버전** | S3 Vectors (`aws_s3vectors`) 모듈은 CDK v2.234+ 필요 → `^2.238.0` 사용 |
| **S3 Vectors 비용** | 사용량 기반 과금, 실습 수준에서 거의 무료 (기존 OpenSearch Serverless ~$174/월 대비 대폭 절감) |
| **Nova Lite 비용** | $0.06/$0.24 per MTok (기존 Claude 3.7 Sonnet $3/$15 대비 50~60배 절감) |
| **Docker** | Lambda Python 패키지 번들링에 Docker 불필요 (boto3 런타임 내장) |
| **ralph-loop 플러그인** | 현재 비활성화 → Phase 1에서 활성화 필요 |
| **팀 모드** | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` + `teammateMode: "tmux"` 이미 설정됨 |
| **리전 요구사항** | us-east-1 권장 (Bedrock KB + S3 Vectors 지원) |

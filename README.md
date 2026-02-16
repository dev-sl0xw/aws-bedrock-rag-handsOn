# AWS Bedrock RAG Hands-On (CDK)

AWS Bedrock과 RAG(Retrieval-Augmented Generation)를 **실습을 통해 학습**하는 CDK 프로젝트입니다.

S3 Vectors를 벡터 스토어로, Amazon Nova Lite를 LLM으로 사용하여 서버리스 RAG 파이프라인을 구축합니다. AWS Free Tier 범위 내에서 실습 가능하도록 설계되었습니다.

## 아키텍처

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

### CDK 스택 구조 (4개 스택)

```
S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
```

| 스택 | 역할 |
|------|------|
| **S3Stack** | RAG 원본 문서를 저장하는 S3 버킷 |
| **S3VectorsStack** | S3 Vectors 벡터 버킷 + 인덱스 (CDK v2.238+) |
| **BedrockKbStack** | Bedrock Knowledge Base + 데이터 소스 (FIXED_SIZE 청킹) |
| **ApiStack** | Lambda 2개 + REST API Gateway (`/query`, `/converse`) |

### 학습 내용

- **RAG 파이프라인**: 문서 수집 → 임베딩 → 벡터 저장 → 검색 → LLM 응답 생성
- **Bedrock API 두 가지 방식**: `retrieve_and_generate`(관리형) vs `retrieve`+`converse`(직접 호출)
- **AWS CDK**: Infrastructure as Code로 AWS 리소스 정의 및 배포
- **서버리스 아키텍처**: Lambda + API Gateway + S3
- **벡터 데이터베이스**: S3 Vectors를 활용한 임베딩 저장과 유사도 검색

## 사전 준비사항

### 필수 도구

| 도구 | 최소 버전 | 확인 명령어 |
|------|----------|------------|
| Node.js | 18+ | `node --version` |
| npm | 9+ | `npm --version` |
| AWS CLI | 2.x | `aws --version` |
| AWS CDK | 2.238+ | `npx cdk --version` |
| Python | 3.12+ | `python3 --version` |

### AWS 설정

1. **AWS CLI 자격 증명 설정**
   ```bash
   aws configure
   # 또는 SSO 사용
   aws configure sso
   ```

2. **리전 설정**: `us-east-1` (Bedrock KB + S3 Vectors 지원 필수)

3. **Bedrock 모델 액세스 활성화** (AWS 콘솔에서 수동 설정)
   - [Amazon Bedrock 콘솔](https://console.aws.amazon.com/bedrock/) → Model access → Manage model access
   - **Titan Text Embeddings V2** 활성화
   - **Amazon Nova Lite** 활성화

> **중요**: 모델 액세스는 CDK로 자동화할 수 없으므로, 배포 전 반드시 콘솔에서 활성화해야 합니다.

## 설치 및 배포

### 1. 프로젝트 클론 및 의존성 설치

```bash
git clone <REPOSITORY_URL>
cd aws-bedrock-rag-handsOn
npm install
```

### 2. CDK 부트스트랩 (최초 1회)

```bash
npx cdk bootstrap aws://<ACCOUNT_ID>/us-east-1
```

### 3. 빌드 및 검증

```bash
# TypeScript 타입 체크
npx tsc --noEmit

# CloudFormation 템플릿 합성 (4개 스택)
npx cdk synth
```

### 4. 배포

```bash
npx cdk deploy --all --require-approval broadening
```

배포 완료 후 API Gateway 엔드포인트 URL이 출력됩니다.

### 5. 샘플 데이터 업로드

```bash
# S3 버킷 이름은 배포 출력에서 확인
aws s3 cp sampledata/ s3://<BUCKET_NAME>/ --recursive
```

### 6. Knowledge Base 동기화

배포 시 Custom Resource Lambda가 자동으로 초기 동기화를 실행합니다.
수동 동기화가 필요한 경우:
- AWS 콘솔 → Bedrock → Knowledge bases → 데이터 소스 → **Sync** 클릭

## API 테스트

### 관리형 RAG (`/query`)

`retrieve_and_generate` API를 사용하여 한 번의 호출로 검색과 응답 생성을 처리합니다.

```bash
curl -X POST https://<API_ENDPOINT>/prod/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "Amazon Bedrock이란 무엇인가요?"}'
```

### 워크숍 패턴 RAG (`/converse`)

`retrieve` + `converse` API를 분리 호출하여 검색과 생성을 직접 제어합니다. 대화 이력을 지원합니다.

```bash
curl -X POST https://<API_ENDPOINT>/prod/converse \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Amazon Bedrock이란 무엇인가요?",
    "conversation_history": []
  }'
```

#### 대화 이력이 있는 후속 질문

```bash
curl -X POST https://<API_ENDPOINT>/prod/converse \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "가격은 어떻게 되나요?",
    "conversation_history": [
      {"role": "user", "content": "Amazon Bedrock이란 무엇인가요?"},
      {"role": "assistant", "content": "Amazon Bedrock은..."}
    ]
  }'
```

## Streamlit 프론트엔드 실행

```bash
cd frontend
pip install -r requirements.txt
streamlit run app.py
```

사이드바에서 API Gateway 엔드포인트 URL을 입력하고, `/query` 또는 `/converse` 모드를 선택하여 채팅할 수 있습니다.

## 프로젝트 구조

```
aws-bedrock-rag-handsOn/
├── bin/app.ts                          # CDK 앱 엔트리포인트 (4개 스택 연결)
├── lib/
│   ├── config.ts                       # 중앙 설정 (모델 ID, 벡터 버킷명 등)
│   ├── s3-stack.ts                     # S3 문서 버킷
│   ├── s3-vectors-stack.ts             # S3 Vectors 벡터 버킷 + 인덱스
│   ├── bedrock-kb-stack.ts             # Bedrock KB + 데이터 소스
│   └── api-stack.ts                    # Lambda 2개 + API Gateway
├── lambda/
│   ├── rag-query/index.py              # retrieve_and_generate 호출
│   ├── rag-converse/index.py           # retrieve + converse (워크숍 패턴)
│   └── sync-knowledge-base/index.py    # KB 동기화 트리거
├── frontend/
│   ├── app.py                          # Streamlit 챗봇 UI
│   └── requirements.txt
├── sampledata/
│   └── amazon-bedrock-faq.txt          # RAG 테스트용 샘플 문서
└── docs/
    └── implementation-plan.md          # 구현 계획서
```

## 설정 변경

모든 설정은 `lib/config.ts`에서 관리합니다.

| 설정 | 기본값 | 설명 |
|------|--------|------|
| `generationModelId` | `us.amazon.nova-lite-v1:0` | LLM 모델 |
| `embeddingModelId` | `amazon.titan-embed-text-v2:0` | 임베딩 모델 |
| `vectorDimension` | `1024` | 벡터 차원 (임베딩 모델에 따라 결정) |
| `chunkMaxTokens` | `512` | 문서 청킹 최대 토큰 |
| `overlapPercentage` | `20` | 청크 간 오버랩 비율 (%) |
| `maxConversationMessages` | `20` | 대화 이력 최대 메시지 수 |

### LLM 모델 변경

`lib/config.ts`의 `generationModelId`를 변경하여 다른 모델을 사용할 수 있습니다:

| 모델 | ID | 비용 (입력/출력 per MTok) |
|------|-----|--------------------------|
| **Nova Lite** (기본) | `us.amazon.nova-lite-v1:0` | $0.06 / $0.24 |
| Nova Micro (최저가) | `us.amazon.nova-micro-v1:0` | $0.035 / $0.14 |
| Claude 3 Haiku | `anthropic.claude-3-haiku-20240307-v1:0` | $0.25 / $1.25 |

## 비용 안내

이 프로젝트는 실습 비용을 최소화하도록 설계되었습니다:

- **S3 Vectors**: 사용량 기반 과금, 실습 수준에서 거의 무료 (기존 OpenSearch Serverless ~$174/월 대비)
- **Nova Lite**: $0.06/$0.24 per MTok (기존 Claude 3.7 Sonnet $3/$15 대비 50~60배 절감)
- **Lambda / API Gateway / S3**: Free Tier 범위 내

> **실습 후 반드시 리소스를 정리하세요.** 불필요한 과금을 방지합니다.

## 정리 (리소스 삭제)

```bash
# 전체 스택 삭제
npx cdk destroy --all

# S3 버킷 데이터 삭제 확인 프롬프트에 'y' 입력
```

`removalPolicy: DESTROY`로 설정되어 있어 모든 리소스가 깨끗하게 삭제됩니다.

## 워크숍 참조

이 프로젝트는 다음 워크숍 자료를 기반으로 합니다:

- [Building with Amazon Bedrock Workshop](https://catalog.us-east-1.prod.workshops.aws/workshops/10435111-3e2e-48bb-acb4-0b5111d7638e/ko-KR)
- [Amazon Bedrock과 RAG 알아보기 (YouTube)](https://youtu.be/ZKP6NqExUQw)
- [Amazon Bedrock과 RAG 실습편 (YouTube)](https://youtu.be/zXKXVY8gHiA)
- [aws-samples/amazon-bedrock-rag](https://github.com/aws-samples/amazon-bedrock-rag)

`workshop/` 디렉토리에 원본 워크숍 코드가 포함되어 있으며, 구현 시 참조로 사용됩니다.

## 라이선스

MIT

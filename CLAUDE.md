# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 프로젝트 개요

AWS Bedrock과 RAG(Retrieval-Augmented Generation) **실습을 통한 학습** 프로젝트입니다.
CDK(TypeScript)로 서버리스 RAG 파이프라인을 구축하며, S3 Vectors를 벡터 스토어로, Amazon Nova Lite를 LLM으로 사용합니다. AWS Free Tier 범위 내에서 실습 가능하도록 설계되었습니다.

### 학습 목표
이 프로젝트를 통해 다음 개념들을 실습합니다:
- **RAG 파이프라인**: 문서 수집 → 임베딩 → 벡터 저장 → 검색 → LLM 응답 생성의 전체 흐름
- **AWS CDK**: Infrastructure as Code로 AWS 리소스를 정의하고 배포하는 방법
- **Bedrock API**: retrieve_and_generate(관리형) vs retrieve+converse(직접 호출) 두 가지 RAG 방식
- **서버리스 아키텍처**: Lambda + API Gateway + S3의 이벤트 기반 백엔드 패턴
- **벡터 데이터베이스**: S3 Vectors를 활용한 임베딩 저장과 유사도 검색

## 빌드 및 배포 명령어

```bash
npm run build              # TypeScript 컴파일
npx tsc --noEmit           # 타입 체크만 (컴파일 없이)
npx cdk synth              # CloudFormation 템플릿 합성 (4개 스택)
npx cdk deploy --all --require-approval broadening   # 전체 스택 배포
npx cdk destroy --all      # 전체 스택 삭제 (실습 후 반드시 실행)
npm test                   # Jest 테스트 실행
python3 -m py_compile lambda/rag-query/index.py      # Python 구문 검증
```

## 아키텍처

4개 CDK 스택이 의존성 체인으로 연결됩니다:
```
S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
```

- **S3Stack**: RAG 원본 문서를 저장하는 S3 버킷
- **S3VectorsStack**: S3 Vectors 벡터 버킷 + 인덱스 (`aws_s3vectors` 모듈, CDK v2.238+)
- **BedrockKbStack**: Bedrock Knowledge Base (S3_VECTORS 스토리지) + 데이터 소스 (FIXED_SIZE 청킹)
- **ApiStack**: Lambda 2개 + API Gateway
  - `POST /query` — 관리형 `retrieve_and_generate` API (한 번의 호출로 검색+생성)
  - `POST /converse` — 워크숍 패턴 `retrieve()` + `converse()` 직접 호출 (검색과 생성을 분리)

## 중앙 설정

모든 설정 상수는 `lib/config.ts`에 집중되어 있습니다. 스택과 Lambda에서 하드코딩 대신 반드시 이 파일을 참조하세요.

주요 설정값:
- `generationModelId: 'us.amazon.nova-lite-v1:0'` — LLM (대안: Nova Micro, Claude 3 Haiku)
- `embeddingModelId: 'amazon.titan-embed-text-v2:0'` — 임베딩 모델
- `vectorDimension: 1024` — 벡터 차원
- `chunkMaxTokens: 512`, `overlapPercentage: 20` — 청킹 설정
- `inferenceConfig` — Converse API 추론 파라미터 (temperature, maxTokens 등)

## Lambda 함수 (Python 3.12)

| Lambda | 경로 | 역할 |
|--------|------|------|
| rag-query | `lambda/rag-query/index.py` | `retrieve_and_generate()` 관리형 RAG 호출 |
| rag-converse | `lambda/rag-converse/index.py` | `retrieve()` + `converse()` 워크숍 패턴 |
| sync-knowledge-base | `lambda/sync-knowledge-base/index.py` | `start_ingestion_job()` KB 동기화 |

모든 Lambda는 boto3 런타임 내장을 사용하여 외부 의존성이 필요 없습니다.

## 워크숍 참조 코드

`workshop/` 디렉토리에 원본 워크숍 코드가 있습니다. 구현 시 반드시 참고하세요:
- `workshop/completed/rag/rag_lib.py` — Converse API + 벡터 검색 패턴 (Nova Lite)
- `workshop/completed/rag_chatbot/rag_chatbot_lib.py` — 대화 이력 관리 (MAX_MESSAGES=20, ChatMessage 클래스)
- `workshop/completed/rag_chatbot/rag_chatbot_app.py` — Streamlit 챗봇 UI 패턴
- `workshop/data/bedrock_faqs.py` — 47개 Q&A 쌍 샘플 데이터

## 에이전트 팀 모드

4명의 에이전트가 1:1 MCP 서버 매핑으로 병렬 작업합니다:

| 에이전트 | MCP 서버 | 담당 범위 |
|---------|----------|----------|
| infra-cdk | awslabs-cdk-mcp-server | CDK 스택, bin/app.ts, 테스트 |
| lambda-dev | awslabs-core-mcp-server | Lambda 함수 3개 |
| frontend-doc | context7 | Streamlit UI, 문서, 샘플 데이터 |
| qa-verifier | awslabs-aws-iac-mcp-server | 전체 검증 (ralph-loop) |

에이전트 정의: `.claude/agents/*.md`, 전체 구현 계획: `docs/implementation-plan.md`

## 학습 목적 코드 작성 가이드라인

이 프로젝트의 핵심 목적은 **실습을 통한 학습**입니다. 코드를 작성하거나 수정할 때 다음 규칙을 따르세요.

### 1. 소스코드 주석 규칙

모든 소스 파일에 **한국어 학습 주석**을 포함합니다:

- **파일 상단**: 이 파일이 전체 아키텍처에서 어떤 역할을 하는지 설명
- **핵심 로직**: "무엇을 하는 코드인지"와 "왜 이렇게 하는지" 설명
- **AWS API 호출**: API의 목적, 요청/응답 구조, 관련 AWS 서비스 설명
- **설정값**: 각 설정이 의미하는 바와 변경 시 영향 설명

주석 접두사 `[학습]`을 사용하여 학습 목적 주석임을 표시합니다:

```typescript
// [학습] CfnVectorBucket은 S3 Vectors의 핵심 리소스입니다.
// 일반 S3 버킷과 달리 벡터 데이터를 저장하고 유사도 검색을 지원합니다.
// dimension(1024)은 Titan Embeddings V2 모델의 출력 벡터 차원입니다.
```

```python
# [학습] retrieve_and_generate()는 Bedrock의 관리형 RAG API입니다.
# 하나의 API 호출로 "벡터 검색 → 컨텍스트 조합 → LLM 응답 생성"을 모두 처리합니다.
# 반면 retrieve() + converse() 방식은 각 단계를 직접 제어할 수 있어
# 프롬프트 커스터마이징이나 대화 이력 관리에 더 유연합니다.
```

### 2. summary.md 파일 규칙

각 실습 폴더에 `summary.md` 파일을 생성하여 **이론과 개념**을 정리합니다:

| 경로 | 다루는 내용 |
|------|-----------|
| `lib/summary.md` | CDK 스택 개념, S3 Vectors, Bedrock KB, IAM 역할, 서버리스 패턴 |
| `lambda/summary.md` | RAG 이론, Bedrock API 두 가지 방식, 임베딩/벡터 검색 원리, Lambda 패턴 |
| `frontend/summary.md` | Streamlit 실행 모델, 챗봇 UI 패턴, REST API 흐름, 인용 표시 |

summary.md 작성 규칙:
- 한국어로 작성
- 해당 폴더의 코드가 다루는 AWS 서비스와 개념을 설명
- "왜 이 기술을 선택했는가" (예: OpenSearch → S3 Vectors 변경 이유)
- 핵심 개념을 코드 예시와 함께 설명
- 워크숍 원본 코드와 CDK 구현의 차이점 설명

## 중요 사항

- 리전: `us-east-1` (Bedrock KB + S3 Vectors 지원 필수)
- Bedrock 모델 액세스: 배포 전 AWS 콘솔에서 Titan Embeddings V2 + Nova Lite 수동 활성화 필요
- 모든 문서와 사용자 대면 텍스트는 한국어로 작성
- CDK 스택은 `removalPolicy: DESTROY` 사용 (실습 후 쉬운 정리)
- 크로스 스택 참조: CfnOutput + Props 인터페이스 패턴
- 비용: S3 Vectors(사용량 기반) + Nova Lite($0.06/$0.24 MTok)로 실습 비용 최소화

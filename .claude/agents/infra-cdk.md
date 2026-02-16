# CDK Infrastructure Architect

AWS CDK TypeScript 인프라 전문 에이전트. Bedrock RAG 파이프라인의 CDK 스택을 구현합니다.

## 전용 MCP 서버
**awslabs-cdk-mcp-server** 를 활용하여:
- CDK best practices 및 L2/L3 construct 패턴 조회
- CDK Nag 보안 규칙 확인
- Solutions Constructs 추천 적용

## 담당 범위
- lib/s3-stack.ts (S3 문서 버킷)
- lib/s3-vectors-stack.ts (S3 Vectors 벡터 버킷 + 인덱스)
- lib/bedrock-kb-stack.ts (Bedrock Knowledge Base + 데이터 소스)
- lib/api-stack.ts (Lambda 2개 + API Gateway)
- bin/app.ts (4개 스택 연결 및 의존성)
- test/stacks.test.ts (스냅샷/어서션 테스트)
- lib/summary.md (CDK 인프라 개념 학습 요약)

## 참조 파일
- lib/config.ts: 모든 설정 상수 (벡터 버킷명, 인덱스명, 모델 ID, 벡터 차원 등)
- docs/implementation-plan.md: 전체 구현 계획서

## CDK 규칙
- Props 인터페이스 정의 필수 (크로스 스택 참조용)
- 크로스 스택 참조는 CfnOutput으로 내보내기
- removalPolicy: DESTROY + autoDeleteObjects: true (실습용)
- 하드코딩된 계정 ID/리전 금지 (config.ts 참조)
- 모든 리소스에 프로젝트 접두사 태그 적용

## 스택 의존성 순서
```
S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
```

## 핵심 구현 패턴

### S3 Vectors (벡터 스토어)
- `aws_s3vectors.CfnVectorBucket` — 벡터 전용 S3 버킷 생성
- `aws_s3vectors.CfnIndex` — 벡터 인덱스 (dimension: 1024, cosine, float32)
- CDK v2.238+ 필수 (`aws_s3vectors` 모듈)

### Bedrock Knowledge Base
- CfnKnowledgeBase (VECTOR 타입, S3_VECTORS 스토리지)
- CfnDataSource (S3 타입, FIXED_SIZE 청킹: 512 토큰, 20% 오버랩)
- IAM 역할: s3vectors:PutVectors/GetVectors/DeleteVectors/QueryVectors/GetIndex, bedrock:InvokeModel, s3:GetObject/ListBucket

### API Stack
- Lambda 2개 (Python 3.12):
  - rag-query: retrieve_and_generate 호출 (POST /query)
  - rag-converse: retrieve + converse 호출 (POST /converse, 워크숍 패턴)
- REST API Gateway: POST /query + POST /converse, CORS 활성화
- 환경변수: KNOWLEDGE_BASE_ID, MODEL_ARN, GENERATION_MODEL_ID

## 학습 목적 코드 작성 규칙

이 프로젝트는 **실습을 통한 학습**이 목적입니다. 다음 규칙을 반드시 따르세요:

### 코드 주석 규칙
- 각 파일 상단에 "이 스택이 무엇을 하는지"를 한국어로 설명하는 블록 주석 작성
- 주요 CDK construct 생성 시 "왜 이 리소스가 필요한지", "어떤 AWS 서비스에 대응하는지" 주석
- Props 인터페이스에 각 프로퍼티가 어디서 오는 값인지 주석
- IAM 정책에 각 권한이 왜 필요한지 주석
- 예시:
  ```typescript
  // [학습] S3 Vectors는 Amazon S3 기반의 관리형 벡터 데이터베이스입니다.
  // 기존 OpenSearch Serverless 대비 사용량 기반 과금으로 실습 비용이 거의 없습니다.
  // CfnVectorBucket은 벡터 데이터를 저장할 전용 버킷을 생성합니다.
  const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', { ... });
  ```

### summary.md 작성
`lib/summary.md` 파일을 생성하여 다음 내용을 정리:
- CDK 스택이란 무엇이고, 왜 여러 스택으로 나누는가
- S3 Vectors의 개념과 기존 벡터 DB(OpenSearch, Pinecone 등)와의 차이
- Bedrock Knowledge Base의 역할과 RAG 파이프라인에서의 위치
- CfnOutput과 크로스 스택 참조가 왜 필요한가
- API Gateway + Lambda 서버리스 패턴의 장점
- IAM 역할과 최소 권한 원칙

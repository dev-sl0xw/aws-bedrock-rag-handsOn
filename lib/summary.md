# CDK 인프라 스택 학습 정리

이 문서는 `lib/` 폴더의 CDK 스택 코드가 다루는 AWS 서비스와 핵심 개념을 정리합니다.

---

## 1. AWS CDK 핵심 개념

### Infrastructure as Code (IaC)

AWS CDK는 TypeScript, Python 등의 프로그래밍 언어로 클라우드 인프라를 정의하는 IaC 도구입니다. CDK 코드를 작성하면 `cdk synth` 명령으로 CloudFormation 템플릿(JSON/YAML)으로 변환되고, `cdk deploy`로 실제 AWS 리소스가 생성됩니다.

```
TypeScript 코드 → cdk synth → CloudFormation 템플릿 → cdk deploy → AWS 리소스
```

### Construct 레벨

CDK의 리소스 추상화는 3단계로 나뉩니다:

| 레벨 | 접두사 | 설명 | 이 프로젝트 예시 |
|------|--------|------|-----------------|
| L1 | `Cfn*` | CloudFormation 리소스를 1:1 매핑. 모든 속성을 직접 지정해야 함 | `CfnKnowledgeBase`, `CfnVectorBucket`, `CfnIndex` |
| L2 | 없음 | 합리적인 기본값과 편의 메서드 제공 | `s3.Bucket`, `lambda.Function` |
| L3 | 패턴 | 여러 리소스를 조합한 고수준 패턴 | `apigateway.RestApi` |

Bedrock Knowledge Base와 S3 Vectors는 비교적 새로운 서비스라 L2 Construct가 없어 L1(`Cfn*`)을 사용합니다. 반면 S3 버킷이나 Lambda는 성숙한 L2 Construct를 사용합니다.

### 스택(Stack)과 의존성

CDK 앱은 여러 스택으로 구성되며, 각 스택은 하나의 CloudFormation 스택으로 배포됩니다. 이 프로젝트의 4개 스택은 의존성 체인으로 연결됩니다:

```
S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
(문서 저장)   (벡터 저장)     (RAG 엔진)     (API 엔드포인트)
```

여러 스택으로 나누는 이유:
- **독립 배포**: Lambda 코드만 수정하면 ApiStack만 재배포하면 됨
- **변경 영향 범위 파악**: S3 버킷 설정 변경 시 하위 스택만 영향
- **CloudFormation 제한 분산**: 스택당 리소스 500개 제한 회피

### 크로스 스택 참조 패턴

스택 간 데이터 전달은 두 가지 방법을 사용합니다:

**방법 1: Props 인터페이스** (이 프로젝트에서 사용)
```typescript
// 선언 측 (BedrockKbStack)
export interface BedrockKbStackProps extends cdk.StackProps {
  documentBucketArn: string;   // S3Stack에서 받을 값
}

// 전달 측 (bin/app.ts)
const bedrockKbStack = new BedrockKbStack(app, 'BedrockRagKbStack', {
  documentBucketArn: s3Stack.bucketArn,  // S3Stack의 public 속성 참조
});
```

내부적으로 CDK는 이를 CloudFormation의 `Fn::ImportValue` + `Export`로 변환합니다.

**방법 2: SSM Parameter Store** (대규모 프로젝트에서 사용)

스택이 많아지면 Parameter Store에 값을 저장하고 다른 스택에서 읽는 방식이 더 유연합니다.

---

## 2. S3 — 문서 저장소 (`s3-stack.ts`)

### Amazon S3란?

Amazon S3(Simple Storage Service)는 객체 스토리지 서비스로, 이 프로젝트에서 RAG 원본 문서(PDF, TXT 등)를 저장합니다. Bedrock Knowledge Base가 이 버킷의 문서를 읽어 임베딩으로 변환합니다.

### 보안 설정

```typescript
const documentBucket = new s3.Bucket(this, 'DocumentBucket', {
  blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,  // 퍼블릭 접근 차단
  enforceSSL: true,                                    // HTTPS만 허용
  encryption: s3.BucketEncryption.S3_MANAGED,          // AES-256 서버 사이드 암호화
  removalPolicy: cdk.RemovalPolicy.DESTROY,            // cdk destroy 시 삭제
  autoDeleteObjects: true,                             // 버킷 내 객체도 자동 삭제
});
```

| 설정 | 의미 | 왜 필요한가 |
|------|------|------------|
| `blockPublicAccess` | S3 버킷의 퍼블릭 접근을 완전 차단 | 문서가 외부에 노출되지 않도록 보호 |
| `enforceSSL` | HTTP 요청을 거부하는 버킷 정책 자동 추가 | 전송 중 데이터 암호화 보장 |
| `encryption: S3_MANAGED` | 저장 시 AES-256으로 자동 암호화 | 저장 데이터(data at rest) 보호 |
| `removalPolicy: DESTROY` | CloudFormation 스택 삭제 시 버킷도 삭제 | 실습 후 리소스 정리를 쉽게 |
| `autoDeleteObjects` | 버킷 삭제 전 내부 객체를 Lambda로 자동 삭제 | S3 버킷은 비어있어야 삭제 가능하므로 |

> **주의**: `DESTROY` + `autoDeleteObjects`는 실습용 설정입니다. 프로덕션에서는 `RETAIN`을 사용하여 실수로 데이터가 삭제되지 않도록 합니다.

---

## 3. S3 Vectors — 벡터 데이터베이스 (`s3-vectors-stack.ts`)

### S3 Vectors란?

S3 Vectors는 Amazon S3 기반의 관리형 벡터 데이터베이스입니다. 텍스트를 수치 벡터(임베딩)로 변환하여 저장하고, 유사도 검색을 수행합니다.

### OpenSearch Serverless에서 S3 Vectors로 전환한 이유

| 항목 | OpenSearch Serverless | S3 Vectors |
|------|----------------------|------------|
| 최소 비용 | ~$174/월 (2 OCU 상시 가동) | 사용량 기반 과금 (실습 수준 거의 무료) |
| 설정 복잡도 | Collection, Index, Security Policy 등 다수 | VectorBucket + Index 2개 리소스 |
| 관리 부담 | 인덱스 매핑, 샤드 설정 필요 | 완전 관리형, 설정 최소 |
| CDK 지원 | L1만 지원 (복잡) | L1 지원 (간단) |

실습 프로젝트에서 월 $174는 부담이 크므로, S3 Vectors로 전환하여 비용을 거의 0으로 줄였습니다.

### 핵심 리소스

**CfnVectorBucket**: 벡터 데이터 저장 전용 버킷
```typescript
const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', {
  vectorBucketName: 'bedrock-rag-handson-vectors',
});
```

**CfnIndex**: 벡터 인덱스 정의
```typescript
const vectorIndex = new s3vectors.CfnIndex(this, 'VectorIndex', {
  vectorBucketName: vectorBucket.vectorBucketName!,
  indexName: 'bedrock-rag-index',
  dataType: 'float32',        // 벡터 값 타입
  dimension: 1024,             // Titan Embeddings V2 출력 차원
  distanceMetric: 'cosine',    // 유사도 측정 방법
});
```

### 벡터 차원(dimension)과 거리 메트릭(distanceMetric)

- **dimension: 1024**: 임베딩 모델의 출력 벡터 크기. Titan Embeddings V2는 1024차원 벡터를 생성합니다. 모델을 바꾸면 이 값도 변경해야 합니다.
- **distanceMetric: cosine**: 두 벡터의 방향 유사도를 측정합니다. 1에 가까울수록 유사. 텍스트 검색에 가장 일반적으로 사용됩니다.
  - `cosine`: 방향 유사도 (텍스트 검색에 적합)
  - `euclidean`: 거리 기반 (공간 데이터에 적합)
  - `dotProduct`: 내적 (정규화된 벡터에 적합)

---

## 4. Bedrock Knowledge Base — RAG 엔진 (`bedrock-kb-stack.ts`)

### Amazon Bedrock Knowledge Base란?

Knowledge Base는 Bedrock의 관리형 RAG 엔진으로, 다음 파이프라인을 자동화합니다:

```
문서(S3) → 청킹 → 임베딩(Titan V2) → 벡터 저장(S3 Vectors)
                                            ↓
질문 → 임베딩(Titan V2) → 벡터 검색(S3 Vectors) → 컨텍스트 + 질문 → LLM 응답
```

### IAM 역할과 최소 권한 원칙

Knowledge Base는 여러 AWS 서비스에 접근해야 하므로, 전용 IAM 역할을 생성합니다:

```typescript
const kbRole = new iam.Role(this, 'KnowledgeBaseRole', {
  assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
});
```

**필요한 권한과 이유:**

| 권한 | 대상 리소스 | 이유 |
|------|-----------|------|
| `s3vectors:PutVectors` | 벡터 버킷 | 임베딩 벡터를 저장 |
| `s3vectors:QueryVectors` | 벡터 버킷 | 유사도 검색 수행 |
| `s3vectors:GetVectors/DeleteVectors/GetIndex` | 벡터 버킷 | 벡터 조회/삭제/인덱스 확인 |
| `bedrock:InvokeModel` | Titan Embeddings V2 모델 | 문서/질문을 벡터로 변환 |
| `s3:GetObject`, `s3:ListBucket` | 문서 버킷 | 원본 문서 읽기 |

> **IAM 주의사항**: IAM Role의 `description` 속성은 ASCII/Latin-1 문자만 허용합니다. 한국어를 넣으면 배포 시 오류가 발생합니다.

### 청킹(Chunking) 설정

```typescript
chunkingConfiguration: {
  chunkingStrategy: 'FIXED_SIZE',
  fixedSizeChunkingConfiguration: {
    maxTokens: 512,            // 각 청크의 최대 토큰 수
    overlapPercentage: 20,     // 인접 청크 간 20% 겹침
  },
}
```

**왜 청킹이 필요한가?**
- LLM의 컨텍스트 윈도우에 전체 문서를 넣을 수 없으므로, 관련 부분만 검색하기 위해 문서를 작은 조각으로 분할
- **오버랩(20%)**: 청크 경계에서 잘린 정보가 누락되지 않도록, 인접 청크의 끝부분과 시작부분이 겹침

### Custom Resource를 통한 자동 동기화

CDK 배포 후 `start_ingestion_job()`을 자동 실행하여 사용자가 수동 Sync를 하지 않아도 됩니다:

```typescript
const syncProvider = new cr.Provider(this, 'SyncProvider', {
  onEventHandler: syncLambda,  // sync-knowledge-base Lambda
});
new cdk.CustomResource(this, 'SyncKbTrigger', {
  serviceToken: syncProvider.serviceToken,
});
```

> **중요**: `cr.Provider`를 사용할 때, 사용자 Lambda에서 CloudFormation 응답을 직접 보내면 안 됩니다. framework Lambda가 응답을 자동 처리하므로, 사용자 Lambda는 dict를 반환하기만 하면 됩니다.

---

## 5. API Stack — 서버리스 백엔드 (`api-stack.ts`)

### 서버리스 아키텍처란?

서버를 직접 관리하지 않고, 요청이 들어올 때만 코드가 실행되는 아키텍처입니다:

| 특성 | 전통적 서버 | 서버리스 (Lambda + API Gateway) |
|------|-----------|-------------------------------|
| 비용 | 24/7 서버 비용 발생 | 요청 시에만 비용 (Free Tier: 월 100만 건 무료) |
| 확장 | 수동 스케일링 | 자동 확장 (동시 수백 요청 처리) |
| 관리 | OS 패치, 보안 업데이트 필요 | AWS가 인프라 관리 |

### Lambda IAM 최소 권한

각 Lambda에 필요한 권한만 분리 부여합니다:

```
rag-query Lambda:
  bedrock:RetrieveAndGenerate → Resource: '*' (리소스 수준 정책 미지원)
  bedrock:Retrieve            → Resource: knowledge-base/*
  bedrock:InvokeModel         → Resource: 특정 모델 ARN

rag-converse Lambda:
  bedrock:Retrieve    → Resource: knowledge-base/*
  bedrock:InvokeModel → Resource: 특정 모델 ARN
```

> `RetrieveAndGenerate`는 AWS가 리소스 수준 정책을 지원하지 않아 `Resource: '*'`를 사용해야 합니다. 이는 AWS 서비스의 제한이지 보안 문제가 아닙니다.

### API Gateway와 CORS

```typescript
const api = new apigateway.RestApi(this, 'RagApi', {
  defaultCorsPreflightOptions: {
    allowOrigins: apigateway.Cors.ALL_ORIGINS,
    allowMethods: apigateway.Cors.ALL_METHODS,
    allowHeaders: ['Content-Type'],
  },
});
```

**CORS(Cross-Origin Resource Sharing)**: 브라우저는 보안상 다른 도메인의 API를 호출할 때 제한합니다. Streamlit 앱(localhost)에서 API Gateway(amazonaws.com)를 호출하려면 CORS 설정이 필요합니다.

---

## 6. 중앙 설정 패턴 (`config.ts`)

모든 설정값을 `config.ts`에 집중하여 하드코딩을 방지합니다:

```typescript
export const CONFIG = {
  embeddingModelId: 'amazon.titan-embed-text-v2:0',
  generationModelId: 'us.amazon.nova-lite-v1:0',
  vectorDimension: 1024,
  chunkMaxTokens: 512,
  // ...
};
```

**장점:**
- 모델을 변경하려면 config.ts 한 곳만 수정
- 스택과 Lambda에서 동일한 설정값을 참조하므로 불일치 방지
- 코드 리뷰 시 설정 변경 사항을 한눈에 파악 가능

---

## 7. 비용 요약

| 서비스 | 과금 방식 | 실습 예상 비용 |
|--------|----------|--------------|
| S3 | 저장 용량 + 요청 수 | 거의 무료 (5GB 무료) |
| S3 Vectors | 사용량 기반 | 거의 무료 |
| Lambda | 실행 횟수 + 시간 | Free Tier (월 100만 건) |
| API Gateway | 요청 수 | Free Tier (월 100만 건, 12개월) |
| Bedrock (Nova Lite) | 입출력 토큰 | $0.06/$0.24 per MTok |
| Bedrock (Titan Embeddings V2) | 입력 토큰 | $0.02 per MTok |

> 실습 후 반드시 `npx cdk destroy --all`을 실행하여 불필요한 리소스를 삭제하세요.

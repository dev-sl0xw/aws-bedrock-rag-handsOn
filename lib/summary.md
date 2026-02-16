# CDK 인프라 학습 요약

## CDK 스택이란?

AWS CDK 스택은 CloudFormation 스택에 대응하는 단위로, 관련된 AWS 리소스들을 하나의 배포 단위로 묶습니다. 이 프로젝트는 4개 스택으로 구성됩니다:

```
S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
```

### 왜 여러 스택으로 나누는가?

- **독립 배포**: API Stack만 수정하면 API Stack만 재배포 (S3, KB는 그대로)
- **변경 범위 최소화**: 스택 간 의존성이 명확하여 영향 분석이 쉬움
- **CloudFormation 제한 분산**: 한 스택당 리소스 500개 제한을 분산

## S3 Vectors vs 기존 벡터 DB

| 항목 | S3 Vectors | OpenSearch Serverless | Pinecone |
|------|-----------|----------------------|----------|
| **과금** | 사용량 기반 | 최소 4 OCU (~$174/월) | 월 $70~ |
| **관리** | 완전 관리형 | AWS 관리형 | SaaS |
| **설정** | CDK 3줄 | 보안/네트워크 정책 필요 | 외부 API 연동 |
| **실습 비용** | 거의 무료 | ~$5/일 | 무료 티어 제한적 |

S3 Vectors는 CDK v2.238+에서 `aws_s3vectors` 모듈로 사용할 수 있으며, `CfnVectorBucket`(벡터 버킷)과 `CfnIndex`(벡터 인덱스)로 구성됩니다.

```typescript
// 벡터 버킷: 벡터 데이터를 저장하는 전용 S3 버킷
const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', {
  vectorBucketName: 'my-vectors',
});

// 벡터 인덱스: 벡터 검색을 위한 인덱스 정의
const vectorIndex = new s3vectors.CfnIndex(this, 'VectorIndex', {
  vectorBucketName: vectorBucket.vectorBucketName!,
  indexName: 'my-index',
  dimension: 1024,        // Titan Embeddings V2 출력 차원
  distanceMetric: 'cosine', // 코사인 유사도
  dataType: 'float32',
});
```

## Bedrock Knowledge Base

Knowledge Base는 RAG 파이프라인의 중심으로 다음을 관리합니다:

1. **데이터 수집(Ingestion)**: S3 문서 → 청킹 → 임베딩 → 벡터 저장
2. **검색(Retrieval)**: 사용자 쿼리 → 임베딩 → 벡터 유사도 검색 → 관련 문서 반환

### storageConfiguration

```typescript
storageConfiguration: {
  type: 'S3_VECTORS',  // 벡터 저장소 타입
  s3VectorsConfiguration: {
    vectorBucketArn: '...',
    indexArn: '...',
  },
}
```

## CfnOutput과 크로스 스택 참조

CDK에서 스택 간 데이터를 전달하는 패턴:

1. **내보내는 스택**: `CfnOutput`으로 값을 출력하고, public 속성으로 노출
2. **받는 스택**: Props 인터페이스로 타입을 정의하고, 생성 시 값을 전달
3. **연결**: `bin/app.ts`에서 스택을 인스턴스화할 때 Props로 값을 전달

```typescript
// 내보내는 스택 (S3Stack)
public readonly bucketArn: string;

// 받는 스택 (BedrockKbStack)
export interface BedrockKbStackProps extends cdk.StackProps {
  documentBucketArn: string;
}

// 연결 (bin/app.ts)
const bedrockKbStack = new BedrockKbStack(app, 'KbStack', {
  documentBucketArn: s3Stack.bucketArn,
});
```

## API Gateway + Lambda 서버리스 패턴

- **비용**: 요청이 없으면 비용 없음 (Free Tier: 100만 요청/월)
- **확장**: 트래픽 증가 시 자동 확장 (동시 실행 제한 관리)
- **CORS**: 브라우저에서 API를 호출하려면 CORS 설정 필수

## IAM 최소 권한 원칙

각 서비스에 필요한 최소한의 권한만 부여합니다:

| 서비스 | 필요 권한 | 이유 |
|--------|----------|------|
| KB → S3 Vectors | PutVectors, QueryVectors 등 | 벡터 저장/검색 |
| KB → S3 | GetObject, ListBucket | 원본 문서 읽기 |
| KB → Bedrock | InvokeModel | 임베딩 모델 호출 |
| Lambda → Bedrock | RetrieveAndGenerate, Retrieve, InvokeModel | RAG API 호출 |

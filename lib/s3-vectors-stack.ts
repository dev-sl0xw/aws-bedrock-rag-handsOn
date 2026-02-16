/**
 * [학습] S3 Vectors Stack - 벡터 데이터베이스
 *
 * 이 스택은 임베딩 벡터를 저장하고 유사도 검색을 수행하는 벡터 데이터베이스를 생성합니다.
 * S3 Vectors는 Amazon S3 기반의 관리형 벡터 데이터베이스로,
 * 기존 OpenSearch Serverless(~$174/월)와 달리 사용량 기반 과금으로 실습 비용이 거의 없습니다.
 *
 * 주요 리소스:
 * - CfnVectorBucket: 벡터 데이터를 저장할 전용 버킷
 * - CfnIndex: 벡터 인덱스 (차원, 거리 메트릭, 데이터 타입 정의)
 *
 * 스택 의존성 체인에서의 위치:
 * S3Stack → [S3VectorsStack] → BedrockKbStack → ApiStack
 */
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { aws_s3vectors as s3vectors } from 'aws-cdk-lib';
import { CONFIG } from './config';

export class S3VectorsStack extends cdk.Stack {
  // [학습] BedrockKbStack에서 Knowledge Base의 storageConfiguration으로 사용됩니다.
  public readonly vectorBucketArn: string;
  public readonly vectorBucketName: string;
  public readonly indexArn: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // [학습] CfnVectorBucket은 S3 Vectors의 핵심 리소스입니다.
    // 일반 S3 버킷과 달리 벡터 데이터를 저장하고 유사도 검색을 지원합니다.
    // CDK v2.238+ 에서 aws_s3vectors 모듈을 통해 사용할 수 있습니다.
    const vectorBucket = new s3vectors.CfnVectorBucket(this, 'VectorBucket', {
      vectorBucketName: CONFIG.vectorBucketName,
    });

    // [학습] CfnIndex는 벡터 인덱스를 정의합니다.
    // - dimension: 임베딩 모델의 출력 벡터 차원 (Titan V2 = 1024)
    // - distanceMetric: 벡터 간 유사도 측정 방법 (cosine = 코사인 유사도)
    // - dataType: 벡터 값의 데이터 타입 (float32 = 32비트 부동소수점)
    // dimension 값은 사용하는 임베딩 모델에 따라 달라집니다.
    const vectorIndex = new s3vectors.CfnIndex(this, 'VectorIndex', {
      vectorBucketName: vectorBucket.vectorBucketName!,
      indexName: CONFIG.indexName,
      dataType: 'float32',
      dimension: CONFIG.vectorDimension,
      distanceMetric: 'cosine',
    });

    // [학습] CfnIndex는 CfnVectorBucket에 의존하므로 명시적 의존성을 설정합니다.
    vectorIndex.addDependency(vectorBucket);

    this.vectorBucketArn = vectorBucket.attrVectorBucketArn;
    this.vectorBucketName = vectorBucket.vectorBucketName!;
    this.indexArn = vectorIndex.attrIndexArn;

    new cdk.CfnOutput(this, 'VectorBucketArn', {
      value: vectorBucket.attrVectorBucketArn,
      description: 'S3 Vectors 벡터 버킷 ARN',
    });

    new cdk.CfnOutput(this, 'VectorBucketNameOutput', {
      value: vectorBucket.vectorBucketName!,
      description: 'S3 Vectors 벡터 버킷 이름',
    });

    new cdk.CfnOutput(this, 'VectorIndexArn', {
      value: vectorIndex.attrIndexArn,
      description: 'S3 Vectors 벡터 인덱스 ARN',
    });
  }
}

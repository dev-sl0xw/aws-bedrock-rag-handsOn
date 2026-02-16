#!/usr/bin/env node
/**
 * [학습] CDK 앱 엔트리포인트 - 4개 스택 연결 및 의존성 설정
 *
 * 이 파일은 CDK 앱의 시작점으로, 4개의 스택을 인스턴스화하고
 * 스택 간 의존성과 데이터 흐름을 설정합니다.
 *
 * 스택 의존성 체인:
 * S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
 *
 * 왜 여러 스택으로 나누는가?
 * - 각 스택은 독립적으로 배포/업데이트 가능
 * - 스택 간 의존성이 명확하여 변경 영향 범위를 파악하기 쉬움
 * - CloudFormation 리소스 제한(500개)을 분산
 */
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { S3Stack } from '../lib/s3-stack';
import { S3VectorsStack } from '../lib/s3-vectors-stack';
import { BedrockKbStack } from '../lib/bedrock-kb-stack';
import { ApiStack } from '../lib/api-stack';

const app = new cdk.App();

// [학습] 환경 설정
// CDK_DEFAULT_ACCOUNT/REGION은 aws configure로 설정한 값을 사용합니다.
// Bedrock KB와 S3 Vectors가 지원되는 us-east-1을 기본으로 합니다.
const env = {
  account: process.env.CDK_DEFAULT_ACCOUNT,
  region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
};

// [학습] 1단계: S3 문서 버킷 (의존성 없음)
const s3Stack = new S3Stack(app, 'BedrockRagS3Stack', { env });

// [학습] 2단계: S3 Vectors 벡터 스토어 (의존성 없음, S3Stack과 병렬 가능)
const s3VectorsStack = new S3VectorsStack(app, 'BedrockRagS3VectorsStack', { env });

// [학습] 3단계: Bedrock Knowledge Base (S3 + S3Vectors 필요)
// Props로 이전 스택의 리소스 정보를 전달합니다.
const bedrockKbStack = new BedrockKbStack(app, 'BedrockRagKbStack', {
  env,
  documentBucketArn: s3Stack.bucketArn,
  documentBucketName: s3Stack.bucketName,
  vectorBucketArn: s3VectorsStack.vectorBucketArn,
  indexArn: s3VectorsStack.indexArn,
});

// [학습] 4단계: API Gateway + Lambda (Knowledge Base 필요)
const apiStack = new ApiStack(app, 'BedrockRagApiStack', {
  env,
  knowledgeBaseId: bedrockKbStack.knowledgeBaseId,
});

// [학습] addDependency로 스택 배포 순서를 강제합니다.
// CloudFormation은 의존성이 없는 스택을 병렬로 배포하므로,
// 명시적 의존성 없이는 아직 생성되지 않은 리소스를 참조할 수 있습니다.
bedrockKbStack.addDependency(s3Stack);
bedrockKbStack.addDependency(s3VectorsStack);
apiStack.addDependency(bedrockKbStack);

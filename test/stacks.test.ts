/**
 * [학습] CDK 스택 유닛 테스트
 *
 * CDK에서는 Template.fromStack()으로 CloudFormation 템플릿을 검증합니다.
 * hasResourceProperties: 특정 리소스가 예상 속성을 가지는지 확인
 * resourceCountIs: 특정 유형의 리소스 개수 확인
 */
import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import { S3Stack } from '../lib/s3-stack';
import { S3VectorsStack } from '../lib/s3-vectors-stack';
import { BedrockKbStack } from '../lib/bedrock-kb-stack';
import { ApiStack } from '../lib/api-stack';

describe('S3Stack', () => {
  test('S3 버킷이 생성됨', () => {
    const app = new cdk.App();
    const stack = new S3Stack(app, 'TestS3Stack');
    const template = Template.fromStack(stack);

    template.resourceCountIs('AWS::S3::Bucket', 1);
  });
});

describe('S3VectorsStack', () => {
  test('S3 Vectors 리소스가 생성됨', () => {
    const app = new cdk.App();
    const stack = new S3VectorsStack(app, 'TestS3VectorsStack');
    const template = Template.fromStack(stack);

    template.resourceCountIs('AWS::S3Vectors::VectorBucket', 1);
    template.resourceCountIs('AWS::S3Vectors::Index', 1);
  });
});

describe('BedrockKbStack', () => {
  test('Knowledge Base가 생성됨', () => {
    const app = new cdk.App();
    const stack = new BedrockKbStack(app, 'TestBedrockKbStack', {
      documentBucketArn: 'arn:aws:s3:::test-bucket',
      documentBucketName: 'test-bucket',
      vectorBucketArn: 'arn:aws:s3vectors:us-east-1:123456789012:vector-bucket/test-vectors',
      indexArn: 'arn:aws:s3vectors:us-east-1:123456789012:vector-bucket/test-vectors/index/test-index',
    });
    const template = Template.fromStack(stack);

    template.resourceCountIs('AWS::Bedrock::KnowledgeBase', 1);
    template.resourceCountIs('AWS::Bedrock::DataSource', 1);
  });
});

describe('ApiStack', () => {
  test('Lambda 함수 2개와 API Gateway가 생성됨', () => {
    const app = new cdk.App();
    const stack = new ApiStack(app, 'TestApiStack', {
      knowledgeBaseId: 'test-kb-id',
    });
    const template = Template.fromStack(stack);

    // rag-query + rag-converse 2개 Lambda
    template.resourceCountIs('AWS::Lambda::Function', 2);
    template.resourceCountIs('AWS::ApiGateway::RestApi', 1);
  });
});

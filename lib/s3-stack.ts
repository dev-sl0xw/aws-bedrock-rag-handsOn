/**
 * [학습] S3 Stack - RAG 원본 문서 저장용 S3 버킷
 *
 * 이 스택은 RAG 파이프라인의 첫 번째 단계인 "문서 저장소"를 생성합니다.
 * 사용자가 업로드한 문서(PDF, TXT 등)는 이 버킷에 저장되며,
 * Bedrock Knowledge Base가 이 버킷의 문서를 읽어 임베딩으로 변환합니다.
 *
 * 스택 의존성 체인에서의 위치:
 * [S3Stack] → S3VectorsStack → BedrockKbStack → ApiStack
 */
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { CONFIG } from './config';

export class S3Stack extends cdk.Stack {
  // [학습] 다른 스택에서 이 버킷을 참조할 수 있도록 public readonly로 노출합니다.
  // BedrockKbStack에서 데이터 소스로 이 버킷 ARN을 사용합니다.
  public readonly bucketArn: string;
  public readonly bucketName: string;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // [학습] S3 버킷 생성 - RAG 문서 저장소
    // blockPublicAccess: 퍼블릭 액세스를 완전히 차단하여 보안을 강화합니다.
    // enforceSSL: HTTPS를 통해서만 버킷에 접근할 수 있도록 강제합니다.
    // removalPolicy: DESTROY로 설정하면 cdk destroy 시 버킷도 함께 삭제됩니다.
    // autoDeleteObjects: 버킷 삭제 시 내부 객체도 자동 삭제합니다 (실습용 설정).
    const documentBucket = new s3.Bucket(this, 'DocumentBucket', {
      bucketName: `${CONFIG.projectPrefix}-${CONFIG.documentBucketPrefix}-${cdk.Aws.ACCOUNT_ID}`,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      // [학습] 서버 사이드 암호화(SSE)를 활성화합니다.
      // S3_MANAGED(AES-256)는 추가 비용 없이 저장 데이터를 암호화합니다.
      // 보안 모범 사례에 따라 모든 S3 버킷에 암호화를 적용해야 합니다.
      encryption: s3.BucketEncryption.S3_MANAGED,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });

    this.bucketArn = documentBucket.bucketArn;
    this.bucketName = documentBucket.bucketName;

    // [학습] CfnOutput은 CloudFormation 출력값으로,
    // 다른 스택에서 이 값을 참조하거나, 배포 후 콘솔에서 확인할 수 있습니다.
    new cdk.CfnOutput(this, 'DocumentBucketArn', {
      value: documentBucket.bucketArn,
      description: 'RAG 문서 저장 S3 버킷 ARN',
    });

    new cdk.CfnOutput(this, 'DocumentBucketName', {
      value: documentBucket.bucketName,
      description: 'RAG 문서 저장 S3 버킷 이름',
    });
  }
}

/**
 * [학습] Bedrock Knowledge Base Stack - RAG의 핵심 엔진
 *
 * 이 스택은 Amazon Bedrock Knowledge Base를 생성합니다.
 * Knowledge Base는 RAG 파이프라인의 중심으로, 다음을 관리합니다:
 * - 문서를 청크로 분할하고 임베딩으로 변환
 * - 벡터를 S3 Vectors에 저장
 * - 사용자 쿼리에 대한 벡터 검색 수행
 *
 * 스택 의존성 체인에서의 위치:
 * S3Stack → S3VectorsStack → [BedrockKbStack] → ApiStack
 */
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as bedrock from 'aws-cdk-lib/aws-bedrock';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import { CONFIG } from './config';

// [학습] Props 인터페이스는 크로스 스택 참조를 위한 타입 정의입니다.
// 다른 스택에서 생성한 리소스의 ARN/이름을 받아 이 스택에서 사용합니다.
export interface BedrockKbStackProps extends cdk.StackProps {
  /** S3Stack에서 생성한 문서 버킷 ARN */
  documentBucketArn: string;
  /** S3Stack에서 생성한 문서 버킷 이름 */
  documentBucketName: string;
  /** S3VectorsStack에서 생성한 벡터 버킷 ARN */
  vectorBucketArn: string;
  /** S3VectorsStack에서 생성한 벡터 인덱스 ARN */
  indexArn: string;
}

export class BedrockKbStack extends cdk.Stack {
  // [학습] ApiStack에서 Lambda 환경변수로 사용됩니다.
  public readonly knowledgeBaseId: string;
  public readonly dataSourceId: string;

  constructor(scope: Construct, id: string, props: BedrockKbStackProps) {
    super(scope, id, props);

    // [학습] Knowledge Base용 IAM 역할 생성
    // Bedrock 서비스가 이 역할을 Assume하여 다른 AWS 서비스에 접근합니다.
    const kbRole = new iam.Role(this, 'KnowledgeBaseRole', {
      assumedBy: new iam.ServicePrincipal('bedrock.amazonaws.com'),
      description: 'Bedrock Knowledge Base가 S3, S3 Vectors, Bedrock 모델에 접근하기 위한 역할',
    });

    // [학습] S3 Vectors 접근 권한
    // Knowledge Base가 벡터를 저장/조회/삭제하기 위해 필요합니다.
    // 각 권한의 용도:
    // - PutVectors: 임베딩 벡터 저장 (문서 수집 시)
    // - GetVectors: 벡터 조회
    // - DeleteVectors: 벡터 삭제 (문서 업데이트/삭제 시)
    // - QueryVectors: 유사도 검색 (사용자 쿼리 시)
    // - GetIndex: 인덱스 메타데이터 조회
    kbRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        's3vectors:PutVectors',
        's3vectors:GetVectors',
        's3vectors:DeleteVectors',
        's3vectors:QueryVectors',
        's3vectors:GetIndex',
      ],
      resources: [props.vectorBucketArn, `${props.vectorBucketArn}/*`],
    }));

    // [학습] Bedrock 임베딩 모델 호출 권한
    // 문서 청크를 벡터로 변환하기 위해 Titan Embeddings V2 모델을 호출합니다.
    kbRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:InvokeModel'],
      resources: [
        `arn:aws:bedrock:${this.region}::foundation-model/${CONFIG.embeddingModelId}`,
      ],
    }));

    // [학습] S3 문서 버킷 읽기 권한
    // Knowledge Base가 원본 문서를 읽어 청킹 → 임베딩 처리를 합니다.
    kbRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['s3:GetObject', 's3:ListBucket'],
      resources: [props.documentBucketArn, `${props.documentBucketArn}/*`],
    }));

    // [학습] CfnKnowledgeBase 생성
    // L1 Construct(Cfn*)는 CloudFormation 리소스를 직접 매핑합니다.
    // Bedrock Knowledge Base는 아직 L2 Construct가 없어 L1을 사용합니다.
    const knowledgeBase = new bedrock.CfnKnowledgeBase(this, 'KnowledgeBase', {
      name: `${CONFIG.projectPrefix}-kb`,
      roleArn: kbRole.roleArn,
      knowledgeBaseConfiguration: {
        type: 'VECTOR',
        vectorKnowledgeBaseConfiguration: {
          embeddingModelArn: `arn:aws:bedrock:${this.region}::foundation-model/${CONFIG.embeddingModelId}`,
        },
      },
      // [학습] storageConfiguration: 벡터를 어디에 저장할지 설정합니다.
      // S3_VECTORS 타입은 S3 Vectors 벡터 버킷을 사용합니다.
      // 기존 OpenSearch Serverless 대비 비용이 대폭 절감됩니다.
      storageConfiguration: {
        type: 'S3_VECTORS',
        s3VectorsConfiguration: {
          vectorBucketArn: props.vectorBucketArn,
          indexArn: props.indexArn,
        },
      },
    });

    // [학습] CfnDataSource 생성
    // 데이터 소스는 Knowledge Base에 문서를 공급하는 파이프라인입니다.
    // S3 버킷을 데이터 소스로 지정하면 해당 버킷의 문서를 자동으로 처리합니다.
    const dataSource = new bedrock.CfnDataSource(this, 'DataSource', {
      name: `${CONFIG.projectPrefix}-datasource`,
      knowledgeBaseId: knowledgeBase.attrKnowledgeBaseId,
      dataSourceConfiguration: {
        type: 'S3',
        s3Configuration: {
          bucketArn: props.documentBucketArn,
        },
      },
      // [학습] 청킹 설정
      // FIXED_SIZE: 고정 크기로 문서를 분할합니다.
      // maxTokens: 각 청크의 최대 토큰 수 (512)
      // overlapPercentage: 인접 청크 간 겹치는 비율 (20%)
      // 오버랩이 있으면 청크 경계에서 잘린 정보도 검색할 수 있습니다.
      vectorIngestionConfiguration: {
        chunkingConfiguration: {
          chunkingStrategy: CONFIG.chunkingStrategy,
          fixedSizeChunkingConfiguration: {
            maxTokens: CONFIG.chunkMaxTokens,
            overlapPercentage: CONFIG.overlapPercentage,
          },
        },
      },
    });

    this.knowledgeBaseId = knowledgeBase.attrKnowledgeBaseId;
    this.dataSourceId = dataSource.attrDataSourceId;

    // [학습] Custom Resource로 초기 데이터 동기화를 자동 실행합니다.
    // CDK 배포 완료 후 자동으로 S3 문서를 KB에 수집하여
    // 사용자가 수동으로 콘솔에서 Sync를 클릭하지 않아도 됩니다.
    const syncLambda = new lambda.Function(this, 'SyncKbLambda', {
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/sync-knowledge-base'),
      timeout: cdk.Duration.minutes(5),
      environment: {
        KNOWLEDGE_BASE_ID: knowledgeBase.attrKnowledgeBaseId,
        DATA_SOURCE_ID: dataSource.attrDataSourceId,
      },
    });

    // [학습] 동기화 Lambda에 bedrock-agent API 호출 권한 부여
    syncLambda.addToRolePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['bedrock:StartIngestionJob'],
      resources: [knowledgeBase.attrKnowledgeBaseArn],
    }));

    const syncProvider = new cr.Provider(this, 'SyncProvider', {
      onEventHandler: syncLambda,
    });

    new cdk.CustomResource(this, 'SyncKbTrigger', {
      serviceToken: syncProvider.serviceToken,
    });

    new cdk.CfnOutput(this, 'KnowledgeBaseId', {
      value: knowledgeBase.attrKnowledgeBaseId,
      description: 'Bedrock Knowledge Base ID',
    });

    new cdk.CfnOutput(this, 'DataSourceId', {
      value: dataSource.attrDataSourceId,
      description: 'Bedrock 데이터 소스 ID',
    });
  }
}

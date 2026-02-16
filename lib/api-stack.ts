/**
 * [학습] API Stack - Lambda + API Gateway 서버리스 백엔드
 *
 * 이 스택은 RAG 파이프라인의 API 레이어를 생성합니다:
 * - POST /query: 관리형 retrieve_and_generate (한 번의 호출로 검색+생성)
 * - POST /converse: 워크숍 패턴 retrieve + converse (검색과 생성을 분리)
 *
 * 서버리스 아키텍처의 장점:
 * - 요청이 없으면 비용이 발생하지 않음 (Free Tier 범위)
 * - 자동 확장: 트래픽 증가 시 Lambda가 자동으로 확장
 * - 관리 부담 없음: 서버 프로비저닝/패치 불필요
 *
 * 스택 의존성 체인에서의 위치:
 * S3Stack → S3VectorsStack → BedrockKbStack → [ApiStack]
 */
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import { CONFIG } from './config';

// [학습] Props 인터페이스: BedrockKbStack에서 생성한 Knowledge Base ID를 받습니다.
export interface ApiStackProps extends cdk.StackProps {
  /** BedrockKbStack에서 생성한 Knowledge Base ID */
  knowledgeBaseId: string;
}

export class ApiStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    // [학습] 모델 ARN 조합
    // CDK에서 모델 ID를 ARN 형식으로 변환합니다.
    // retrieve_and_generate API는 모델 ARN을 요구하고,
    // converse API는 모델 ID를 직접 사용합니다.
    const modelArn = `arn:aws:bedrock:${this.region}::foundation-model/${CONFIG.generationModelId}`;

    // [학습] RAG 쿼리 Lambda (관리형 방식)
    // retrieve_and_generate() API를 사용하여 한 번의 호출로 RAG를 수행합니다.
    const ragQueryLambda = new lambda.Function(this, 'RagQueryLambda', {
      functionName: `${CONFIG.projectPrefix}-rag-query`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/rag-query'),
      timeout: cdk.Duration.seconds(30),
      environment: {
        KNOWLEDGE_BASE_ID: props.knowledgeBaseId,
        MODEL_ARN: modelArn,
      },
    });

    // [학습] RAG Converse Lambda (워크숍 패턴)
    // retrieve() + converse() 를 분리 호출하여 프롬프트와 대화 이력을 직접 제어합니다.
    const ragConverseLambda = new lambda.Function(this, 'RagConverseLambda', {
      functionName: `${CONFIG.projectPrefix}-rag-converse`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'index.handler',
      code: lambda.Code.fromAsset('lambda/rag-converse'),
      timeout: cdk.Duration.seconds(30),
      environment: {
        KNOWLEDGE_BASE_ID: props.knowledgeBaseId,
        GENERATION_MODEL_ID: CONFIG.generationModelId,
      },
    });

    // [학습] Bedrock API 호출 IAM 권한
    // - RetrieveAndGenerate: 관리형 RAG API (rag-query Lambda용)
    // - Retrieve: 검색 전용 API (rag-converse Lambda용)
    // - InvokeModel: LLM 직접 호출 (rag-converse Lambda의 converse 호출용)
    const bedrockPolicy = new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'bedrock:RetrieveAndGenerate',
        'bedrock:Retrieve',
        'bedrock:InvokeModel',
      ],
      resources: ['*'],
    });

    ragQueryLambda.addToRolePolicy(bedrockPolicy);
    ragConverseLambda.addToRolePolicy(bedrockPolicy);

    // [학습] REST API Gateway 생성
    // API Gateway는 HTTP 요청을 Lambda 함수로 라우팅합니다.
    // defaultCorsPreflightOptions: 브라우저의 CORS 프리플라이트(OPTIONS) 요청을 자동 처리합니다.
    // CORS가 없으면 브라우저(Streamlit 등)에서 API를 호출할 수 없습니다.
    const api = new apigateway.RestApi(this, 'RagApi', {
      restApiName: `${CONFIG.projectPrefix}-api`,
      description: 'Bedrock RAG API - /query (관리형) + /converse (워크숍 패턴)',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type'],
      },
    });

    // [학습] API 경로 설정
    // POST /query → rag-query Lambda (관리형 retrieve_and_generate)
    // POST /converse → rag-converse Lambda (워크숍 패턴 retrieve + converse)
    const queryResource = api.root.addResource('query');
    queryResource.addMethod('POST', new apigateway.LambdaIntegration(ragQueryLambda));

    const converseResource = api.root.addResource('converse');
    converseResource.addMethod('POST', new apigateway.LambdaIntegration(ragConverseLambda));

    new cdk.CfnOutput(this, 'ApiEndpoint', {
      value: api.url,
      description: 'API Gateway 엔드포인트 URL',
    });
  }
}

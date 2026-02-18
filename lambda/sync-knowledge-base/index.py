"""
[학습] KB 동기화 Lambda - CDK Custom Resource 핸들러

이 Lambda는 CDK Custom Resource(cr.Provider)로 호출되어 Knowledge Base의 데이터 소스를 동기화합니다.
동기화(Ingestion)란:
1. S3 버킷의 문서를 읽어오고
2. 문서를 청크(조각)로 분할하고
3. 각 청크를 Titan Embeddings V2로 벡터화하고
4. 벡터를 S3 Vectors에 저장하는 과정입니다.

CDK 배포 시 자동으로 초기 동기화를 실행하여,
사용자가 수동으로 AWS 콘솔에서 Sync를 클릭하지 않아도 됩니다.

[학습] cr.Provider와 CloudFormation 응답 패턴:
CDK의 cr.Provider는 "framework Lambda"가 CloudFormation 이벤트를 수신하고,
이 사용자 Lambda를 동기적으로 호출(invoke)합니다.
CloudFormation 응답(ResponseURL에 PUT)은 framework Lambda가 처리하므로,
이 Lambda에서는 결과를 dict로 반환하기만 하면 됩니다.
직접 send_cfn_response()를 호출하면 이중 응답으로 오류가 발생합니다.

환경변수:
- KNOWLEDGE_BASE_ID: 동기화할 Knowledge Base ID
- DATA_SOURCE_ID: 동기화할 데이터 소스 ID
"""
import json
import os
import boto3

# [학습] bedrock-agent 클라이언트는 Knowledge Base 관리 API를 제공합니다.
# bedrock-agent-runtime(검색/생성)과는 달리 관리 작업(생성, 삭제, 동기화)에 사용됩니다.
bedrock_agent = boto3.client('bedrock-agent')

KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
DATA_SOURCE_ID = os.environ.get('DATA_SOURCE_ID', '')


def handler(event, context):
    """
    [학습] CDK Custom Resource(cr.Provider) 핸들러
    cr.Provider의 framework Lambda가 이 함수를 호출합니다.
    RequestType에 따라 다른 동작을 수행하고, 결과를 dict로 반환합니다.
    - Create/Update: 데이터 소스 동기화 실행
    - Delete: 아무 작업도 하지 않음 (Knowledge Base는 CDK가 삭제)

    [학습] 반환값 규칙:
    cr.Provider는 이 함수의 반환값에서 다음을 읽습니다:
    - PhysicalResourceId: 리소스 식별자 (Update/Delete 시 이전 값과 비교)
    - Data: CloudFormation 출력으로 사용할 키-값 쌍
    CloudFormation 응답은 framework Lambda가 자동으로 전송합니다.
    """
    print(f"Event: {json.dumps(event)}")

    request_type = event.get('RequestType', '')

    if request_type in ('Create', 'Update'):
        # [학습] start_ingestion_job() API 호출
        # 이 API는 비동기로 데이터 수집 작업을 시작합니다.
        # S3의 문서를 읽어 → 청킹 → 임베딩 → 벡터 저장 과정을 수행합니다.
        response = bedrock_agent.start_ingestion_job(
            knowledgeBaseId=KNOWLEDGE_BASE_ID,
            dataSourceId=DATA_SOURCE_ID,
        )
        ingestion_job_id = response.get('ingestionJob', {}).get('ingestionJobId', '')
        print(f"Started ingestion job: {ingestion_job_id}")

        # [학습] cr.Provider에 결과를 dict로 반환합니다.
        # framework Lambda가 이 값을 CloudFormation에 보고합니다.
        return {
            'PhysicalResourceId': f'sync-kb-{KNOWLEDGE_BASE_ID}',
            'Data': {
                'IngestionJobId': ingestion_job_id,
            },
        }
    else:
        # Delete 이벤트: 별도 정리 작업 불필요
        print(f"RequestType={request_type}, skipping.")
        return {
            'PhysicalResourceId': f'sync-kb-{KNOWLEDGE_BASE_ID}',
        }

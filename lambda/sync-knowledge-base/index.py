"""
[학습] KB 동기화 Lambda - CDK Custom Resource 핸들러

이 Lambda는 CDK Custom Resource로 호출되어 Knowledge Base의 데이터 소스를 동기화합니다.
동기화(Ingestion)란:
1. S3 버킷의 문서를 읽어오고
2. 문서를 청크(조각)로 분할하고
3. 각 청크를 Titan Embeddings V2로 벡터화하고
4. 벡터를 S3 Vectors에 저장하는 과정입니다.

CDK 배포 시 자동으로 초기 동기화를 실행하여,
사용자가 수동으로 AWS 콘솔에서 Sync를 클릭하지 않아도 됩니다.

환경변수:
- KNOWLEDGE_BASE_ID: 동기화할 Knowledge Base ID
- DATA_SOURCE_ID: 동기화할 데이터 소스 ID
"""
import json
import os
import boto3
import urllib3

# [학습] bedrock-agent 클라이언트는 Knowledge Base 관리 API를 제공합니다.
# bedrock-agent-runtime(검색/생성)과는 달리 관리 작업(생성, 삭제, 동기화)에 사용됩니다.
bedrock_agent = boto3.client('bedrock-agent')

KNOWLEDGE_BASE_ID = os.environ.get('KNOWLEDGE_BASE_ID', '')
DATA_SOURCE_ID = os.environ.get('DATA_SOURCE_ID', '')

http = urllib3.PoolManager()


def handler(event, context):
    """
    [학습] CDK Custom Resource 핸들러
    CloudFormation은 스택 생성/수정/삭제 시 이 Lambda를 호출합니다.
    RequestType에 따라 다른 동작을 수행합니다:
    - Create/Update: 데이터 소스 동기화 실행
    - Delete: 아무 작업도 하지 않음 (Knowledge Base는 CDK가 삭제)
    """
    print(f"Event: {json.dumps(event)}")

    request_type = event.get('RequestType', '')
    response_url = event.get('ResponseURL', '')

    try:
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

            send_cfn_response(event, context, 'SUCCESS', {
                'IngestionJobId': ingestion_job_id,
            })
        else:
            # Delete 이벤트: 별도 정리 작업 불필요
            print(f"RequestType={request_type}, skipping.")
            send_cfn_response(event, context, 'SUCCESS', {})

    except Exception as e:
        print(f"Error: {str(e)}")
        send_cfn_response(event, context, 'FAILED', {
            'Error': str(e),
        })


def send_cfn_response(event, context, status, data):
    """
    [학습] CloudFormation Custom Resource 응답 전송
    Custom Resource Lambda는 반드시 CloudFormation에 결과를 보고해야 합니다.
    응답을 보내지 않으면 CloudFormation 스택이 무한 대기 상태에 빠집니다.
    ResponseURL은 CloudFormation이 제공하는 사전 서명된 S3 URL입니다.
    """
    response_body = json.dumps({
        'Status': status,
        'Reason': f"See CloudWatch Log Stream: {context.log_stream_name}",
        'PhysicalResourceId': context.log_stream_name,
        'StackId': event.get('StackId', ''),
        'RequestId': event.get('RequestId', ''),
        'LogicalResourceId': event.get('LogicalResourceId', ''),
        'Data': data,
    })

    response_url = event.get('ResponseURL', '')
    if response_url:
        try:
            http.request(
                'PUT',
                response_url,
                body=response_body.encode('utf-8'),
                headers={'Content-Type': ''},
            )
            print("CFN response sent successfully")
        except Exception as e:
            print(f"Failed to send CFN response: {str(e)}")

export const CONFIG = {
  projectPrefix: 'bedrock-rag-handson',

  // S3 Vectors (OpenSearch Serverless 대체)
  vectorBucketName: 'bedrock-rag-handson-vectors',
  indexName: 'bedrock-rag-index',

  // Bedrock 임베딩 모델
  embeddingModelId: 'amazon.titan-embed-text-v2:0',
  vectorDimension: 1024,

  // Bedrock 생성 모델 (LLM)
  // 워크숍 rag_lib.py에서도 사용하는 모델
  // 대안: us.amazon.nova-micro-v1:0 (최저가), anthropic.claude-3-haiku-20240307-v1:0
  generationModelId: 'us.amazon.nova-lite-v1:0',

  // S3 문서 버킷
  documentBucketPrefix: 'rag-documents',

  // Knowledge Base 청킹 설정
  chunkingStrategy: 'FIXED_SIZE' as const,
  chunkMaxTokens: 512,
  overlapPercentage: 20,

  // LLM 추론 설정 (워크숍 converse API 기본값)
  inferenceConfig: {
    maxTokens: 2000,
    temperature: 0,
    topP: 0.9,
    stopSequences: [] as string[],
  },

  // 대화 이력 관리 (워크숍 chatbot_lib.py 패턴)
  maxConversationMessages: 20,
};

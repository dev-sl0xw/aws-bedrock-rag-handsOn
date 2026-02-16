# 작업 내역 요약 (Work Log)

> 최종 업데이트: 2026-02-17

## 개요

AWS Bedrock RAG Hands-On CDK 프로젝트의 아키텍처 재설계 및 학습 목적 개선 작업 내역입니다.

---

## Phase 1: 아키텍처 재설계

### 핵심 변경 사항

| 항목 | 변경 전 | 변경 후 | 이유 |
|------|---------|---------|------|
| 벡터 스토어 | OpenSearch Serverless (~$174/월) | S3 Vectors (사용량 기반, 거의 무료) | Free Tier 범위 내 실습 |
| LLM 모델 | Claude 3 Haiku ($0.25/$1.25 MTok) | Nova Lite ($0.06/$0.24 MTok) | 비용 50~60배 절감 |
| CDK 스택 수 | 5개 | 4개 | OpenSearch 관련 2개 스택 삭제 |
| CDK 버전 | ^2.170.0 | ^2.238.0 | `aws_s3vectors` 모듈 지원 |
| API 엔드포인트 | POST /query 1개 | POST /query + POST /converse 2개 | 워크숍 패턴 추가 |

### 스택 구조 변경

```
변경 전 (5 스택):
S3Stack → OpenSearchStack → OpenSearchIndexStack → BedrockKbStack → ApiStack

변경 후 (4 스택):
S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
```

### 삭제된 파일/구성요소
- `lib/opensearch-stack.ts` (보안정책, 네트워크정책, CfnCollection)
- `lib/opensearch-index-stack.ts` (Custom Resource Lambda)
- `lambda/create-index/` (opensearch-py 벡터 인덱스 생성)

### 신규 파일/구성요소
- `lib/s3-vectors-stack.ts` — S3 Vectors 벡터 버킷 + 인덱스
- `lambda/rag-converse/index.py` — Converse API 기반 RAG (워크숍 패턴)

---

## Phase 2: 수정된 파일 상세

### 1. `docs/implementation-plan.md` (전면 수정)
- 11개 섹션으로 구성된 전체 구현 계획서 재작성
- S3 Vectors 아키텍처, Nova Lite 모델, 4스택 체인 반영
- 워크숍 코드 참조 매핑 섹션(Section 6) 신규 추가
- Bedrock API 패턴 코드 예시 5가지 포함
- 에이전트 팀 태스크 14개로 재조정

### 2. `lib/config.ts` (수정)
- `collectionName` 삭제 → `vectorBucketName` 추가
- `generationModelId`: Claude 3 Haiku → `us.amazon.nova-lite-v1:0`
- `maxTokens` → `chunkMaxTokens` 이름 변경 (혼동 방지)
- `inferenceConfig` 블록 추가 (Converse API 추론 파라미터)
- `maxConversationMessages: 20` 추가 (워크숍 chatbot_lib.py 패턴)

### 3. `package.json` (수정)
- `aws-cdk`: `^2.170.0` → `^2.238.0`
- `aws-cdk-lib`: `^2.170.0` → `^2.238.0`

### 4. `CLAUDE.md` (생성 후 재작성)
- 학습 목표 5가지 명시
- 빌드/배포 명령어, 4스택 아키텍처, 중앙 설정 가이드
- `[학습]` 주석 규칙 (TypeScript/Python 예시 포함)
- summary.md 파일 규칙 (3개 폴더: lib/, lambda/, frontend/)

### 5. `.claude/agents/infra-cdk.md` (수정)
- OpenSearch 관련 모든 내용 제거, S3 Vectors 패턴으로 교체
- 담당 범위에 `lib/summary.md` 추가
- 학습 목적 코드 작성 규칙 섹션 추가

### 6. `.claude/agents/lambda-dev.md` (수정)
- `lambda/create-index/` 삭제, `lambda/rag-converse/` 신규 추가
- 워크숍 참조 코드 섹션 추가 (rag_lib.py, rag_chatbot_lib.py)
- `lambda/summary.md` 작성 지침 추가

### 7. `.claude/agents/frontend-doc.md` (수정)
- 스택 순서, 비용 경고, 엔드포인트 업데이트
- 워크숍 참조 코드 섹션 추가
- `frontend/summary.md` 작성 지침 추가

### 8. `.claude/agents/qa-verifier.md` (수정)
- 4개 스택 기준으로 검증 체크리스트 업데이트
- 7번 검증 항목 신규: 학습 자료 검증 (소스코드 주석 + summary.md 존재 여부)
- 완료 조건: 6개 → 7개 영역

---

## Phase 3: 학습 목적 개선

### `[학습]` 주석 규칙
모든 소스 파일에 한국어 학습 주석을 포함하도록 규칙 수립:
- 파일 상단: 전체 아키텍처에서의 역할 설명
- 핵심 로직: "무엇을 하는 코드인지" + "왜 이렇게 하는지"
- AWS API 호출: API 목적, 요청/응답 구조, 관련 AWS 서비스
- `[학습]` 접두사로 학습 목적 주석임을 표시

### summary.md 파일 규칙
각 실습 폴더에 이론과 개념을 정리하는 문서 생성:

| 경로 | 다루는 내용 |
|------|-----------|
| `lib/summary.md` | CDK 스택 개념, S3 Vectors, Bedrock KB, IAM, 서버리스 패턴 |
| `lambda/summary.md` | RAG 이론, Bedrock API 두 방식, 임베딩/벡터 검색, Lambda 패턴 |
| `frontend/summary.md` | Streamlit 실행 모델, 챗봇 UI, REST API 흐름, 인용 표시 |

---

## 미완료 작업 (구현 대기)

실제 코드 구현은 에이전트 팀 모드로 병렬 실행 예정입니다:

### infra-cdk 에이전트
- [ ] `lib/s3-stack.ts` — S3 문서 버킷
- [ ] `lib/s3-vectors-stack.ts` — S3 Vectors 벡터 버킷 + 인덱스
- [ ] `lib/bedrock-kb-stack.ts` — Bedrock KB + 데이터 소스
- [ ] `lib/api-stack.ts` — Lambda 2개 + API Gateway
- [ ] `bin/app.ts` — 4개 스택 연결 및 의존성
- [ ] `test/stacks.test.ts` — 스냅샷/어서션 테스트
- [ ] `lib/summary.md` — CDK 인프라 개념 학습 요약

### lambda-dev 에이전트
- [ ] `lambda/rag-query/index.py` — retrieve_and_generate 관리형 RAG
- [ ] `lambda/rag-converse/index.py` — retrieve + converse 워크숍 패턴
- [ ] `lambda/sync-knowledge-base/index.py` — KB 동기화 트리거
- [ ] `lambda/summary.md` — Lambda 및 Bedrock API 개념 학습 요약

### frontend-doc 에이전트
- [ ] `frontend/app.py` — Streamlit 챗봇 UI
- [ ] `frontend/requirements.txt` — 의존성
- [ ] `frontend/summary.md` — Streamlit 및 챗봇 UI 개념 학습 요약
- [ ] `sampledata/amazon-bedrock-faq.txt` — RAG 테스트용 샘플 문서
- [ ] `README.md` — 사용자 문서 (배포 가이드)

### qa-verifier 에이전트
- [ ] 7개 영역 전체 검증 (CDK 빌드, 코드 품질, 보안, 아키텍처, 문서, 프론트엔드, 학습 자료)

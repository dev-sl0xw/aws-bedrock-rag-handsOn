# Quality Assurance Verifier (Ralph-Loop)

모든 에이전트의 작업물을 검증하는 품질 검증 에이전트.
ralph-loop 패턴으로 반복 검증하여 모든 이슈가 해결될 때까지 순회합니다.

## 전용 MCP 서버
**awslabs-aws-iac-mcp-server** 를 활용하여:
- CloudFormation 템플릿 검증
- CDK 배포 트러블슈팅
- IaC 모범 사례 확인

## 검증 체크리스트

### 1. CDK 빌드 검증
- `npx tsc --noEmit` 타입 체크 통과
- `npx cdk synth` CloudFormation 템플릿 생성 성공
- 4개 스택 모두 정상 합성 (S3Stack, S3VectorsStack, BedrockKbStack, ApiStack)

### 2. 코드 품질 검증
- TypeScript: 타입 안전성, Props 인터페이스 정의
- Python Lambda: 에러 핸들링, 환경변수 사용, 구문 에러 없음 (`python3 -m py_compile`)
- lib/config.ts의 설정값이 모든 스택에서 올바르게 참조됨
- 하드코딩된 값 없음

### 3. 보안 검증
- S3: 퍼블릭 액세스 차단 (blockPublicAccess), SSL 강제
- IAM: 최소 권한 원칙 (와일드카드 리소스 ARN 사용 최소화)
- S3 Vectors: 적절한 IAM 권한 설정 (s3vectors:PutVectors/GetVectors/QueryVectors 등)
- API Gateway: CORS 설정 올바름

### 4. 아키텍처 검증
- 스택 간 의존성 체인 올바른지 확인
  - S3Stack → S3VectorsStack → BedrockKbStack → ApiStack
- CfnOutput으로 크로스 스택 참조 정확
- Lambda 환경변수에 올바른 리소스 ID/ARN 전달
- bin/app.ts에서 addDependency 올바르게 설정
- API Gateway에 /query + /converse 두 엔드포인트 존재

### 5. 문서 검증
- CLAUDE.md: 스택명, 명령어, 설정값이 실제 코드와 일치
- README.md: 배포 가이드 완성도, 사전 준비사항 정확
- 비용 안내 포함 여부 (S3 Vectors + Nova Lite)

### 6. 프론트엔드 검증
- frontend/app.py: Streamlit 구문 에러 없음
- API 엔드포인트 호출 로직 올바름 (/query + /converse 모두)
- requirements.txt 의존성 완전

### 7. 학습 자료 검증
- 모든 소스 파일에 학습용 한국어 주석이 포함되어 있는지 확인
- 각 실습 폴더(lib/, lambda/, frontend/)에 summary.md가 존재하는지 확인
- summary.md 내용이 해당 폴더의 코드와 관련된 이론/개념을 다루고 있는지 확인

## Ralph-Loop 실행 방식
```
/ralph-loop "프로젝트 전체 검증 체크리스트 실행" --max-iterations 5 --completion-promise "ALL_CHECKS_PASSED"
```

## 검증 실패 시 행동
1. 이슈를 구체적으로 식별
2. 직접 코드 수정
3. 수정 후 전체 검증 재실행
4. 모든 체크 통과 시에만 "ALL_CHECKS_PASSED" 출력

## 완료 조건
위 7개 영역 모두 통과 시 "ALL_CHECKS_PASSED" 출력

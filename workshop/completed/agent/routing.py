from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Callable
from util import llm_call, extract_xml

def route(input: str, routes: Dict[str, str]) -> str:
    """콘텐츠 분류를 사용하여 입력을 특수 프롬프트로 라우팅합니다."""
    print(f"\nAvailable routes: {list(routes.keys())}")
    selector_prompt = f"""
    입력을 분석하고 다음 옵션 중에서 가장 적합한 지원 팀을 선택하세요: {list(routes.keys())}
    먼저 추론을 설명한 다음 다음 XML 형식으로 선택 사항을 제공하세요:

    <reasoning>
    이 티켓이 특정 팀으로 라우팅되어야 하는 이유에 대한 간략한 설명.
    주요 용어, 사용자 의도, 긴급성 수준을 고려하세요.
    </reasoning>

    <selection>
    선택한 팀 이름
    </selection>

    Input: {input}""".strip()
    
    route_response = llm_call(selector_prompt)
    reasoning = extract_xml(route_response, 'reasoning')
    route_key = extract_xml(route_response, 'selection').strip().lower()
    
    print("Routing Analysis:")
    print(reasoning)
    print(f"\nSelected route: {route_key}")
    
    selected_prompt = routes[route_key]
    return llm_call(f"{selected_prompt}\nInput: {input}")


# 예시 3: 고객 지원 티켓 처리를 위한 라우팅 워크플로우
# 내용 분석을 기반으로 지원 티켓을 적절한 팀에 라우팅

support_routes = {
    "billing": """귀하는 결제 지원 전문가 입니다. 다음 지침을 따르세요:
    1. 항상 "결제 지원 답변:"으로 시작하세요
    2. 먼저 구체적인 결제 문제를 인지했음을 알리세요
    3. 요금이나 불일치 사항을 명확히 설명하세요
    4. 구체적인 다음 단계를 일정과 함께 나열하세요
    5. 관련이 있다면 결제 옵션으로 마무리하세요
    
    전문적이면서도 친근한 답변을 유지하세요.
    
    Input: """,
    
    "technical": """귀하는 기술 지원 엔지니어입니다. 다음 지침을 따르세요:
    1. 항상 "기술 지원 답변:"으로 시작하세요
    2. 문제 해결을 위한 정확한 단계를 나열하세요
    3. 관련이 있다면 시스템 요구사항을 포함하세요
    4. 일반적인 문제에 대한 대안을 제공하세요
    5. 필요한 경우 상위 단계 이관 경로로 마무리하세요
    
    명확한 번호가 매겨진 단계와 기술적 세부사항을 사용하세요.
    
    Input: """,
    
    "account": """귀하는 계정 보안 전문가입니다. 다음 지침을 따르세요:
    1. 항상 "계정 지원 답변:"으로 시작하세요
    2. 계정 보안과 인증을 우선시하세요
    3. 계정 복구/변경을 위한 명확한 단계를 제공하세요
    4. 보안 팁과 경고를 포함하세요
    5. 해결 시간에 대한 명확한 기대치를 설정하세요
    
    진지하고 보안 중심적인 어조를 유지하세요.
    
    Input: """,
    
    "product": """귀하는 제품 전문가입니다. 다음 지침을 따르세요:
    1. 항상 "제품 지원 답변:"으로 시작하세요
    2. 기능 교육과 모범 사례에 집중하세요
    3. 구체적인 사용 예시를 포함하세요
    4. 관련 문서 섹션에 대한 링크를 제공하세요
    5. 도움이 될 만한 관련 기능을 제안하세요
    
    교육적이고 격려하는 어조를 유지하세요.
    
    Input: """
}

# Test with different support tickets
tickets = [
    """제목: 계정 접속 불가
    메시지: 안녕하세요, 지난 1시간 동안 로그인을 시도했지만 계속 '잘못된 비밀번호' 오류가 발생합니다.
    제가 올바른 비밀번호를 사용하고 있다고 확신합니다. 접속 권한을 다시 받을 수 있도록 도와주시겠습니까? 오늘 업무 종료 전까지
    보고서를 제출해야 해서 긴급합니다.
    - John""",
    
    """제목: 카드에 예상치 못한 청구
    메시지: 안녕하세요, 방금 귀사에서 제 신용카드에 $49.99가 청구된 것을 확인했는데, 제가 알기로는
    $29.99 요금제를 사용 중이었습니다. 이 청구에 대해 설명해 주시고 실수라면 조정해 주실 수 있나요?
    감사합니다,
    Sarah""",
    
    """제목: 데이터 내보내기 방법?
    메시지: 제 프로젝트 데이터를 모두 엑셀로 내보내야 합니다. 문서를 살펴봤지만 일괄 내보내기 방법을
    찾을 수 없습니다. 이것이 가능한가요? 가능하다면, 단계별로 설명해 주시겠습니까?
    감사합니다,
    Mike"""
]

print("지원 티켓 처리 중...\n")
for i, ticket in enumerate(tickets, 1):
    print(f"\n티켓 {i}:")
    print("-" * 40)
    print(ticket)
    print("\n답변:")
    print("-" * 40)
    response = route(ticket, support_routes)
    print(response)

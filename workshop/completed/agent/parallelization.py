from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Callable
from util import llm_call, extract_xml

def parallel(prompt: str, inputs: List[str], n_workers: int = 3) -> List[str]:
    """동일한 프롬프트로 여러 입력을 동시에 처리할 수 있습니다."""
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(llm_call, f"{prompt}\nInput: {x}") for x in inputs]
        return [f.result() for f in futures]


# 예시 2: 병렬 처리 워크플로우를 활용한 stakeholder 영향도 분석
# 여러 Stakeholder 그룹에 대한 영향 분석을 동시에 처리

stakeholders = [
    """고객:
    - 가격에 민감함
    - 더 나은 기술 원함
    - 환경 관련 우려사항""",
    
    """직원:
    - 고용 안정성 우려
    - 새로운 기술 습득 필요
    - 명확한 방향성 요구""",
    
    """투자자:
    - 성장 기대
    - 비용 통제 원함
    - 리스크 우려사항""",
    
    """공급업체:
    - 생산능력 제약
    - 가격 압박
    - 기술 전환"""
]

impact_results = parallel(
    """이 stakeholder 그룹에 대한 시장 변화의 영향을 분석하세요.
    구체적인 영향과 권장 조치를 제공하세요.
    명확한 섹션과 우선순위로 형식을 갖추세요.""",
    stakeholders
)

for result in impact_results:
    print(result)
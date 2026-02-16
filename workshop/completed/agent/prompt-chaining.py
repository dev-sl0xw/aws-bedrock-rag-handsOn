from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Callable
from util import llm_call, extract_xml

def chain(input: str, prompts: List[str]) -> str:
    """여러 LLM 호출을 순차적으로 연결하여 단계 간에 결과를 전달합니다."""
    result = input
    for i, prompt in enumerate(prompts, 1):
        print(f"\nStep {i}:")
        result = llm_call(f"{prompt}\nInput: {result}")
        print(result)
    return result

# 예시 1: 구조화된 데이터 추출 및 형식화를 위한 체인 워크플로우
# 각 단계는 raw 텍스트를 점진적으로 형식화된 표로 변환합니다

data_processing_steps = [
    """텍스트에서 숫자값과 관련 지표만 추출하세요.
    각각을 새로운 줄에 'value: metric' 형식으로 작성하세요.
    예시 형식:
    92: 고객 만족도
    45%: 매출 성장률""",
    
    """가능한 모든 숫자값을 백분율로 변환하세요.
    백분율이나 포인트가 아닌 경우 소수로 변환하세요 (예: 92 points -> 92%).
    한 줄당 하나의 숫자를 유지하세요.
    예시 형식:
    92%: 고객 만족도
    45%: 매출 성장률""",
    
    """모든 줄을 숫자값 기준 내림차순으로 정렬하세요.
    각 줄의 'value: metric' 형식을 유지하세요.
    예시:
    92%: 고객 만족도
    87%: 직원 만족도""",
    
    """정렬된 데이터를 다음과 같은 마크다운 표 형식으로 작성하세요:
    | Metric | Value |
    |:--|--:|
    | 고객 만족도 | 92% |"""
]

report = """
3분기 실적 요약:
이번 분기 고객 만족도 점수는 92포인트로 상승했습니다.
매출은 전년 대비 45% 성장했습니다.
주요 시장에서의 시장 점유율은 현재 23%입니다.
고객 이탈률은 8%에서 5%로 감소했습니다.
신규 사용자 획득 비용은 사용자당 $43입니다.
제품 도입률은 78%로 증가했습니다.
직원 만족도는 87포인트입니다.
영업이익률은 34%로 개선되었습니다.
"""

print("\nInput text:")
print(report)
formatted_result = chain(report, data_processing_steps)
#print(formatted_result)

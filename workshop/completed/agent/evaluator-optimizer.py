from util import llm_call, extract_xml

def generate(prompt: str, task: str, context: str = "") -> tuple[str, str]:
    """Generate and improve a solution based on feedback."""
    full_prompt = f"{prompt}\n{context}\nTask: {task}" if context else f"{prompt}\nTask: {task}"
    response = llm_call(full_prompt)
    thoughts = extract_xml(response, "thoughts")
    result = extract_xml(response, "response")
    
    print("\n=== GENERATION START ===")
    print(f"Thoughts:\n{thoughts}\n")
    print(f"Generated:\n{result}")
    print("=== GENERATION END ===\n")
    
    return thoughts, result

def evaluate(prompt: str, content: str, task: str) -> tuple[str, str]:
    """Evaluate if a solution meets requirements."""
    full_prompt = f"{prompt}\nOriginal task: {task}\nContent to evaluate: {content}"
    response = llm_call(full_prompt)
    evaluation = extract_xml(response, "evaluation")
    feedback = extract_xml(response, "feedback")
    
    print("=== EVALUATION START ===")
    print(f"Status: {evaluation}")
    print(f"Feedback: {feedback}")
    print("=== EVALUATION END ===\n")
    
    return evaluation, feedback

def loop(task: str, evaluator_prompt: str, generator_prompt: str) -> tuple[str, list[dict]]:
    """Keep generating and evaluating until requirements are met."""
    memory = []
    chain_of_thought = []
    
    thoughts, result = generate(generator_prompt, task)
    memory.append(result)
    chain_of_thought.append({"thoughts": thoughts, "result": result})
    
    while True:
        evaluation, feedback = evaluate(evaluator_prompt, result, task)
        if evaluation == "PASS":
            return result, chain_of_thought
            
        context = "\n".join([
            "Previous attempts:",
            *[f"- {m}" for m in memory],
            f"\nFeedback: {feedback}"
        ])
        
        thoughts, result = generate(generator_prompt, task, context)
        memory.append(result)
        chain_of_thought.append({"thoughts": thoughts, "result": result})


evaluator_prompt = """
다음 코드 구현을 아래 기준으로 평가하세요:
1. 코드 정확성
2. 시간 복잡도
3. 스타일 및 모범 사례

평가만 진행하고 과제 해결을 시도하지 마세요.
모든 기준이 충족되고 더 이상 개선 제안이 없는 경우에만 "PASS"를 출력하세요.
평가를 다음 형식으로 간단히 출력하세요.

<evaluation>PASS, NEEDS_IMPROVEMENT, 또는 FAIL</evaluation>
<feedback>
개선이 필요한 사항과 그 이유.
</feedback>
"""

generator_prompt = """
<user input>에 기반하여 과제를 완료하는 것이 목표입니다. 이전 생성에 대한
피드백이 있다면 이를 반영하여 해결책을 개선해야 합니다.

답변을 다음 형식으로 간단히 출력하세요:

<thoughts>
[과제와 피드백에 대한 이해, 개선 계획]
</thoughts>

<response>
[코드 구현 내용]
</response>
"""

task = """
<user input>
스택을 구현합니다:
1. push(x)
2. pop()
3. getMin()
모든 연산은 O(1)이어야 합니다.
</user input>
"""

loop(task, evaluator_prompt, generator_prompt)

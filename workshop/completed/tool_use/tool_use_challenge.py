import boto3
import json

session = boto3.Session()
bedrock = session.client(service_name='bedrock-runtime')

tool_list = [
    {
        "toolSpec": {
            "name": "get_weather",
            "description": "Get current weather information for a specific city.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "The name of the city"
                        }
                    },
                    "required": ["city"]
                }
            }
        }
    }
]

def get_weather(city):
    result = f'오늘 {city} 날씨는 맑음!'
    return result

message_list = []

initial_message = {
    "role": "user",
    "content": [
        { "text": "서울의 현재 날씨는 어떤가요?" } 
    ],
}

message_list.append(initial_message)

response = bedrock.converse(
    modelId="anthropic.claude-3-sonnet-20240229-v1:0",
    system=[{"text":"반드시 매칭되는 도구만 사용해서 날씨를 확인해야 합니다. 도구 사용이 불가능할 경우, 추정하지 말고 모른다고 답하세요."}],
    messages=message_list,
    inferenceConfig={
        "maxTokens": 2000,
        "temperature": 0
    },
    toolConfig={
        "tools": tool_list
    },
)

response_message = response['output']['message']
message_list.append(response_message)


response_content_blocks = response_message['content']
follow_up_content_blocks = []
for content_block in response_content_blocks:
    if 'toolUse' in content_block:
        tool_use_block = content_block['toolUse']
        tool_use_name = tool_use_block['name']
            
        if tool_use_name == 'get_weather':
            tool_result = get_weather(tool_use_block['input']['city'])
            follow_up_content_blocks.append({
                "toolResult": {
                    "toolUseId": tool_use_block['toolUseId'],
                    "content": [
                        {
                            "json": {
                                "result": tool_result
                            }
                        }
                    ]
                }
            })

if len(follow_up_content_blocks) > 0:
    follow_up_message = {
        "role": "user",
        "content": follow_up_content_blocks,
    }
    
    message_list.append(follow_up_message)

    response = bedrock.converse(
        modelId="anthropic.claude-3-sonnet-20240229-v1:0",
        system=[{"text":"반드시 매칭되는 도구만 사용해서 날씨를 확인해야 합니다. 도구 사용이 불가능할 경우, 추정하지 말고 모른다고 답하세요."}],
        messages=message_list,
        inferenceConfig={
            "maxTokens": 2000,
            "temperature": 0
        },
        toolConfig={
            "tools": tool_list
        },
    )
    
    response_message = response['output']['message']
    
    message_list.append(response_message)
    print('============최종 응답===============')
    print(json.dumps(response_message, indent=4, ensure_ascii=False))

import requests
import json

GEMINI_API_KEY = "AIzaSyDT7dzyNXZdohIyXEhUhIu8VphSViwMMKQ"
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"

def get_mcp_json_from_gemini(user_input):
    prompt = (
        "你是一个MCP协议助手。"
        "用户输入一句自然语言，请你根据意图生成MCP协议的JSON。"
        "如果是打招呼（如早上好、hello等），生成tools/call，name为say_hi。"
        "如果是问时间（如现在几点、时间是什么），生成tools/call，name为get_time。"
        "只输出JSON，不要多余内容。"
        f"用户输入：{user_input}"
    )
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    response = requests.post(GEMINI_API_URL, headers=headers, data=json.dumps(data))
    result = response.json()
    # 解析 Gemini 返回的文本内容
    try:
        mcp_json = result["candidates"][0]["content"]["parts"][0]["text"]
        return mcp_json.strip()
    except Exception as e:
        print("Gemini API 返回异常：", result)
        raise e

def call_mcp_server(mcp_json):
    url = "http://localhost:8001/mcp"
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, data=mcp_json, headers=headers)
    return response.json()

if __name__ == "__main__":
    user_input = input("请输入：")
    mcp_json = get_mcp_json_from_gemini(user_input)
    print("Gemini 生成的MCP协议：", mcp_json)
    result = call_mcp_server(mcp_json)
    print("MCP Server返回：", result)
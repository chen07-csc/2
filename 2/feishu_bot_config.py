#!/usr/bin/env python3
"""
飞书机器人配置和工具
"""

import os
import json
import logging
from typing import Dict, Any
import httpx
import openai  # 新增

logger = logging.getLogger(__name__)

class FeishuBot:
    def __init__(self):
        # 飞书机器人配置
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self.verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
        self.encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")
        
        # MCP服务器配置
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080")
        print(f"MCP_SERVER_URL = {self.mcp_server_url}")
        
        # HTTP客户端
        self.client = httpx.AsyncClient(timeout=30.0)

        # OpenAI 配置
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = self.openai_api_key
    
    async def get_access_token(self) -> str:
        # ...保持不变...

    async def send_message(self, chat_id: str, content: str, msg_type: str = "text"):
        # ...保持不变...

    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> str:
        # ...保持不变...

    async def get_mcp_json_from_gemini(self, user_text: str) -> dict:
        """用 OpenAI 替代本地 Gemini，生成 MCP JSON"""
        prompt = (
            "你是一个MCP协议助手。"
            "用户输入一句自然语言，请你根据意图生成MCP协议的JSON。"
            "如果是打招呼（如早上好、hello等），生成tools/call，name为say_hi。"
            "如果是问时间（如现在几点、时间是什么），生成tools/call，name为get_time。"
            "只输出JSON，不要多余内容。"
            f"用户输入：{user_text}"
        )
        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=300,
            )
            reply = response.choices[0].message.content.strip()
            # 尝试解析返回的 JSON
            mcp_json = json.loads(reply)
            return mcp_json
        except Exception as e:
            logger.error(f"OpenAI MCP JSON 解析失败: {e}, 返回: {reply if 'reply' in locals() else '无内容'}")
            return None

    async def handle_message(self, event: Dict[str, Any]) -> str:
        # 这里保持不变，调用改后的 get_mcp_json_from_gemini 即可
        try:
            message = event.get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except:
                    content = {"text": content}
            text = content.get("text", "").strip()

            if text == "/hi" or text == "hi":
                return await self.call_mcp_tool("say_hi")
            elif text == "/time" or text == "时间":
                return await self.call_mcp_tool("get_time")
            elif text == "/help" or text == "帮助":
                return """可用命令：
/hi - 打招呼
/time - 获取当前时间
/help - 显示帮助信息"""
            else:
                mcp_json = await self.get_mcp_json_from_gemini(text)
                if mcp_json and mcp_json.get("method") == "tools/call":
                    tool_name = mcp_json["params"]["name"]
                    arguments = mcp_json["params"].get("arguments", {})
                    return await self.call_mcp_tool(tool_name, arguments)
                else:
                    return f"收到消息: {text}\n使用 /help 查看可用命令"

        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return f"处理消息时出错: {str(e)}"

# 创建全局机器人实例
feishu_bot = FeishuBot()

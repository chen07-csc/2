#!/usr/bin/env python3
"""
飞书机器人配置和工具
"""

import os
import json
import logging
from typing import Dict, Any, List
import httpx
import subprocess

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
    
    async def get_access_token(self) -> str:
        """获取飞书访问令牌"""
        try:
            url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
            data = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }
            
            response = await self.client.post(url, json=data)
            response.raise_for_status()
            
            result = response.json()
            return result.get("tenant_access_token")
            
        except Exception as e:
            logger.error(f"获取访问令牌失败: {e}")
            return None
    
    async def send_message(self, chat_id: str, content: str, msg_type: str = "text"):
        """发送消息到飞书群"""
        try:
            access_token = await self.get_access_token()
            if not access_token:
                return False
            
            url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            data = {
                "receive_id": chat_id,
                "msg_type": msg_type,
                "content": json.dumps({"text": content})
            }
            
            response = await self.client.post(url, json=data, headers=headers)
            response.raise_for_status()
            
            return True
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return False
    
    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> str:
        """调用MCP工具"""
        try:
            if arguments is None:
                arguments = {}
            
            mcp_request = {
                "jsonrpc": "2.0",
                "id": "feishu-bot",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }
            
            response = await self.client.post(
                f"{self.mcp_server_url}/mcp",
                json=mcp_request
            )
            response.raise_for_status()
            
            result = response.json()
            if "result" in result and "content" in result["result"]:
                content = result["result"]["content"]
                if content and len(content) > 0:
                    return content[0].get("text", "")
            
            return "工具调用成功，但无返回内容"
            
        except Exception as e:
            logger.error(f"调用MCP工具失败: {e}")
            return f"工具调用失败: {str(e)}"
    
    async def get_mcp_json_from_gemini(self, user_text: str) -> dict:
        prompt = (
            "你是一个MCP协议助手。"
            "用户输入一句自然语言，请你根据意图生成MCP协议的JSON。"
            "如果是打招呼（如早上好、hello等），生成tools/call，name为say_hi。"
            "如果是问时间（如现在几点、时间是什么），生成tools/call，name为get_time。"
            "只输出JSON，不要多余内容。"
            f"用户输入：{user_text}"
        )
        result = subprocess.run(["gemini", prompt], stdout=subprocess.PIPE, text=True)
        try:
            mcp_json = result.stdout.strip()
            return json.loads(mcp_json)
        except Exception as e:
            logger.error(f"Gemini CLI 解析失败: {e}, 输出: {result.stdout}")
            return None

    async def handle_message(self, event: Dict[str, Any]) -> str:
        """处理飞书消息"""
        try:
            # 提取消息内容
            message = event.get("message", {})
            content = message.get("content", "")
            
            # 解析消息内容
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except:
                    content = {"text": content}
            
            text = content.get("text", "").strip()
            
            # 处理命令
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
                # 智能理解自然语言
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
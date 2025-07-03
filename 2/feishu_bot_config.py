#!/usr/bin/env python3
"""
飞书机器人配置和工具
"""

import os
import json
import logging
from typing import Dict, Any
import httpx
import datetime
import openai

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class FeishuBot:
    def __init__(self):
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self.verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
        self.encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")

        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080")
        logger.info(f"MCP_SERVER_URL = {self.mcp_server_url}")

        self.client = httpx.AsyncClient(timeout=30.0)

        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        openai.api_key = self.openai_api_key

        self._access_token = None
        self._token_expire_time = None

    async def get_access_token(self) -> str:
        now = datetime.datetime.utcnow()
        if self._access_token and self._token_expire_time and now < self._token_expire_time:
            return self._access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal/"
        data = {"app_id": self.app_id, "app_secret": self.app_secret}
        try:
            resp = await self.client.post(url, json=data)
            resp.raise_for_status()
            j = resp.json()
            if j.get("code") == 0:
                self._access_token = j["app_access_token"]
                expire_seconds = j.get("expire", 7200)
                self._token_expire_time = now + datetime.timedelta(seconds=expire_seconds - 60)
                logger.info("飞书access_token获取成功")
                return self._access_token
            else:
                logger.error(f"飞书access_token获取失败: {j}")
                return ""
        except Exception as e:
            logger.error(f"获取飞书access_token异常: {e}")
            return ""

    async def send_message(self, chat_id: str, content: str, msg_type: str = "text"):
        token = await self.get_access_token()
        if not token:
            return {"error": "无法获取access_token"}

        url = "https://open.feishu.cn/open-apis/message/v4/send/"
        headers = {"Authorization": f"Bearer {token}"}

        # 注意：这里content必须是dict，不要json.dumps转字符串
        if msg_type == "text":
            body_content = {"text": content}
        else:
            body_content = content

        body = {
            "chat_id": chat_id,
            "msg_type": msg_type,
            "content": body_content
        }

        try:
            resp = await self.client.post(url, headers=headers, json=body)
            resp.raise_for_status()
            j = resp.json()
            if j.get("code") == 0:
                logger.info(f"消息发送成功，chat_id={chat_id}")
            else:
                logger.error(f"消息发送失败: {j}")
            return j
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return {"error": str(e)}

    async def call_mcp_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> str:
        url = f"{self.mcp_server_url}/mcp"  # 改成正确的接口路径
        payload = {
            "jsonrpc": "2.0",
            "id": "1",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            }
        }
        try:
            resp = await self.client.post(url, json=payload)
            resp.raise_for_status()
            j = resp.json()
            # 取result.content里所有text拼起来返回
            if "result" in j and "content" in j["result"]:
                content_list = j["result"]["content"]
                texts = [item.get("text", "") for item in content_list if item.get("type") == "text"]
                return "\n".join(texts)
            else:
                logger.error(f"MCP Server调用异常: {j}")
                return "调用失败"
        except Exception as e:
            logger.error(f"调用 MCP Server 工具异常: {e}")
            return f"调用 MCP Server 工具失败: {str(e)}"

    async def get_mcp_json_from_gemini(self, user_text: str) -> dict:
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
            mcp_json = json.loads(reply)
            logger.info(f"OpenAI MCP JSON解析成功: {mcp_json}")
            return mcp_json
        except Exception as e:
            logger.error(f"OpenAI MCP JSON解析失败: {e}, 返回: {reply if 'reply' in locals() else '无内容'}")
            return None

    async def handle_message(self, event: Dict[str, Any]) -> str:
        try:
            message = event.get("message", {})
            content = message.get("content", "")
            if isinstance(content, str):
                try:
                    content = json.loads(content)
                except:
                    content = {"text": content}
            text = content.get("text", "").strip()

            if text == "/hi" or text.lower() == "hi":
                return await self.call_mcp_tool("say_hi")
            elif text == "/time" or text == "时间":
                return await self.call_mcp_tool("get_time")
            elif text == "/help" or text == "帮助":
                return (
                    "可用命令：\n"
                    "/hi - 打招呼\n"
                    "/time - 获取当前时间\n"
                    "/help - 显示帮助信息"
                )
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

#!/usr/bin/env python3
"""
飞书机器人配置和工具 - 升级到 openai-python 1.0.0+ 接口
"""

import os
import json
import logging
from typing import Dict, Any
import httpx
import asyncio
import datetime

# 新版 openai 客户端导入
from openai import OpenAI

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class FeishuBot:
    def __init__(self):
        # 飞书机器人配置
        self.app_id = os.getenv("FEISHU_APP_ID", "")
        self.app_secret = os.getenv("FEISHU_APP_SECRET", "")
        self.verification_token = os.getenv("FEISHU_VERIFICATION_TOKEN", "")
        self.encrypt_key = os.getenv("FEISHU_ENCRYPT_KEY", "")

        # MCP服务器配置
        self.mcp_server_url = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8080")
        logger.info(f"MCP_SERVER_URL = {self.mcp_server_url}")

        # HTTP客户端
        self.client = httpx.AsyncClient(timeout=30.0)

        # OpenAI 客户端实例
        self.openai_client = OpenAI()

        self._access_token = None
        self._token_expire_time = None  # token过期时间戳

    async def get_access_token(self) -> str:
        """获取飞书access_token，简单缓存，过期后刷新"""
        now = datetime.datetime.utcnow()
        if self._access_token and self._token_expire_time and now < self._token_expire_time:
            return self._access_token

        url = "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal/"
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
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
        """发送消息到飞书群聊或单聊"""
        token = await self.get_access_token()
        if not token:
            return {"error": "无法获取access_token"}

        url = "https://open.feishu.cn/open-apis/message/v4/send/"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        body = {
            "chat_id": chat_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": content}) if msg_type == "text" else content
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
        """调用 MCP Server 工具接口（示例用httpx请求）"""
        url = f"{self.mcp_server_url}/mcp"
        payload = {
            "jsonrpc": "2.0",
            "id": "feishu_call_001",
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
            if "result" in j and "content" in j["result"]:
                # 拼接content中的文本
                content_text = "".join([item.get("text", "") for item in j["result"]["content"] if item.get("type") == "text"])
                return content_text
            return "无结果返回"
        except Exception as e:
            logger.error(f"调用 MCP Server 工具异常: {e}")
            return f"调用 MCP Server 工具失败: {str(e)}"

    async def get_mcp_json_from_gemini(self, user_text: str) -> dict:
        """用 OpenAI GPT 生成 MCP JSON"""
        prompt = (
            "你是一个MCP协议助手。"
            "用户输入一句自然语言，请你根据意图生成MCP协议的JSON。"
            "如果是打招呼（如早上好、hello等），生成tools/call，name为say_hi。"
            "如果是问时间（如现在几点、时间是什么），生成tools/call，name为get_time。"
            "只输出JSON，不要多余内容。"
            f"用户输入：{user_text}"
        )
        try:
            response = await self.openai_client.chat.completions.acreate(
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
        """处理飞书消息事件，返回回复内容"""
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

# 测试代码（可删除）
if __name__ == "__main__":
    import asyncio

    async def test():
        print("测试发送消息:")
        resp = await feishu_bot.send_message("oc_1234567890abcdef", "Hello from FeishuBot!")
        print(resp)

        print("测试调用 MCP say_hi:")
        ret = await feishu_bot.call_mcp_tool("say_hi")
        print("say_hi 返回:", ret)

        print("测试用 OpenAI 生成 MCP JSON:")
        mcp = await feishu_bot.get_mcp_json_from_gemini("你好")
        print("生成的 MCP JSON:", mcp)

        print("测试处理消息:")
        reply = await feishu_bot.handle_message({
            "message": {
                "content": json.dumps({"text": "/hi"})
            }
        })
        print("handle_message 返回:", reply)

    asyncio.run(test())

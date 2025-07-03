#!/usr/bin/env python3
"""
HTTP MCP服务器 - 支持流式传输和飞书集成
"""

import asyncio
import json
import logging
from typing import Any, Dict
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# 导入飞书机器人
from feishu_bot_config import feishu_bot

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="HTTP MCP Server", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Dict[str, Any] = {}

class MCPServer:
    def __init__(self):
        self.name = "http-mcp-server"
        self.version = "1.0.0"
        self.tools = [
            {
                "name": "say_hi",
                "description": "返回一个简单的问候语",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_time",
                "description": "获取当前时间",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    async def handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理初始化请求"""
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "serverInfo": {
                "name": self.name,
                "version": self.version
            }
        }
    
    async def handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具列表请求"""
        return {
            "tools": self.tools
        }
    
    async def handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """处理工具调用请求"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name == "say_hi":
            return {
                "content": [
                    {
                        "type": "text",
                        "text": "hi"
                    }
                ]
            }
        elif tool_name == "get_time":
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"当前时间: {current_time}"
                    }
                ]
            }
        else:
            raise Exception(f"未知工具: {tool_name}")
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """处理MCP请求"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        try:
            if method == "initialize":
                result = await self.handle_initialize(params)
            elif method == "tools/list":
                result = await self.handle_tools_list(params)
            elif method == "tools/call":
                result = await self.handle_tools_call(params)
            else:
                raise Exception(f"未知方法: {method}")
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }

mcp_server = MCPServer()

@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest):
    try:
        response = await mcp_server.handle_request(request.dict())
        return JSONResponse(content=response)
    except Exception as e:
        logger.error(f"MCP请求处理错误: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/stream")
async def handle_mcp_stream_request(request: MCPRequest):
    """处理流式MCP请求"""
    data = request.dict()  # 先转dict方便访问
    async def generate_stream():
        try:
            response = await mcp_server.handle_request(data)
            if data.get("method") == "tools/call":
                tool_name = data.get("params", {}).get("name")
                if tool_name == "say_hi":
                    # 模拟分块发送 "hi"
                    yield f"data: {json.dumps({'type': 'partial', 'content': 'h'})}\n\n"
                    await asyncio.sleep(0.1)
                    yield f"data: {json.dumps({'type': 'partial', 'content': 'i'})}\n\n"
                    await asyncio.sleep(0.1)
                    yield f"data: {json.dumps({'type': 'complete', 'response': response})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'complete', 'response': response})}\n\n"
            else:
                yield f"data: {json.dumps({'type': 'complete', 'response': response})}\n\n"
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": data.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }
            yield f"data: {json.dumps({'type': 'error', 'response': error_response})}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.post("/feishu/webhook")
async def feishu_webhook(request: Request):
    data = await request.json()
    logger.info(f"收到飞书请求：{data}")
    # 处理 challenge 验证
    if "challenge" in data:
        return {"challenge": data["challenge"]}
    if "event" in data:
        event = data["event"]
        chat_id = event.get("message", {}).get("chat_id")
        reply = await feishu_bot.handle_message(event)
        if chat_id and reply:
            await feishu_bot.send_message(chat_id, reply)
    return {"msg": "ok"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/tools")
async def list_tools():
    return {"tools": mcp_server.tools}

if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8001))
    uvicorn.run(
        "http_mcp_server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info"
    )

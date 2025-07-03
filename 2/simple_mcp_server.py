#!/usr/bin/env python3
"""
简单的MCP服务器演示
提供返回"hi"的工具
"""

import asyncio
import json
import sys
from typing import Any, Dict, List

class SimpleMCPServer:
    def __init__(self):
        self.name = "simple-mcp-server"
        self.version = "1.0.0"
        
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
            "tools": [
                {
                    "name": "say_hi",
                    "description": "返回一个简单的问候语",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ]
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
    
    async def run(self):
        """运行MCP服务器"""
        print("MCP服务器已启动，等待连接...", file=sys.stderr)
        
        while True:
            try:
                # 从stdin读取请求
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                if not line:
                    break
                
                request = json.loads(line.strip())
                response = await self.handle_request(request)
                
                # 输出响应到stdout
                print(json.dumps(response), flush=True)
                
            except json.JSONDecodeError as e:
                print(f"JSON解析错误: {e}", file=sys.stderr)
            except Exception as e:
                print(f"处理请求时出错: {e}", file=sys.stderr)

async def main():
    """主函数"""
    server = SimpleMCPServer()
    await server.run()

if __name__ == "__main__":
    asyncio.run(main()) 
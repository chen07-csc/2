# MCP服务器演示项目

这是一个完整的MCP（Model Context Protocol）服务器演示项目，支持HTTP流式传输和飞书机器人集成。

## 架构

```
飞书机器人 → Webhook → Railway → MCP服务器
```

## 功能特性

- ✅ HTTP MCP服务器
- ✅ 流式传输支持 (Server-Sent Events)
- ✅ 飞书机器人集成
- ✅ Railway部署支持
- ✅ 工具：say_hi, get_time

## 安装和运行

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置环境变量
复制 `env.example` 为 `.env` 并填写配置：
```bash
cp env.example .env
```

### 3. 本地运行
```bash
python http_mcp_server.py
```

### 4. Railway部署
```bash
# 安装Railway CLI
npm install -g @railway/cli

# 登录Railway
railway login

# 部署项目
railway up
```

## API端点

- `POST /mcp` - 标准MCP请求
- `POST /mcp/stream` - 流式MCP请求
- `POST /feishu/webhook` - 飞书webhook
- `GET /health` - 健康检查
- `GET /tools` - 列出可用工具

## 飞书机器人配置

1. 在飞书开放平台创建应用
2. 配置webhook URL: `https://your-railway-app.railway.app/feishu/webhook`
3. 设置环境变量

## 可用命令

在飞书群中使用以下命令：
- `/hi` - 打招呼
- `/time` - 获取当前时间
- `/help` - 显示帮助

## 项目结构
```
├── http_mcp_server.py    # HTTP MCP服务器
├── feishu_bot_config.py  # 飞书机器人配置
├── requirements.txt      # Python依赖
├── railway.json         # Railway部署配置
├── env.example          # 环境变量示例
└── README.md            # 说明文档
```

## 下一步
- 2. 集成谷歌地图MCP
- 3. 添加更多MCP工具 
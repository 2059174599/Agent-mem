#!/usr/bin/env python3
"""
启动Agent Memo服务器
"""

import uvicorn
from app import app

if __name__ == "__main__":
    print("🚀 启动Agent Memo服务器...")
    print("📝 鉴权Token: yixinagentmemory")
    print("🌐 服务地址: http://localhost:8000")
    print("📚 API文档: http://localhost:8000/docs")
    print("🔧 健康检查: http://localhost:8000/health")
    print("\n按 Ctrl+C 停止服务")
    print("-" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )

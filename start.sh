#!/bin/bash
# FastAPI版本启动脚本

echo "🚀 启动FastAPI记忆服务..."

# 检查Python版本
python_version=$(python3 --version 2>&1 | grep -o '[0-9]\+\.[0-9]\+')
echo "Python版本: $python_version"

# 检查依赖
echo "📦 检查依赖..."
if ! python3 -c "import fastapi, uvicorn, aiohttp" 2>/dev/null; then
    echo "❌ 缺少依赖，正在安装..."
    pip install -r requirements.txt
fi

# 设置环境变量
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
export LOG_LEVEL=${LOG_LEVEL:-INFO}
export CACHE_TTL=${CACHE_TTL:-3600}
export MAX_CONCURRENT_REQUESTS=${MAX_CONCURRENT_REQUESTS:-100}

# 创建日志目录
mkdir -p logs

echo "🔧 配置信息:"
echo "  日志级别: $LOG_LEVEL"
echo "  缓存TTL: $CACHE_TTL秒"
echo "  最大并发: $MAX_CONCURRENT_REQUESTS"
echo "  端口: ${APP_PORT:-8000}"

# 启动服务
echo "🌟 启动FastAPI服务..."
python3 app.py

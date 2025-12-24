#!/bin/bash

set -e

# 设置环境变量
export PYTHONPATH=/app
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8
export PYTHONIOENCODING=utf-8

# 切换到应用目录
cd /app

# 创建日志目录
mkdir -p logs

# 信号处理函数
cleanup() {
    echo ""
    echo "🛑 正在停止所有服务..."
    
    # 停止 ARQ Worker
    if [[ -n "$ARQ_PID" ]] && kill -0 $ARQ_PID 2>/dev/null; then
        echo "   停止 ARQ Worker (PID: $ARQ_PID)..."
        kill -TERM $ARQ_PID 2>/dev/null || true
        wait $ARQ_PID 2>/dev/null || true
    fi
    
    # 停止 Gunicorn
    if [[ -n "$GUNICORN_PID" ]] && kill -0 $GUNICORN_PID 2>/dev/null; then
        echo "   停止 Gunicorn (PID: $GUNICORN_PID)..."
        kill -TERM $GUNICORN_PID 2>/dev/null || true
        wait $GUNICORN_PID 2>/dev/null || true
    fi
    
    echo "✅ 所有服务已停止"
    exit 0
}

# 注册信号处理
trap cleanup SIGTERM SIGINT SIGQUIT

# 根据环境变量选择启动模式
if [[ "${MODE}" == "arq" ]]; then
    # 仅启动 ARQ Worker
    echo "🔧 启动 ARQ Worker 模式..."
    echo "   - Redis: ${REDIS_HOST:-redis}:${REDIS_PORT:-6379}"
    echo "   - 持久化: ${PERSISTENCE_ENABLED:-true}"
    echo "   - 持久化后端: ${PERSISTENCE_BACKEND:-file}"
    echo "   - 持久化间隔: ${PERSISTENCE_INTERVAL:-300}秒"
    exec arq services.arq_tasks.WorkerSettings

elif [[ "${MODE}" == "worker" ]]; then
    # Celery Worker 模式
    echo "启动Worker模式..."
    exec python -m celery worker -A app.celery --loglevel=info

elif [[ "${MODE}" == "beat" ]]; then
    # Celery Beat 模式
    echo "启动Beat模式..."
    exec python -m celery beat -A app.celery --loglevel=info

elif [[ "${MODE}" == "all" ]]; then
    # 同时启动 FastAPI + ARQ Worker（单容器模式）
    echo "🚀 启动完整服务模式 (FastAPI + ARQ Worker)..."
    echo ""
    
    # 启动 ARQ Worker（后台）
    if [[ "${PERSISTENCE_ENABLED}" == "true" ]]; then
        echo "🔧 启动 ARQ Worker (后台)..."
        echo "   - Redis: ${REDIS_HOST:-redis}:${REDIS_PORT:-6379}"
        echo "   - 持久化后端: ${PERSISTENCE_BACKEND:-file}"
        echo "   - 持久化间隔: ${PERSISTENCE_INTERVAL:-300}秒"
        
        arq services.arq_tasks.WorkerSettings > logs/arq_worker.log 2>&1 &
        ARQ_PID=$!
        echo "   ✅ ARQ Worker 已启动 (PID: $ARQ_PID)"
        
        # 等待一下确保启动成功
        sleep 2
        
        if ! kill -0 $ARQ_PID 2>/dev/null; then
            echo "   ❌ ARQ Worker 启动失败，查看日志: tail -f logs/arq_worker.log"
            exit 1
        fi
    else
        echo "ℹ️  持久化功能已禁用，跳过 ARQ Worker"
    fi
    
    echo ""
    echo "🌐 启动 Gunicorn 服务..."
    echo "   - 端口: ${APP_PORT:-8000}"
    echo "   - Workers: ${SERVER_WORKER_AMOUNT:-4}"
    echo "   - Worker类型: ${SERVER_WORKER_CLASS:-uvicorn.workers.UvicornWorker}"
    echo ""
    
    # 启动 Gunicorn（前台）
    gunicorn app:app \
        -w ${SERVER_WORKER_AMOUNT:-4} \
        -k ${SERVER_WORKER_CLASS:-uvicorn.workers.UvicornWorker} \
        --bind 0.0.0.0:${APP_PORT:-8000} \
        --timeout ${GUNICORN_TIMEOUT:-200} \
        --keep-alive 2 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --preload \
        --access-logfile - \
        --error-logfile - \
        --log-level ${LOG_LEVEL:-info} &
    
    GUNICORN_PID=$!
    echo "✅ Gunicorn 已启动 (PID: $GUNICORN_PID)"
    
    # 等待进程
    wait $GUNICORN_PID

else
    # 默认：仅启动 FastAPI (Web 模式)
    echo "🌐 启动 Web 服务模式..."
    echo "   - 端口: ${APP_PORT:-8000}"
    echo "   - Workers: ${SERVER_WORKER_AMOUNT:-4}"
    echo "   - Worker类型: ${SERVER_WORKER_CLASS:-uvicorn.workers.UvicornWorker}"
    
    # 如果启用持久化，提示需要启动 ARQ Worker
    if [[ "${PERSISTENCE_ENABLED}" == "true" ]]; then
        echo ""
        echo "   ⚠️  持久化功能已启用，请确保 ARQ Worker 已启动:"
        echo "      方式1: MODE=arq ./start.sh"
        echo "      方式2: MODE=all ./start.sh (单容器同时启动)"
        echo "      方式3: docker-compose up -d arq-worker"
    fi
    
    # 启动Gunicorn服务
    exec gunicorn app:app \
        -w ${SERVER_WORKER_AMOUNT:-4} \
        -k ${SERVER_WORKER_CLASS:-uvicorn.workers.UvicornWorker} \
        --bind 0.0.0.0:${APP_PORT:-8000} \
        --timeout ${GUNICORN_TIMEOUT:-200} \
        --keep-alive 2 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --preload \
        --access-logfile - \
        --error-logfile - \
        --log-level ${LOG_LEVEL:-info}
fi
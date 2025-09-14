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

# 根据环境变量选择启动模式
if [[ "${MODE}" == "worker" ]]; then
    echo "启动Worker模式..."
    exec python -m celery worker -A app.celery --loglevel=info
elif [[ "${MODE}" == "beat" ]]; then
    echo "启动Beat模式..."
    exec python -m celery beat -A app.celery --loglevel=info
else
    echo "启动Web服务模式..."
    # 启动Gunicorn服务
    exec gunicorn app:app \
        -w ${SERVER_WORKER_AMOUNT:-4} \
        -k ${SERVER_WORKER_CLASS:-uvicorn.workers.UvicornWorker} \
        --bind 0.0.0.0:8000 \
        --timeout ${GUNICORN_TIMEOUT:-200} \
        --keep-alive 2 \
        --max-requests 1000 \
        --max-requests-jitter 100 \
        --preload \
        --access-logfile - \
        --error-logfile - \
        --log-level ${LOG_LEVEL:-info}
fi
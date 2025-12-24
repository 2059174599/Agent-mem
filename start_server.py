#!/usr/bin/env python3
"""
本地开发启动脚本
同时启动 FastAPI 和 ARQ Worker（如果启用持久化）
"""

import os
import sys
import subprocess
import signal
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 全局变量存储子进程
arq_process = None
uvicorn_process = None


def signal_handler(sig, frame):
    """处理 Ctrl+C 信号"""
    print("\n\n🛑 正在停止服务...")
    
    # 停止 ARQ Worker
    if arq_process:
        print("   停止 ARQ Worker...")
        arq_process.terminate()
        try:
            arq_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            arq_process.kill()
    
    # 停止 FastAPI
    if uvicorn_process:
        print("   停止 FastAPI...")
        uvicorn_process.terminate()
        try:
            uvicorn_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            uvicorn_process.kill()
    
    print("✅ 所有服务已停止")
    sys.exit(0)


def start_arq_worker():
    """启动 ARQ Worker"""
    global arq_process
    
    print("🔧 启动 ARQ Worker...")
    print(f"   - Redis: {os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}")
    print(f"   - 持久化后端: {os.getenv('PERSISTENCE_BACKEND', 'file')}")
    print(f"   - 持久化间隔: {os.getenv('PERSISTENCE_INTERVAL', '300')}秒")
    
    # 检查 arq 是否安装
    try:
        import arq
    except ImportError:
        print("   ❌ arq 未安装")
        print("   请运行: pip install arq")
        return False
    
    try:
        arq_process = subprocess.Popen(
            ["arq", "services.arq_tasks.WorkerSettings"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        # 等待一下确保启动
        time.sleep(2)
        
        if arq_process.poll() is None:
            print("   ✅ ARQ Worker 启动成功")
            return True
        else:
            # 读取完整错误信息
            try:
                stdout_output = arq_process.stdout.read() if arq_process.stdout else ""
                stderr_output = arq_process.stderr.read() if arq_process.stderr else ""
                error_msg = stderr_output or stdout_output
            except:
                error_msg = "无法读取错误信息"
            
            print("   ❌ ARQ Worker 启动失败")
            if error_msg:
                # 只显示最后几行关键错误
                lines = error_msg.strip().split('\n')
                print(f"   错误信息: {lines[-1] if lines else '未知错误'}")
            return False
    except FileNotFoundError:
        print("   ❌ arq 命令未找到")
        print("   请运行: pip install arq")
        return False
    except Exception as e:
        print(f"   ❌ ARQ Worker 启动失败: {e}")
        return False


def start_fastapi():
    """启动 FastAPI"""
    global uvicorn_process
    
    port = int(os.getenv('APP_PORT', '8000'))
    
    print(f"\n🌐 启动 FastAPI 服务...")
    print(f"   - 端口: {port}")
    print(f"   - 热重载: 已启用")
    print(f"   - 日志级别: info")
    print(f"\n📚 服务地址:")
    print(f"   - API文档: http://localhost:{port}/docs")
    print(f"   - 健康检查: http://localhost:{port}/health")
    print(f"   - 场景列表: http://localhost:{port}/scenarios")
    print(f"\n📝 默认鉴权Token: yixinagentmemory")
    print(f"\n按 Ctrl+C 停止所有服务")
    print("-" * 60)
    
    try:
        # 使用字符串形式传入应用，支持热重载
        import uvicorn
        
        uvicorn.run(
            "app:app",  # 使用字符串形式而不是导入对象
            host="0.0.0.0",
            port=port,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        pass


def main():
    """主函数"""
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print("🚀 Agent Memo 本地开发环境启动")
    print("=" * 60)
    print()
    
    # 检查是否启用持久化
    persistence_enabled = os.getenv('PERSISTENCE_ENABLED', 'true').lower() == 'true'
    
    if persistence_enabled:
        print("✅ 持久化功能已启用")
        
        # 启动 ARQ Worker
        arq_started = start_arq_worker()
        
        if not arq_started:
            print("\n⚠️  ARQ Worker 未启动，持久化功能将不可用")
            print("   如需使用持久化功能，请:")
            print("   1. 安装依赖: pip install -r requirements.txt")
            print("   2. 确保 Redis 运行中: redis-cli ping")
            print("   3. 检查环境变量配置: cat .env")
            
            # 自动继续，不需要用户确认
            print("\n   继续启动 FastAPI（持久化功能将被禁用）...")
            time.sleep(1)
    else:
        print("ℹ️  持久化功能已禁用")
    
    print()
    
    # 启动 FastAPI
    try:
        start_fastapi()
    except Exception as e:
        print(f"\n❌ FastAPI 启动失败: {e}")
        signal_handler(None, None)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
异步日志服务 - 支持多进程和异步的日志系统
"""
import asyncio
import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor
import aiofiles
from config import Config

class AsyncLogHandler(logging.Handler):
    """异步日志处理器"""
    
    def __init__(self, log_file: str, max_bytes: int = 10 * 1024 * 1024, backup_count: int = 5):
        super().__init__()
        self.log_file = log_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="async_log")
        
        # 确保日志目录存在
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        
        # 创建轮转文件处理器
        self.file_handler = logging.handlers.RotatingFileHandler(
            log_file, 
            maxBytes=max_bytes, 
            backupCount=backup_count,
            encoding='utf-8'
        )
        
        # 设置格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(thread)d - %(message)s'
        )
        self.file_handler.setFormatter(formatter)
    
    def emit(self, record):
        """异步发送日志记录"""
        try:
            # 直接同步处理，避免异步问题
            self._sync_emit(record)
        except Exception:
            self.handleError(record)
    
    async def _async_emit(self, record):
        """异步处理日志记录"""
        try:
            # 在线程池中执行文件操作
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(self.executor, self._sync_emit, record)
        except Exception as e:
            print(f"异步日志处理失败: {e}", file=sys.stderr)
    
    def _sync_emit(self, record):
        """同步处理日志记录"""
        try:
            self.file_handler.emit(record)
        except Exception:
            pass
    
    def close(self):
        """关闭处理器"""
        try:
            self.file_handler.close()
            self.executor.shutdown(wait=True)
        except Exception:
            pass

class AsyncLoggingService:
    """异步日志服务"""
    
    def __init__(self):
        self.loggers: Dict[str, logging.Logger] = {}
        self.executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="async_log")
        self._setup_root_logger()
    
    def _setup_root_logger(self):
        """设置根日志器"""
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    def get_logger(self, name: str, log_file: Optional[str] = None) -> logging.Logger:
        """获取日志器"""
        if name in self.loggers:
            return self.loggers[name]
        
        logger = logging.getLogger(name)
        
        # 正确设置日志级别
        log_level_str = Config.get_log_level().upper()
        if log_level_str == "DEBUG":
            logger.setLevel(logging.DEBUG)
        elif log_level_str == "INFO":
            logger.setLevel(logging.INFO)
        elif log_level_str == "WARNING":
            logger.setLevel(logging.WARNING)
        elif log_level_str == "ERROR":
            logger.setLevel(logging.ERROR)
        else:
            logger.setLevel(logging.INFO)  # 默认INFO级别
        
        # 添加异步文件处理器
        if log_file:
            async_handler = AsyncLogHandler(log_file)
            logger.addHandler(async_handler)
        
        # 避免重复日志
        logger.propagate = False
        
        self.loggers[name] = logger
        return logger
    
    async def log_async(self, logger_name: str, level: str, message: str, 
                       extra: Optional[Dict[str, Any]] = None, log_file: Optional[str] = None):
        """异步记录日志"""
        try:
            logger = self.get_logger(logger_name, log_file)
            
            # 构建日志记录
            log_data = {
                "timestamp": datetime.now().isoformat(),
                "level": level.upper(),
                "logger": logger_name,
                "message": message,
                "process_id": os.getpid(),
                "thread_id": asyncio.current_task().get_name() if asyncio.current_task() else "main"
            }
            
            if extra:
                log_data.update(extra)
            
            # 在线程池中执行日志记录
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor, 
                self._sync_log, 
                logger, 
                level, 
                message, 
                log_data
            )
            
        except Exception as e:
            print(f"异步日志记录失败: {e}", file=sys.stderr)
    
    def _sync_log(self, logger: logging.Logger, level: str, message: str, log_data: Dict[str, Any]):
        """同步记录日志"""
        try:
            log_method = getattr(logger, level.lower(), logger.info)
            # 直接记录消息，不传递extra参数
            log_method(message)
        except Exception as e:
            print(f"同步日志记录失败: {e}", file=sys.stderr)
    
    async def log_performance(self, operation: str, duration: float, 
                            success: bool = True, extra: Optional[Dict[str, Any]] = None):
        """记录性能日志"""
        perf_data = {
            "operation": operation,
            "duration_ms": round(duration * 1000, 2),
            "success": success,
            "timestamp": datetime.now().isoformat()
        }
        
        if extra:
            perf_data.update(extra)
        
        await self.log_async(
            "performance", 
            "info", 
            f"性能监控 - {operation}: {duration:.3f}s",
            perf_data,
            "logs/performance.log"
        )
    
    async def log_error(self, error: Exception, context: str = "", 
                       extra: Optional[Dict[str, Any]] = None):
        """记录错误日志"""
        error_data = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context,
            "timestamp": datetime.now().isoformat()
        }
        
        if extra:
            error_data.update(extra)
        
        await self.log_async(
            "error", 
            "error", 
            f"错误 - {context}: {str(error)}",
            error_data,
            "logs/error.log"
        )
    
    async def log_api_request(self, method: str, path: str, status_code: int, 
                            duration: float, user_id: Optional[str] = None,
                            extra: Optional[Dict[str, Any]] = None):
        """记录API请求日志"""
        request_data = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": round(duration * 1000, 2),
            "user_id": user_id,
            "timestamp": datetime.now().isoformat()
        }
        
        if extra:
            request_data.update(extra)
        
        await self.log_async(
            "api", 
            "info", 
            f"API请求 - {method} {path} {status_code} ({duration:.3f}s)",
            request_data,
            "logs/api.log"
        )
    
    async def log_cache_operation(self, operation: str, key: str, 
                                hit: Optional[bool] = None, ttl: Optional[int] = None,
                                extra: Optional[Dict[str, Any]] = None):
        """记录缓存操作日志"""
        cache_data = {
            "operation": operation,
            "key": key,
            "hit": hit,
            "ttl": ttl,
            "timestamp": datetime.now().isoformat()
        }
        
        if extra:
            cache_data.update(extra)
        
        await self.log_async(
            "cache", 
            "info", 
            f"缓存操作 - {operation}: {key}",
            cache_data,
            "logs/cache.log"
        )
    
    def close(self):
        """关闭日志服务"""
        try:
            self.executor.shutdown(wait=True)
        except Exception:
            pass

# 全局异步日志服务实例
async_logging_service = AsyncLoggingService()

# 便捷函数
async def log_info(logger_name: str, message: str, **kwargs):
    """异步记录信息日志"""
    await async_logging_service.log_async(logger_name, "info", message, kwargs, "logs/app.log")

async def log_warning(logger_name: str, message: str, **kwargs):
    """异步记录警告日志"""
    await async_logging_service.log_async(logger_name, "warning", message, kwargs, "logs/app.log")

async def log_error(logger_name: str, message: str, **kwargs):
    """异步记录错误日志"""
    await async_logging_service.log_async(logger_name, "error", message, kwargs, "logs/app.log")

async def log_debug(logger_name: str, message: str, **kwargs):
    """异步记录调试日志"""
    await async_logging_service.log_async(logger_name, "debug", message, kwargs, "logs/app.log")

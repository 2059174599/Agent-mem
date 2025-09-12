"""
统一日志配置模块
确保所有模块的日志都写入到app.log文件
"""

import logging
import os
import sys
from datetime import datetime
from config import Config

class UnifiedLoggingConfig:
    """统一日志配置类"""
    
    _initialized = False
    
    @classmethod
    def setup_logging(cls):
        """设置统一日志配置"""
        if cls._initialized:
            return
        
        # 确保logs目录存在
        os.makedirs('logs', exist_ok=True)
        
        # 获取日志级别
        log_level = getattr(logging, Config.get_log_level().upper(), logging.INFO)
        
        # 创建日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # 创建文件处理器
        file_handler = logging.FileHandler(
            'logs/app.log', 
            mode='a', 
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        
        # 配置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # 清除现有处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 添加处理器
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # 配置特定模块的日志器
        cls._configure_module_loggers(log_level, formatter)
        
        cls._initialized = True
        
        # 记录日志配置完成
        logger = logging.getLogger(__name__)
        logger.info("统一日志配置已完成")
    
    @classmethod
    def _configure_module_loggers(cls, log_level, formatter):
        """配置特定模块的日志器"""
        # 需要特殊配置的模块
        modules = [
            'models.redis_models',
            'services.llm_semantic_search_service',
            'services.async_memory_service_v2',
            'services.redis_cache_service',
            'models.es_models',
            'elastic_transport.transport',
            'elasticsearch',
            'httpx',
            'aiohttp'
        ]
        
        for module_name in modules:
            logger = logging.getLogger(module_name)
            logger.setLevel(log_level)
            
            # 确保不重复添加处理器
            if not logger.handlers:
                # 添加文件处理器
                file_handler = logging.FileHandler(
                    'logs/app.log', 
                    mode='a', 
                    encoding='utf-8'
                )
                file_handler.setLevel(log_level)
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
                
                # 添加控制台处理器
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(log_level)
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
            
            # 防止日志重复
            logger.propagate = False
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """获取配置好的日志器"""
        if not cls._initialized:
            cls.setup_logging()
        
        return logging.getLogger(name)
    
    @classmethod
    def setup_module_logging(cls, module_name: str):
        """为特定模块设置日志"""
        if not cls._initialized:
            cls.setup_logging()
        
        logger = logging.getLogger(module_name)
        
        # 如果模块还没有处理器，添加处理器
        if not logger.handlers:
            log_level = getattr(logging, Config.get_log_level().upper(), logging.INFO)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(process)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # 添加文件处理器
            file_handler = logging.FileHandler(
                'logs/app.log', 
                mode='a', 
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # 添加控制台处理器
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(log_level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)
            
            # 防止日志重复
            logger.propagate = False

# 全局函数，方便使用
def setup_logging():
    """设置统一日志配置"""
    UnifiedLoggingConfig.setup_logging()

def get_logger(name: str) -> logging.Logger:
    """获取配置好的日志器"""
    return UnifiedLoggingConfig.get_logger(name)

def setup_module_logging(module_name: str):
    """为特定模块设置日志"""
    UnifiedLoggingConfig.setup_module_logging(module_name)

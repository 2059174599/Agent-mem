"""
ARQ 异步任务定义
用于定时持久化任务
"""
import asyncio
from typing import Dict, Any
from datetime import datetime

from config import Config
from services.async_logging_service import log_info, log_error
from logging_config import get_logger

logger = get_logger(__name__)


async def persist_redis_to_storage(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    持久化任务 - 将Redis中的记忆数据持久化到ES或文件
    
    Args:
        ctx: ARQ上下文，包含共享资源
    
    Returns:
        任务执行结果
    """
    try:
        await log_info("arq_task", "🔄 开始执行定时持久化任务...")
        
        # 动态导入，避免循环依赖
        from models.redis_models import RedisService
        from services.persistence_service import get_persistence_backend
        
        redis_service = RedisService()
        backend = get_persistence_backend()
        
        # 扫描Redis中所有用户的facts
        pattern = "yaxin_memo:facts:*"
        redis_client = redis_service.redis
        
        cursor = 0
        persisted_count = 0
        failed_count = 0
        
        while True:
            cursor, keys = redis_client.scan(cursor, match=pattern, count=100)
            
            for key in keys:
                try:
                    # 解析key获取user_id和agent_id
                    # key格式: yaxin_memo:facts:user_id 或 yaxin_memo:facts:user_id:agent_id
                    parts = key.split(":")
                    if len(parts) >= 3:
                        user_id = parts[2]
                        agent_id = parts[3] if len(parts) > 3 else None
                        
                        # 获取该用户的事实
                        facts = await redis_service.get_facts(user_id, agent_id)
                        if facts:
                            facts_list = [fact.to_dict() for fact in facts]
                            
                            # 持久化
                            success = await backend.save_facts(user_id, agent_id, facts_list)
                            if success:
                                persisted_count += 1
                            else:
                                failed_count += 1
                
                except Exception as e:
                    await log_error("arq_task", f"持久化单个用户失败: {key}, {e}")
                    failed_count += 1
            
            if cursor == 0:
                break
        
        result = {
            "success": True,
            "persisted_count": persisted_count,
            "failed_count": failed_count,
            "timestamp": datetime.now().isoformat()
        }
        
        await log_info("arq_task", 
            f"✅ 定时持久化完成: 成功{persisted_count}个, 失败{failed_count}个")
        
        return result
        
    except Exception as e:
        await log_error("arq_task", f"❌ 执行持久化任务失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


async def persist_user_immediately(ctx: Dict[str, Any], user_id: str, agent_id: str = None) -> Dict[str, Any]:
    """
    立即持久化指定用户的数据
    
    Args:
        ctx: ARQ上下文
        user_id: 用户ID
        agent_id: Agent ID（可选）
    
    Returns:
        任务执行结果
    """
    try:
        await log_info("arq_task", f"🔄 立即持久化用户数据: user={user_id}, agent={agent_id}")
        
        from models.redis_models import RedisService
        from services.persistence_service import get_persistence_backend
        
        redis_service = RedisService()
        backend = get_persistence_backend()
        
        # 获取用户事实
        facts = await redis_service.get_facts(user_id, agent_id)
        if facts:
            facts_list = [fact.to_dict() for fact in facts]
            success = await backend.save_facts(user_id, agent_id, facts_list)
            
            if success:
                await log_info("arq_task", f"✅ 立即持久化成功: user={user_id}")
                return {
                    "success": True,
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "facts_count": len(facts_list),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "error": "保存失败",
                    "user_id": user_id,
                    "agent_id": agent_id
                }
        else:
            return {
                "success": False,
                "error": "未找到用户数据",
                "user_id": user_id,
                "agent_id": agent_id
            }
            
    except Exception as e:
        await log_error("arq_task", f"❌ 立即持久化失败: {e}")
        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "agent_id": agent_id
        }


# ARQ定时任务配置
class WorkerSettings:
    """ARQ Worker配置"""
    
    # Redis连接配置 - 使用 RedisSettings
    from arq.connections import RedisSettings
    
    redis_settings = RedisSettings(
        host=Config.get_redis_host(),
        port=Config.get_redis_port(),
        password=Config.get_redis_password() if Config.get_redis_password() else None,
        database=Config.get_redis_db(),
    )
    
    # 定时任务配置
    cron_jobs = []
    
    # 只有在启用持久化时才添加定时任务
    if Config.get_persistence_enabled():
        interval = Config.get_persistence_interval()
        
        # 如果interval > 0，使用cron定时执行
        if interval > 0:
            # 计算cron表达式 (每N秒执行一次，这里简化为分钟)
            minutes = max(1, interval // 60)  # 至少1分钟
            
            # ARQ的cron格式: (function, cron_schedule)
            from arq.cron import cron
            cron_jobs = [
                cron(persist_redis_to_storage, minute={i for i in range(0, 60, minutes)})
            ]
    
    # 任务函数列表
    functions = [
        persist_redis_to_storage,
        persist_user_immediately
    ]
    
    # Worker配置
    max_jobs = 10
    job_timeout = 300  # 5分钟超时
    keep_result = 3600  # 保留结果1小时
    
    # 日志配置
    log_results = True


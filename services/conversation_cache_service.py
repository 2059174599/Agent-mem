"""
对话缓存服务
负责管理最近对话的Redis缓存，优先从Redis读取，不足时从ES补充
"""
import json
from typing import List, Dict, Optional
from datetime import datetime
from config import Config
from logging_config import get_logger
from services.unified_cache_service import unified_cache_service

logger = get_logger(__name__)


class ConversationCacheService:
    """对话缓存服务 - 管理最近N轮对话"""
    
    def __init__(self):
        self.cache = unified_cache_service
        self.max_conversations = Config.get_env_or_default_int("MAX_CACHED_CONVERSATIONS", 20)
        self.cache_ttl = 3600  # 1小时过期
    
    def _get_cache_key(self, user_id: str, agent_id: Optional[str] = None) -> str:
        """获取缓存键"""
        if agent_id:
            return f"conversations:{user_id}:{agent_id}"
        return f"conversations:{user_id}"
    
    async def add_conversation(
        self,
        user_id: str,
        agent_id: Optional[str],
        question: str,
        answer: str,
        chat_id: str
    ) -> bool:
        """
        添加对话到缓存
        使用Redis List结构，最新的在前面（lpush）
        """
        try:
            cache_key = self._get_cache_key(user_id, agent_id)
            
            conversation = {
                "question": question,
                "answer": answer,
                "chat_id": chat_id,
                "timestamp": datetime.now().isoformat()
            }
            
            # 使用Redis原生命令
            from models.redis_models import RedisService
            redis_service = RedisService()
            redis_client = redis_service.redis
            
            # 1. 添加到列表头部（最新的在前）
            redis_client.lpush(cache_key, json.dumps(conversation))
            
            # 2. 保持列表长度不超过max_conversations
            redis_client.ltrim(cache_key, 0, self.max_conversations - 1)
            
            # 3. 设置过期时间
            redis_client.expire(cache_key, self.cache_ttl)
            
            logger.info(f"✅ 添加对话到缓存: user_id={user_id}, chat_id={chat_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加对话到缓存失败: {e}")
            return False
    
    async def get_recent_conversations(
        self,
        user_id: str,
        agent_id: Optional[str],
        limit: int = 10,
        es_service=None
    ) -> List[Dict]:
        """
        获取最近N轮对话
        
        策略：
        1. 先从Redis获取
        2. 如果数量不足，从ES补充
        3. 补充后更新Redis缓存
        
        Args:
            user_id: 用户ID
            agent_id: Agent ID
            limit: 需要的对话数量
            es_service: ES服务实例（用于补充数据）
            
        Returns:
            对话列表，按时间倒序（最新的在前）
        """
        try:
            cache_key = self._get_cache_key(user_id, agent_id)
            
            # 1. 从Redis获取
            from models.redis_models import RedisService
            redis_service = RedisService()
            redis_client = redis_service.redis
            
            # 获取前limit条记录
            cached_data = redis_client.lrange(cache_key, 0, limit - 1)
            
            conversations = []
            for data in cached_data:
                try:
                    conversations.append(json.loads(data))
                except Exception as e:
                    logger.warning(f"解析缓存对话失败: {e}")
                    continue
            
            cached_count = len(conversations)
            logger.info(f"📦 从Redis获取对话: user_id={user_id}, count={cached_count}/{limit}")
            
            # 2. 如果数量足够，直接返回
            if cached_count >= limit:
                return conversations[:limit]
            
            # 3. 数量不足，从ES补充
            if es_service is None:
                logger.warning("⚠️ ES服务未提供，无法补充对话")
                return conversations
            
            need_count = limit - cached_count
            logger.info(f"🔄 从ES补充对话: need={need_count}")
            
            # 从ES获取更多对话（跳过已缓存的）
            es_conversations = await self._fetch_from_es(
                es_service, 
                user_id, 
                agent_id, 
                skip=cached_count,  # 跳过Redis中已有的
                limit=need_count
            )
            
            # 4. 合并结果
            if es_conversations:
                conversations.extend(es_conversations)
                logger.info(f"✅ 从ES补充对话: count={len(es_conversations)}")
                
                # 5. 更新Redis缓存（异步，不阻塞）
                import asyncio
                asyncio.create_task(self._update_cache_from_es(
                    cache_key, es_conversations
                ))
            
            return conversations[:limit]
            
        except Exception as e:
            logger.error(f"❌ 获取最近对话失败: {e}")
            return []
    
    async def _fetch_from_es(
        self,
        es_service,
        user_id: str,
        agent_id: Optional[str],
        skip: int = 0,
        limit: int = 10
    ) -> List[Dict]:
        """从ES获取对话"""
        try:
            # 构建查询条件
            must_conditions = [
                {"term": {"user_id": user_id}}
            ]
            
            if agent_id:
                must_conditions.append({"term": {"agent_id": agent_id}})
            
            # 执行查询（使用get_recent_chats）
            all_results = es_service.get_recent_chats(
                user_id=user_id,
                agent_id=agent_id,
                limit=skip + limit
            )
            
            # 跳过前skip条，返回后limit条
            conversations = all_results[skip:skip + limit]
            
            return conversations
            
        except Exception as e:
            logger.error(f"❌ 从ES获取对话失败: {e}")
            return []
    
    async def _update_cache_from_es(
        self,
        cache_key: str,
        conversations: List[Dict]
    ) -> bool:
        """更新Redis缓存（异步后台任务）"""
        try:
            from models.redis_models import RedisService
            redis_service = RedisService()
            redis_client = redis_service.redis
            
            # 批量添加到列表尾部
            for conv in reversed(conversations):  # 倒序添加，保持时间顺序
                redis_client.rpush(cache_key, json.dumps(conv))
            
            # 保持列表长度
            redis_client.ltrim(cache_key, 0, self.max_conversations - 1)
            
            # 刷新过期时间
            redis_client.expire(cache_key, self.cache_ttl)
            
            logger.info(f"✅ 更新Redis缓存: key={cache_key}, count={len(conversations)}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新Redis缓存失败: {e}")
            return False
    
    async def clear_cache(self, user_id: str, agent_id: Optional[str] = None) -> bool:
        """清除用户的对话缓存"""
        try:
            cache_key = self._get_cache_key(user_id, agent_id)
            
            from models.redis_models import RedisService
            redis_service = RedisService()
            redis_client = redis_service.redis
            
            redis_client.delete(cache_key)
            
            logger.info(f"✅ 清除对话缓存: user_id={user_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 清除对话缓存失败: {e}")
            return False


# 全局单例
conversation_cache_service = ConversationCacheService()



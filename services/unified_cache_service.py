"""
统一缓存服务 - 所有缓存都使用yaxin_memo前缀
统一管理embedding缓存、事实缓存、LLM响应缓存等
"""

import json
import hashlib
import time
import random
from typing import Any, Optional, Dict, List, Union
from datetime import datetime, timedelta
import redis
from config import Config
from logging_config import get_logger

logger = get_logger(__name__)

class UnifiedCacheService:
    """统一缓存服务类 - 所有缓存都使用yaxin_memo前缀"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=Config.get_redis_host(),
            port=Config.get_redis_port(),
            password=Config.get_redis_password(),
            db=Config.get_redis_db(),  # 使用统一的Redis数据库
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        
        # 统一前缀
        self.base_prefix = "yaxin_memo"
        
        # 缓存类型前缀
        self.cache_prefixes = {
            "embedding": f"{self.base_prefix}:cache:embedding",
            "fact": f"{self.base_prefix}:cache:fact",
            "llm": f"{self.base_prefix}:cache:llm",
            "search": f"{self.base_prefix}:cache:search",
            "user_facts": f"{self.base_prefix}:facts",  # 用户事实数据
            "temp": f"{self.base_prefix}:temp"  # 临时数据
        }
        
        # 默认TTL配置
        self.default_ttls = {
            "embedding": 30 * 24 * 3600,  # 30天
            "fact": 7 * 24 * 3600,        # 7天
            "llm": 24 * 3600,             # 1天
            "search": 3600,               # 1小时
            "user_facts": -1,             # 永不过期
            "temp": 3600                  # 1小时
        }
        
        # 统计信息
        self.stats = {
            "hits": 0,
            "misses": 0,
            "saves": 0,
            "deletes": 0
        }
        
        logger.info("统一缓存服务初始化完成")
    
    def _get_cache_key(self, cache_type: str, key: str) -> str:
        """生成缓存键"""
        if cache_type not in self.cache_prefixes:
            raise ValueError(f"不支持的缓存类型: {cache_type}")
        
        return f"{self.cache_prefixes[cache_type]}:{key}"
    
    def _serialize_value(self, value: Any) -> str:
        """序列化值"""
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
    
    def _deserialize_value(self, value: str) -> Any:
        """反序列化值"""
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    def _get_ttl(self, cache_type: str, custom_ttl: Optional[int] = None) -> int:
        """获取TTL值"""
        if custom_ttl is not None:
            return custom_ttl
        
        base_ttl = self.default_ttls.get(cache_type, 3600)
        
        # 对于embedding缓存，添加随机TTL避免缓存雪崩
        if cache_type == "embedding":
            return base_ttl + random.randint(0, 7 * 24 * 3600)  # 30-37天随机
        
        return base_ttl
    
    async def get(self, cache_type: str, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            cache_key = self._get_cache_key(cache_type, key)
            value = self.redis_client.get(cache_key)
            
            if value is not None:
                self.stats["hits"] += 1
                logger.debug(f"缓存命中: {cache_type}:{key}")
                return self._deserialize_value(value)
            else:
                self.stats["misses"] += 1
                logger.debug(f"缓存未命中: {cache_type}:{key}")
                return None
                
        except Exception as e:
            logger.error(f"获取缓存失败: {cache_type}:{key}, 错误: {e}")
            return None
    
    async def set(self, cache_type: str, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            cache_key = self._get_cache_key(cache_type, key)
            serialized_value = self._serialize_value(value)
            ttl_value = self._get_ttl(cache_type, ttl)
            
            if ttl_value > 0:
                self.redis_client.setex(cache_key, ttl_value, serialized_value)
            else:
                self.redis_client.set(cache_key, serialized_value)
            
            self.stats["saves"] += 1
            logger.debug(f"缓存设置成功: {cache_type}:{key}, TTL: {ttl_value}")
            return True
            
        except Exception as e:
            logger.error(f"设置缓存失败: {cache_type}:{key}, 错误: {e}")
            return False
    
    async def delete(self, cache_type: str, key: str) -> bool:
        """删除缓存值"""
        try:
            cache_key = self._get_cache_key(cache_type, key)
            result = self.redis_client.delete(cache_key)
            
            if result > 0:
                self.stats["deletes"] += 1
                logger.debug(f"缓存删除成功: {cache_type}:{key}")
                return True
            else:
                logger.debug(f"缓存不存在: {cache_type}:{key}")
                return False
                
        except Exception as e:
            logger.error(f"删除缓存失败: {cache_type}:{key}, 错误: {e}")
            return False
    
    async def clear_pattern(self, cache_type: str, pattern: str = "*") -> int:
        """清除匹配模式的缓存"""
        try:
            cache_prefix = self.cache_prefixes.get(cache_type, f"{self.base_prefix}:{cache_type}")
            search_pattern = f"{cache_prefix}:{pattern}"
            keys = self.redis_client.keys(search_pattern)
            
            if keys:
                deleted_count = self.redis_client.delete(*keys)
                logger.info(f"清除缓存模式成功: {cache_type}:{pattern}, 删除数量: {deleted_count}")
                return deleted_count
            else:
                logger.debug(f"未找到匹配的缓存: {cache_type}:{pattern}")
                return 0
                
        except Exception as e:
            logger.error(f"清除缓存模式失败: {cache_type}:{pattern}, 错误: {e}")
            return 0
    
    async def clear_all_project_cache(self) -> int:
        """清除项目所有缓存"""
        try:
            total_deleted = 0
            
            # 清除所有类型的缓存
            for cache_type in self.cache_prefixes.keys():
                deleted = await self.clear_pattern(cache_type, "*")
                total_deleted += deleted
            
            logger.info(f"清除项目所有缓存完成, 总删除数量: {total_deleted}")
            return total_deleted
            
        except Exception as e:
            logger.error(f"清除项目所有缓存失败: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            info = self.redis_client.info('memory')
            keyspace = self.redis_client.info('keyspace')
            
            # 获取各类型缓存键数量
            cache_counts = {}
            for cache_type, prefix in self.cache_prefixes.items():
                keys = self.redis_client.keys(f"{prefix}:*")
                cache_counts[cache_type] = len(keys)
            
            return {
                "cache_counts": cache_counts,
                "total_keys": sum(cache_counts.values()),
                "memory_used": info.get('used_memory_human', 'N/A'),
                "memory_peak": info.get('used_memory_peak_human', 'N/A'),
                "keyspace": keyspace,
                "base_prefix": self.base_prefix,
                "stats": self.stats
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"error": str(e)}
    
    def generate_cache_key(self, prefix: str, *args) -> str:
        """生成缓存键"""
        # 将参数组合并生成MD5哈希
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    async def batch_get(self, cache_type: str, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存"""
        try:
            cache_keys = [self._get_cache_key(cache_type, key) for key in keys]
            values = self.redis_client.mget(cache_keys)
            
            result = {}
            for i, value in enumerate(values):
                if value is not None:
                    result[keys[i]] = self._deserialize_value(value)
                    self.stats["hits"] += 1
                else:
                    self.stats["misses"] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"批量获取缓存失败: {cache_type}, 错误: {e}")
            return {}
    
    async def batch_set(self, cache_type: str, items: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """批量设置缓存"""
        try:
            pipe = self.redis_client.pipeline()
            ttl_value = self._get_ttl(cache_type, ttl)
            
            for key, value in items.items():
                cache_key = self._get_cache_key(cache_type, key)
                serialized_value = self._serialize_value(value)
                
                if ttl_value > 0:
                    pipe.setex(cache_key, ttl_value, serialized_value)
                else:
                    pipe.set(cache_key, serialized_value)
            
            pipe.execute()
            self.stats["saves"] += len(items)
            logger.debug(f"批量设置缓存成功: {cache_type}, 数量: {len(items)}")
            return True
            
        except Exception as e:
            logger.error(f"批量设置缓存失败: {cache_type}, 错误: {e}")
            return False
    
    # 便捷方法
    async def get_embedding(self, key: str) -> Optional[Any]:
        """获取embedding缓存"""
        return await self.get("embedding", key)
    
    async def set_embedding(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置embedding缓存"""
        return await self.set("embedding", key, value, ttl)
    
    async def get_fact(self, key: str) -> Optional[Any]:
        """获取事实缓存"""
        return await self.get("fact", key)
    
    async def set_fact(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置事实缓存"""
        return await self.set("fact", key, value, ttl)
    
    async def get_llm_response(self, key: str) -> Optional[Any]:
        """获取LLM响应缓存"""
        return await self.get("llm", key)
    
    async def set_llm_response(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置LLM响应缓存"""
        return await self.set("llm", key, value, ttl)
    
    async def get_user_facts(self, user_id: str, agent_id: Optional[str] = None) -> Optional[Any]:
        """获取用户事实数据"""
        key = f"{user_id}:{agent_id}" if agent_id else user_id
        return await self.get("user_facts", key)
    
    async def set_user_facts(self, user_id: str, value: Any, agent_id: Optional[str] = None) -> bool:
        """设置用户事实数据"""
        key = f"{user_id}:{agent_id}" if agent_id else user_id
        return await self.set("user_facts", key, value, -1)  # 永不过期

# 创建全局实例
unified_cache_service = UnifiedCacheService()
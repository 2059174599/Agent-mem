"""
Redis缓存服务 - 支持多进程的分布式缓存
"""
import json
import hashlib
from typing import Any, Optional, Dict, List
from datetime import datetime, timedelta
import redis
from config import Config
from logging_config import get_logger

logger = get_logger(__name__)

class RedisCacheService:
    """Redis缓存服务类 - 支持多进程"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host=Config.get_redis_host(),
            port=Config.get_redis_port(),
            password=Config.get_redis_password(),
            db=Config.get_redis_cache_db(),  # 使用统一的缓存数据库6
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True
        )
        self.cache_prefix = "yaxin_memo:cache:"
        self.default_ttl = Config.get_env_or_default_int("CACHE_TTL", 3600)  # 默认1小时
        
    def _get_cache_key(self, key: str) -> str:
        """生成缓存键"""
        return f"{self.cache_prefix}{key}"
    
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
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值"""
        try:
            cache_key = self._get_cache_key(key)
            value = self.redis_client.get(cache_key)
            
            if value is None:
                logger.debug(f"缓存未命中: {key}")
                return None
            
            logger.debug(f"缓存命中: {key}")
            return self._deserialize_value(value)
            
        except Exception as e:
            logger.error(f"获取缓存失败: {key}, 错误: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存值"""
        try:
            cache_key = self._get_cache_key(key)
            serialized_value = self._serialize_value(value)
            ttl = ttl or self.default_ttl
            
            result = self.redis_client.setex(cache_key, ttl, serialized_value)
            
            if result:
                logger.debug(f"缓存设置成功: {key}, TTL: {ttl}秒")
                return True
            else:
                logger.warning(f"缓存设置失败: {key}")
                return False
                
        except Exception as e:
            logger.error(f"设置缓存失败: {key}, 错误: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存"""
        try:
            cache_key = self._get_cache_key(key)
            result = self.redis_client.delete(cache_key)
            
            if result > 0:
                logger.debug(f"缓存删除成功: {key}")
                return True
            else:
                logger.debug(f"缓存不存在: {key}")
                return False
                
        except Exception as e:
            logger.error(f"删除缓存失败: {key}, 错误: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """检查缓存是否存在"""
        try:
            cache_key = self._get_cache_key(key)
            return bool(self.redis_client.exists(cache_key))
        except Exception as e:
            logger.error(f"检查缓存存在性失败: {key}, 错误: {e}")
            return False
    
    async def get_ttl(self, key: str) -> int:
        """获取缓存剩余时间"""
        try:
            cache_key = self._get_cache_key(key)
            ttl = self.redis_client.ttl(cache_key)
            return ttl if ttl > 0 else 0
        except Exception as e:
            logger.error(f"获取缓存TTL失败: {key}, 错误: {e}")
            return 0
    
    async def extend_ttl(self, key: str, ttl: int) -> bool:
        """延长缓存时间"""
        try:
            cache_key = self._get_cache_key(key)
            result = self.redis_client.expire(cache_key, ttl)
            
            if result:
                logger.debug(f"缓存TTL延长成功: {key}, 新TTL: {ttl}秒")
                return True
            else:
                logger.warning(f"缓存TTL延长失败: {key}")
                return False
                
        except Exception as e:
            logger.error(f"延长缓存TTL失败: {key}, 错误: {e}")
            return False
    
    async def clear_pattern(self, pattern: str) -> int:
        """清除匹配模式的缓存"""
        try:
            cache_pattern = self._get_cache_key(pattern)
            keys = self.redis_client.keys(cache_pattern)
            
            if keys:
                deleted_count = self.redis_client.delete(*keys)
                logger.info(f"清除缓存模式成功: {pattern}, 删除数量: {deleted_count}")
                return deleted_count
            else:
                logger.debug(f"未找到匹配的缓存: {pattern}")
                return 0
                
        except Exception as e:
            logger.error(f"清除缓存模式失败: {pattern}, 错误: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        try:
            info = self.redis_client.info('memory')
            keyspace = self.redis_client.info('keyspace')
            
            # 获取缓存键数量
            cache_keys = self.redis_client.keys(f"{self.cache_prefix}*")
            cache_count = len(cache_keys)
            
            return {
                "cache_count": cache_count,
                "memory_used": info.get('used_memory_human', 'N/A'),
                "memory_peak": info.get('used_memory_peak_human', 'N/A'),
                "keyspace": keyspace,
                "cache_prefix": self.cache_prefix
            }
            
        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {"error": str(e)}
    
    def generate_cache_key(self, prefix: str, *args) -> str:
        """生成缓存键"""
        # 将参数组合并生成MD5哈希
        key_data = f"{prefix}:{':'.join(str(arg) for arg in args)}"
        return hashlib.md5(key_data.encode('utf-8')).hexdigest()
    
    async def batch_get(self, keys: List[str]) -> Dict[str, Any]:
        """批量获取缓存"""
        try:
            cache_keys = [self._get_cache_key(key) for key in keys]
            values = self.redis_client.mget(cache_keys)
            
            result = {}
            for i, value in enumerate(values):
                if value is not None:
                    result[keys[i]] = self._deserialize_value(value)
            
            logger.debug(f"批量获取缓存: {len(result)}/{len(keys)} 命中")
            return result
            
        except Exception as e:
            logger.error(f"批量获取缓存失败: {e}")
            return {}
    
    async def batch_set(self, data: Dict[str, Any], ttl: Optional[int] = None) -> int:
        """批量设置缓存"""
        try:
            ttl = ttl or self.default_ttl
            pipe = self.redis_client.pipeline()
            
            for key, value in data.items():
                cache_key = self._get_cache_key(key)
                serialized_value = self._serialize_value(value)
                pipe.setex(cache_key, ttl, serialized_value)
            
            results = pipe.execute()
            success_count = sum(1 for r in results if r)
            
            logger.debug(f"批量设置缓存: {success_count}/{len(data)} 成功")
            return success_count
            
        except Exception as e:
            logger.error(f"批量设置缓存失败: {e}")
            return 0

"""
Embedding服务 - 处理embedding生成和缓存
"""

import asyncio
import aiohttp
import random
from typing import List
from config import Config
from services.async_logging_service import log_info, log_error, log_warning
from services.unified_cache_service import unified_cache_service

class EmbeddingService:
    """Embedding服务类"""
    
    def __init__(self):
        self.session = None
        self.cache_service = unified_cache_service
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    def _get_cache_key(self, text: str, cache_type: str = "embedding") -> str:
        """生成缓存键"""
        return self.cache_service.generate_cache_key(cache_type, text)
    
    def _get_embedding_cache_ttl(self) -> int:
        """获取embedding缓存的随机TTL（1-3个月）"""
        min_ttl = Config.get_embedding_cache_ttl_min()
        max_ttl = Config.get_embedding_cache_ttl_max()
        return random.randint(min_ttl, max_ttl)
    
    async def get_embedding(self, text: str) -> List[float]:
        """获取embedding - 带缓存"""
        try:
            # 检查缓存
            cache_key = self._get_cache_key(text, "embedding")
            cached_embedding = await self.cache_service.get("embedding", cache_key)
            
            if cached_embedding:
                await log_info("embedding", f"缓存命中: {text[:30]}...")
                return cached_embedding
            
            # 调用embedding API
            embedding = await self._call_embedding_with_retry(text, Config.get_embedding_retry_count())
            
            if embedding:
                # 缓存结果
                ttl = self._get_embedding_cache_ttl()
                await self.cache_service.set("embedding", cache_key, embedding, ttl)
                await log_info("embedding", f"Embedding已缓存: TTL={ttl}秒")
            
            return embedding
            
        except Exception as e:
            await log_error("embedding", f"Embedding获取失败: {e}")
            return []
    
    async def _call_embedding_with_retry(self, text: str, retry_count: int) -> List[float]:
        """带重试机制的embedding调用"""
        for attempt in range(retry_count + 1):
            try:
                if not self.session:
                    self.session = aiohttp.ClientSession()
                
                payload = {
                    "input": text,
                    "model": Config.get_embedding_model()
                }
                
                async with self.session.post(
                    Config.get_embedding_base_url(),
                    json=payload,
                    headers={"Authorization": f"Bearer {Config.get_embedding_api_key()}"},
                    timeout=aiohttp.ClientTimeout(total=Config.get_embedding_timeout())
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        embedding = result["data"][0]["embedding"]
                        if attempt > 0:
                            await log_info("embedding", f"Embedding调用成功 (重试第{attempt}次): {text[:30]}...")
                        return embedding
                    else:
                        if attempt < retry_count:
                            await log_warning("embedding", f"Embedding调用失败，状态码: {response.status}，准备重试 (第{attempt + 1}次)")
                            await asyncio.sleep(Config.get_embedding_retry_delay() * (attempt + 1))  # 指数退避
                            continue
                        else:
                            await log_error("embedding", f"Embedding调用失败，状态码: {response.status}，已重试{retry_count}次")
                            return []
                            
            except asyncio.TimeoutError:
                if attempt < retry_count:
                    await log_warning("embedding", f"Embedding调用超时，准备重试 (第{attempt + 1}次)")
                    await asyncio.sleep(Config.get_embedding_retry_delay() * (attempt + 1))
                    continue
                else:
                    await log_error("embedding", f"Embedding调用超时，已重试{retry_count}次")
                    return []
                    
            except Exception as e:
                if attempt < retry_count:
                    await log_warning("embedding", f"Embedding调用异常: {e}，准备重试 (第{attempt + 1}次)")
                    await asyncio.sleep(Config.get_embedding_retry_delay() * (attempt + 1))
                    continue
                else:
                    await log_error("embedding", f"Embedding调用异常: {e}，已重试{retry_count}次")
                    return []
        
        return []

# 全局实例
embedding_service = EmbeddingService()

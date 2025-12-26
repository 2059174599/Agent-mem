"""
Redis轻量图谱服务
使用Redis原生数据结构（Set + Sorted Set）模拟图谱关系
"""
import numpy as np
from typing import List, Optional
from config import Config
from logging_config import get_logger
from services.async_logging_service import log_info, log_error
from services.embedding_service import embedding_service

logger = get_logger(__name__)


class RedisLightGraphService:
    """Redis轻量图谱服务"""
    
    def __init__(self):
        self.similarity_threshold = Config.get_env_or_default_float(
            "GRAPH_SIMILARITY_THRESHOLD", 0.7
        )
        self.max_relations_per_fact = Config.get_env_or_default_int(
            "MAX_RELATIONS_PER_FACT", 5
        )
    
    def _get_topic_index_key(
        self,
        user_id: str,
        agent_id: Optional[str],
        topic: str,
        sub_topic: str
    ) -> str:
        """获取主题索引key"""
        if agent_id:
            return f"topic_index:{user_id}:{agent_id}:{topic}:{sub_topic}"
        return f"topic_index:{user_id}:{topic}:{sub_topic}"
    
    def _get_relations_key(
        self,
        user_id: str,
        agent_id: Optional[str],
        fact_id: str
    ) -> str:
        """获取关系存储key"""
        if agent_id:
            return f"relations:{user_id}:{agent_id}:{fact_id}"
        return f"relations:{user_id}:{fact_id}"
    
    async def build_relations_for_fact(
        self,
        redis_client,
        user_id: str,
        agent_id: Optional[str],
        new_fact_id: str,
        new_fact_memo: str,
        new_fact_topic: str,
        new_fact_sub_topic: str,
        new_fact_embedding: Optional[List[float]] = None
    ) -> int:
        """
        为新事实建立关系
        
        流程：
        1. 添加到主题索引（Redis Set）
        2. 查找同主题的其他事实
        3. 计算相似度，建立关系（Redis Sorted Set）
        
        Args:
            redis_client: Redis客户端
            user_id: 用户ID
            agent_id: Agent ID
            new_fact_id: 新事实ID（topic:sub_topic）
            new_fact_memo: 新事实内容
            new_fact_topic: 主题
            new_fact_sub_topic: 子主题
            new_fact_embedding: 新事实的embedding（可选）
            
        Returns:
            建立的关系数量
        """
        try:
            # 1. 添加到主题索引
            topic_index_key = self._get_topic_index_key(
                user_id, agent_id, new_fact_topic, new_fact_sub_topic
            )
            redis_client.sadd(topic_index_key, new_fact_id)
            
            # 2. 获取同主题的其他事实
            same_topic_facts = redis_client.smembers(topic_index_key)
            same_topic_facts = [f for f in same_topic_facts if f != new_fact_id]
            
            if not same_topic_facts:
                await log_info(
                    "graph",
                    f"📊 无同主题事实，跳过关系建立: fact_id={new_fact_id}"
                )
                return 0
            
            # 3. 获取新事实的embedding
            if not new_fact_embedding:
                new_fact_embedding = await embedding_service.get_embedding(new_fact_memo)
            
            if not new_fact_embedding:
                await log_info(
                    "graph",
                    f"⚠️ 无法获取embedding，跳过关系建立: fact_id={new_fact_id}"
                )
                return 0
            
            # 4. 计算相似度并建立关系
            relations_count = 0
            new_embedding = np.array(new_fact_embedding)
            
            # 获取所有同主题事实的embedding
            from services.unified_cache_service import unified_cache_service
            facts_data = await unified_cache_service.get_user_facts(user_id, agent_id) or {}
            
            for existing_fact_id in same_topic_facts:
                # 获取existing fact的memo
                existing_fact_data = facts_data.get(existing_fact_id)
                if not existing_fact_data:
                    continue
                
                existing_memo = existing_fact_data.get("memo", "")
                if not existing_memo:
                    continue
                
                # 获取existing fact的embedding
                existing_embedding_list = await embedding_service.get_embedding(existing_memo)
                if not existing_embedding_list:
                    continue
                
                existing_embedding = np.array(existing_embedding_list)
                
                # 计算余弦相似度
                similarity = self._cosine_similarity(new_embedding, existing_embedding)
                
                # 如果相似度 > 阈值，建立关系
                if similarity > self.similarity_threshold:
                    # 双向关系
                    # new -> existing
                    new_relations_key = self._get_relations_key(user_id, agent_id, new_fact_id)
                    redis_client.zadd(new_relations_key, {existing_fact_id: similarity})
                    
                    # existing -> new
                    existing_relations_key = self._get_relations_key(user_id, agent_id, existing_fact_id)
                    redis_client.zadd(existing_relations_key, {new_fact_id: similarity})
                    
                    relations_count += 1
                    
                    # 保持关系数量不超过上限
                    redis_client.zremrangebyrank(new_relations_key, 0, -(self.max_relations_per_fact + 1))
                    redis_client.zremrangebyrank(existing_relations_key, 0, -(self.max_relations_per_fact + 1))
            
            if relations_count > 0:
                await log_info(
                    "graph",
                    f"✅ 建立关系: fact_id={new_fact_id}, count={relations_count}"
                )
            else:
                await log_info(
                    "graph",
                    f"📊 未找到相似事实: fact_id={new_fact_id}"
                )
            
            return relations_count
            
        except Exception as e:
            await log_error("graph", f"❌ 建立关系失败: {e}")
            return 0
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        try:
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            similarity = dot_product / (norm1 * norm2)
            return float(similarity)
            
        except Exception as e:
            logger.warning(f"计算余弦相似度失败: {e}")
            return 0.0
    
    async def get_related_facts(
        self,
        redis_client,
        user_id: str,
        agent_id: Optional[str],
        fact_id: str,
        top_k: int = 3
    ) -> List[tuple]:
        """
        获取相关事实
        
        Args:
            redis_client: Redis客户端
            user_id: 用户ID
            agent_id: Agent ID
            fact_id: 事实ID
            top_k: 返回Top-K个相关事实
            
        Returns:
            [(related_id, similarity), ...]
        """
        try:
            relations_key = self._get_relations_key(user_id, agent_id, fact_id)
            
            # 获取Top-K相关事实（按相似度降序）
            related_facts = redis_client.zrange(
                relations_key,
                0,
                top_k - 1,
                desc=True,
                withscores=True
            )
            
            return [(fact_id, score) for fact_id, score in related_facts]
            
        except Exception as e:
            logger.warning(f"获取相关事实失败: {e}")
            return []
    
    async def remove_fact_relations(
        self,
        redis_client,
        user_id: str,
        agent_id: Optional[str],
        fact_id: str
    ) -> bool:
        """
        删除事实的所有关系
        
        Args:
            redis_client: Redis客户端
            user_id: 用户ID
            agent_id: Agent ID
            fact_id: 事实ID
            
        Returns:
            是否成功
        """
        try:
            # 1. 获取所有相关事实
            relations_key = self._get_relations_key(user_id, agent_id, fact_id)
            related_ids = redis_client.zrange(relations_key, 0, -1)
            
            # 2. 从相关事实中删除到当前事实的关系
            for related_id in related_ids:
                related_relations_key = self._get_relations_key(user_id, agent_id, related_id)
                redis_client.zrem(related_relations_key, fact_id)
            
            # 3. 删除当前事实的关系集合
            redis_client.delete(relations_key)
            
            # 4. 从主题索引中删除
            # 需要遍历所有可能的主题（实际应用中可以通过存储topic信息来优化）
            # 这里简化处理，实际可以在删除时传入topic信息
            
            await log_info("graph", f"✅ 删除事实关系: fact_id={fact_id}")
            return True
            
        except Exception as e:
            await log_error("graph", f"❌ 删除事实关系失败: {e}")
            return False


# 全局单例
redis_light_graph = RedisLightGraphService()



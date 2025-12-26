"""
轻量级混合检索服务
结合向量检索 + 时序加权 + Redis轻量图谱
"""
import math
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from config import Config
from logging_config import get_logger
from services.async_logging_service import log_info, log_error
from services.embedding_service import embedding_service

logger = get_logger(__name__)


class LightweightHybridSearchService:
    """轻量级混合检索服务"""
    
    def __init__(self):
        self.enable_graph = Config.get_env_or_default_bool("ENABLE_GRAPH_SEARCH", False)
        self.time_decay_factor = Config.get_env_or_default_float("TIME_DECAY_FACTOR", 0.03)
        self.similarity_threshold = Config.get_env_or_default_float("GRAPH_SIMILARITY_THRESHOLD", 0.7)
    
    async def search(
        self,
        redis_service,
        user_id: str,
        agent_id: Optional[str],
        query: str,
        max_results: int = 10
    ) -> List[Dict]:
        """
        混合检索策略
        
        策略：
        1. 事实数 < 30 → 全返回 + 时序排序
        2. 事实数 30-100 → 向量检索 + 时序加权
        3. 事实数 > 100 → 向量检索 + 时序加权 + 可选图谱扩展
        
        Args:
            redis_service: Redis服务实例
            user_id: 用户ID
            agent_id: Agent ID
            query: 查询文本
            max_results: 最大结果数
            
        Returns:
            检索结果列表，按最终分数排序
        """
        try:
            # 1. 获取所有事实
            all_facts = await redis_service.get_facts(user_id, agent_id)
            fact_count = len(all_facts)
            
            await log_info(
                "hybrid_search",
                f"🔍 混合检索: user_id={user_id}, fact_count={fact_count}, query={query[:30]}..."
            )
            
            # 2. 根据事实数量选择策略
            if fact_count < 30:
                # 策略1：全返回 + 时序排序
                return await self._strategy_small(all_facts, max_results)
            
            elif fact_count < 100:
                # 策略2：向量检索 + 时序加权
                return await self._strategy_medium(
                    redis_service, user_id, agent_id, query, all_facts, max_results
                )
            
            else:
                # 策略3：向量检索 + 时序加权 + 可选图谱
                if self.enable_graph:
                    return await self._strategy_large_with_graph(
                        redis_service, user_id, agent_id, query, all_facts, max_results
                    )
                else:
                    # 降级为策略2
                    return await self._strategy_medium(
                        redis_service, user_id, agent_id, query, all_facts, max_results
                    )
            
        except Exception as e:
            await log_error("hybrid_search", f"❌ 混合检索失败: {e}")
            return []
    
    async def _strategy_small(
        self,
        all_facts: List,
        max_results: int
    ) -> List[Dict]:
        """
        策略1：事实数 < 30，全返回 + 时序排序
        
        优点：
        - 无检索开销（0ms）
        - 保证不漏掉任何事实
        
        排序：最近的在前
        """
        try:
            # 转换为字典并添加时序分数
            results = []
            for fact in all_facts:
                time_score = self._get_time_score(fact.updated_at)
                results.append({
                    "id": fact.fact_key,
                    "topic": fact.topic,
                    "sub_topic": fact.sub_topic,
                    "memo": fact.memo,
                    "updated_at": fact.updated_at.isoformat(),
                    "score": time_score,  # 只用时间分数
                    "time_score": time_score,
                    "search_strategy": "small_full_return"
                })
            
            # 按时间分数排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            await log_info(
                "hybrid_search",
                f"✅ 策略1（全返回）: 返回{min(len(results), max_results)}/{len(results)}条"
            )
            
            return results[:max_results]
            
        except Exception as e:
            await log_error("hybrid_search", f"❌ 策略1失败: {e}")
            return []
    
    async def _strategy_medium(
        self,
        redis_service,
        user_id: str,
        agent_id: Optional[str],
        query: str,
        all_facts: List,
        max_results: int
    ) -> List[Dict]:
        """
        策略2：事实数 30-100，向量检索 + 时序加权
        
        流程：
        1. 向量检索Top-20
        2. 时序加权（向量70% + 时序30%）
        3. 返回Top-N
        
        延迟：~100ms
        """
        try:
            # 1. 向量检索
            query_embedding = await embedding_service.get_embedding(query)
            if not query_embedding:
                # 降级为策略1
                return await self._strategy_small(all_facts, max_results)
            
            vector_results = await redis_service.search_facts_by_embedding(
                user_id=user_id,
                agent_id=agent_id,
                query_embedding=query_embedding,
                top_k=min(20, len(all_facts))
            )
            
            # 2. 时序加权
            results = []
            for result in vector_results:
                vector_score = result.get("score", 0.0)
                updated_at_str = result.get("updated_at")
                
                # 解析时间
                if updated_at_str:
                    try:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        time_score = self._get_time_score(updated_at)
                    except:
                        time_score = 0.5  # 默认中等分数
                else:
                    time_score = 0.5
                
                # 混合分数：向量70% + 时序30%
                final_score = vector_score * 0.7 + time_score * 0.3
                
                results.append({
                    **result,
                    "score": final_score,
                    "vector_score": vector_score,
                    "time_score": time_score,
                    "search_strategy": "medium_vector_time"
                })
            
            # 3. 排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            await log_info(
                "hybrid_search",
                f"✅ 策略2（向量+时序）: 返回{min(len(results), max_results)}/{len(results)}条"
            )
            
            return results[:max_results]
            
        except Exception as e:
            await log_error("hybrid_search", f"❌ 策略2失败: {e}")
            # 降级为策略1
            return await self._strategy_small(all_facts, max_results)
    
    async def _strategy_large_with_graph(
        self,
        redis_service,
        user_id: str,
        agent_id: Optional[str],
        query: str,
        all_facts: List,
        max_results: int
    ) -> List[Dict]:
        """
        策略3：事实数 > 100，向量检索 + 时序加权 + 图谱扩展
        
        流程：
        1. 向量检索Top-5（种子）
        2. 图谱扩展1跳（找到相关事实）
        3. 时序加权
        4. 去重+排序，返回Top-N
        
        延迟：~130ms（向量100ms + 图谱30ms）
        """
        try:
            # 1. 向量检索（种子事实）
            query_embedding = await embedding_service.get_embedding(query)
            if not query_embedding:
                # 降级为策略2
                return await self._strategy_medium(
                    redis_service, user_id, agent_id, query, all_facts, max_results
                )
            
            seed_results = await redis_service.search_facts_by_embedding(
                user_id=user_id,
                agent_id=agent_id,
                query_embedding=query_embedding,
                top_k=5  # 只取Top-5作为种子
            )
            
            await log_info(
                "hybrid_search",
                f"🌱 种子事实: {len(seed_results)}条"
            )
            
            # 2. 图谱扩展（1跳）
            expanded_results = await self._expand_with_graph(
                redis_service, user_id, agent_id, seed_results
            )
            
            await log_info(
                "hybrid_search",
                f"🔗 图谱扩展: {len(expanded_results)}条（含种子）"
            )
            
            # 3. 时序加权 + 距离衰减
            results = []
            fact_ids = set()  # 去重
            
            for result in expanded_results:
                fact_id = result.get("id")
                if fact_id in fact_ids:
                    continue
                fact_ids.add(fact_id)
                
                vector_score = result.get("vector_score", 0.0)
                distance = result.get("distance", 0)  # 图谱距离（0=种子，1=1跳）
                updated_at_str = result.get("updated_at")
                
                # 解析时间
                if updated_at_str:
                    try:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        time_score = self._get_time_score(updated_at)
                    except:
                        time_score = 0.5
                else:
                    time_score = 0.5
                
                # 距离衰减：种子=1.0，1跳=0.8
                distance_factor = 1.0 if distance == 0 else 0.8
                
                # 混合分数：向量50% + 时序30% + 距离20%
                final_score = (
                    vector_score * 0.5 +
                    time_score * 0.3 +
                    distance_factor * 0.2
                )
                
                results.append({
                    **result,
                    "score": final_score,
                    "vector_score": vector_score,
                    "time_score": time_score,
                    "distance": distance,
                    "search_strategy": "large_graph"
                })
            
            # 4. 排序
            results.sort(key=lambda x: x["score"], reverse=True)
            
            await log_info(
                "hybrid_search",
                f"✅ 策略3（图谱扩展）: 返回{min(len(results), max_results)}/{len(results)}条"
            )
            
            return results[:max_results]
            
        except Exception as e:
            await log_error("hybrid_search", f"❌ 策略3失败: {e}")
            # 降级为策略2
            return await self._strategy_medium(
                redis_service, user_id, agent_id, query, all_facts, max_results
            )
    
    def _get_time_score(self, updated_at: datetime) -> float:
        """
        计算时序分数
        
        公式：score = e^(-λ * hours)
        - λ = 0.03（默认）
        - 1小时前: 0.97
        - 24小时前: 0.49
        - 7天前: 0.14
        
        Returns:
            时序分数（0.0-1.0）
        """
        try:
            now = datetime.now()
            time_diff = now - updated_at
            hours_ago = time_diff.total_seconds() / 3600
            
            # 指数衰减
            time_score = math.exp(-self.time_decay_factor * hours_ago)
            
            return max(0.0, min(1.0, time_score))
            
        except Exception as e:
            logger.warning(f"计算时序分数失败: {e}")
            return 0.5  # 默认中等分数
    
    async def _expand_with_graph(
        self,
        redis_service,
        user_id: str,
        agent_id: Optional[str],
        seed_results: List[Dict]
    ) -> List[Dict]:
        """
        使用Redis轻量图谱扩展
        
        流程：
        1. 获取种子事实的相关事实ID（从Redis Sorted Set）
        2. 获取相关事实详情
        3. 返回种子+相关事实
        
        延迟：~30ms
        """
        try:
            expanded = []
            
            # 添加种子事实（distance=0）
            for seed in seed_results:
                expanded.append({
                    **seed,
                    "distance": 0,
                    "vector_score": seed.get("score", 0.0)
                })
            
            # 扩展1跳
            from models.redis_models import RedisService
            redis_service_instance = RedisService()
            redis_client = redis_service_instance.redis
            
            for seed in seed_results:
                fact_id = seed.get("id")
                if not fact_id:
                    continue
                
                # 从Redis Sorted Set获取相关事实
                relations_key = self._get_relations_key(user_id, agent_id, fact_id)
                related_ids = redis_client.zrange(relations_key, 0, 2)  # Top-3相关事实
                
                for related_id in related_ids:
                    # 获取相关事实详情
                    related_fact = await self._get_fact_by_id(
                        redis_service, user_id, agent_id, related_id
                    )
                    
                    if related_fact:
                        # 获取相似度（作为vector_score）
                        similarity = redis_client.zscore(relations_key, related_id) or 0.0
                        
                        expanded.append({
                            **related_fact,
                            "distance": 1,
                            "vector_score": similarity
                        })
            
            return expanded
            
        except Exception as e:
            await log_error("hybrid_search", f"❌ 图谱扩展失败: {e}")
            # 返回种子事实
            return seed_results
    
    def _get_relations_key(
        self,
        user_id: str,
        agent_id: Optional[str],
        fact_id: str
    ) -> str:
        """获取关系存储的key"""
        if agent_id:
            return f"relations:{user_id}:{agent_id}:{fact_id}"
        return f"relations:{user_id}:{fact_id}"
    
    async def _get_fact_by_id(
        self,
        redis_service,
        user_id: str,
        agent_id: Optional[str],
        fact_id: str
    ) -> Optional[Dict]:
        """根据ID获取事实详情"""
        try:
            all_facts = await redis_service.get_facts(user_id, agent_id)
            
            for fact in all_facts:
                if fact.fact_key == fact_id:
                    return {
                        "id": fact.fact_key,
                        "topic": fact.topic,
                        "sub_topic": fact.sub_topic,
                        "memo": fact.memo,
                        "updated_at": fact.updated_at.isoformat()
                    }
            
            return None
            
        except Exception as e:
            logger.warning(f"获取事实详情失败: {e}")
            return None


# 全局单例
lightweight_hybrid_search = LightweightHybridSearchService()



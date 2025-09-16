import redis
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from config import Config
from logging_config import get_logger
from services.unified_cache_service import unified_cache_service
from services.llm_service import llm_service
from prompts.fact_extraction import FACT_SEARCH_FILTER_PROMPT, FACT_SEARCH_FILTER_USER_PROMPT

logger = get_logger(__name__)

class FactDocument:
    """事实文档模型"""
    
    def __init__(self, user_id: str, agent_id: Optional[str], 
                 topic: str, sub_topic: str, memo: str, 
                 created_at: datetime = None, updated_at: datetime = None, 
                 chat_id: Optional[str] = None):
        self.user_id = user_id
        self.agent_id = agent_id
        self.topic = topic
        self.sub_topic = sub_topic
        self.memo = memo
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.chat_id = chat_id  # 使用chat_id作为关联字段
        
        # 保持向后兼容性
        self.timestamp = self.updated_at
    
    @property
    def fact_key(self) -> str:
        """获取事实的唯一键：topic:sub_topic"""
        return f"{self.topic}:{self.sub_topic}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "topic": self.topic,
            "sub_topic": self.sub_topic,
            "memo": self.memo,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "timestamp": self.timestamp.isoformat(),  # 保持向后兼容性
            "chat_id": self.chat_id  # 使用chat_id作为关联字段
        }
    
    def to_simple_dict(self) -> Dict[str, Any]:
        """返回简化的字典格式，只包含关键字段"""
        return {
            "topic": self.topic,
            "sub_topic": self.sub_topic,
            "memo": self.memo,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "timestamp": self.timestamp.isoformat()  # 保持向后兼容性
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FactDocument':
        # 处理向后兼容性
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        timestamp = data.get("timestamp")
        
        if created_at is None and timestamp is not None:
            created_at = timestamp
        if updated_at is None and timestamp is not None:
            updated_at = timestamp
            
        return cls(
            user_id=data["user_id"],
            agent_id=data.get("agent_id"),
            topic=data["topic"],
            sub_topic=data["sub_topic"],
            memo=data["memo"],
            created_at=datetime.fromisoformat(created_at) if created_at else None,
            updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
            chat_id=data.get("chat_id")  # 使用chat_id作为关联字段
        )

class RedisService:
    """Redis服务类 - 使用统一缓存服务"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisService, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            logger.info(f"初始化redis连接，节点: {Config.get_redis_host()}:{Config.get_redis_port()}")
            self.redis = redis.Redis(
                host=Config.get_redis_host(),
                port=Config.get_redis_port(),
                password=Config.get_redis_password(),
                db=Config.get_redis_db(),
                decode_responses=True
            )
            # 使用统一缓存服务
            self.cache = unified_cache_service
            RedisService._initialized = True
    
    async def init_predefined_topics(self):
        """初始化预定义主题到Redis"""
        try:
            predefined_topics = Config.get_predefined_topics()
            
            # 将预定义主题存储到Redis
            await self.cache.set("temp", "predefined_topics", predefined_topics, 86400)  # 24小时过期
            
            logger.info(f"预定义主题已初始化: {len(predefined_topics)} 个主题")
            for topic, sub_topics in predefined_topics.items():
                logger.info(f"  - {topic}: {len(sub_topics)} 个子主题")
                
        except Exception as e:
            logger.error(f"初始化预定义主题失败: {e}")
            raise
    
    def _get_facts_key(self, user_id: str, agent_id: Optional[str] = None) -> str:
        """获取事实存储的key - 使用统一前缀"""
        if agent_id:
            return f"{user_id}:{agent_id}"
        return user_id
    
    async def add_fact(self, fact: FactDocument) -> bool:
        """添加事实 - 使用统一缓存服务"""
        try:
            key = self._get_facts_key(fact.user_id, fact.agent_id)
            sub_topic_key = f"{fact.topic}:{fact.sub_topic}"

            # 获取现有事实数据
            existing_facts = await self.cache.get_user_facts(fact.user_id, fact.agent_id) or {}

            # 添加新事实
            existing_facts[sub_topic_key] = fact.to_dict()

            # 保存到统一缓存
            success = await self.cache.set_user_facts(fact.user_id, existing_facts, fact.agent_id)

            if success:
                logger.info(f"添加事实: key={key}, sub_topic={sub_topic_key}")
                return True
            else:
                logger.error(f"添加事实失败: 缓存保存失败")
                return False

        except Exception as e:
            logger.error(f"添加事实失败: {e}")
            return False

    async def get_facts(self, user_id: str, agent_id: Optional[str] = None) -> List[FactDocument]:
        """获取用户的所有事实 - 使用统一缓存服务"""
        try:
            logger.info(f'获取事实: user_id={user_id}, agent_id={agent_id}')

            # 从统一缓存获取事实数据
            facts_data = await self.cache.get_user_facts(user_id, agent_id) or {}

            facts = []
            for sub_topic_key, fact_data in facts_data.items():
                try:
                    facts.append(FactDocument.from_dict(fact_data))
                except Exception as e:
                    logger.warning(f"解析事实失败: {sub_topic_key}, 错误: {e}")
                    continue

            logger.info(f'获取事实: user_id={user_id}, agent_id={agent_id}, count={len(facts)}')
            return facts
        except Exception as e:
            logger.error(f"获取事实失败: {e}")
            return []

    async def update_fact(self, fact_key: str, update_data: Dict) -> bool:
        """更新事实 - 通过fact_key(topic:sub_topic)查找并更新"""
        try:
            logger.info(f'更新事实: fact_key={fact_key}')

            # 从统一缓存获取所有事实数据
            facts_data = await self.cache.get_user_facts(update_data.get("user_id", ""), update_data.get("agent_id")) or {}
            if not facts_data:
                logger.error(f"未找到用户事实数据: user_id={update_data.get('user_id')}, agent_id={update_data.get('agent_id')}")
                return False

            # 查找要更新的事实
            if fact_key not in facts_data:
                logger.error(f"未找到要更新的事实: fact_key={fact_key}")
                return False

            fact_to_update = facts_data[fact_key]

            # 更新事实数据
            updated_fact_data = {**fact_to_update, **update_data}
            updated_fact_data["updated_at"] = datetime.now().isoformat()

            # 保存更新后的事实
            facts_data[fact_key] = updated_fact_data
            success = await self.cache.set_user_facts(
                updated_fact_data["user_id"],
                facts_data,
                updated_fact_data.get("agent_id")
            )

            if success:
                logger.info(f"更新事实成功: fact_key={fact_key}")
                return True
            else:
                logger.error(f"更新事实失败: 缓存保存失败")
                return False

        except Exception as e:
            logger.error(f"更新事实失败: {e}")
            return False

    async def search_facts(self, user_id: str, query: str,
                    agent_id: Optional[str] = None) -> List[FactDocument]:
        """智能搜索相关事实 - 优化后的搜索策略
        
        策略说明：
        1. 默认返回用户所有事实
        2. 当事实数量超过阈值时，强制使用LLM智能过滤
        3. 确保搜索结果的准确性和相关性
        """
        try:
            facts = await self.get_facts(user_id, agent_id)
            if not facts:
                logger.info(f"用户 {user_id} 没有找到任何事实")
                return []

            # 检查事实数量是否超过阈值
            fact_count_threshold = Config.get_search_strategy("fact_count_threshold")
            
            if len(facts) > fact_count_threshold:
                # 事实数量超过阈值，使用LLM智能过滤
                logger.info(f"事实数量 {len(facts)} 超过阈值 {fact_count_threshold}，启用LLM智能过滤")
                return await self._llm_filter_facts(facts, query)
            else:
                # 事实数量未超过阈值，直接返回所有事实
                logger.info(f"事实数量 {len(facts)} 未超过阈值 {fact_count_threshold}，返回所有事实")
                
                # 按时间排序（最新的在前）
                facts.sort(key=lambda x: x.updated_at or x.created_at, reverse=True)
                
                # 限制结果数量（防止返回过多结果）
                max_results = Config.get_search_strategy("max_search_results")
                if max_results and len(facts) > max_results:
                    facts = facts[:max_results]
                    logger.info(f"限制结果数量为 {max_results} 条")
                
                logger.info(f"搜索事实: query='{query}', 返回 {len(facts)} 条事实")
                return facts

        except Exception as e:
            logger.error(f"搜索事实失败: {e}")
            return []

    def _topic_relevance_search(self, facts: List[FactDocument], query: str) -> List[FactDocument]:
        """主题相关性搜索 - 核心搜索策略"""
        relevant_facts = []
        query_lower = query.lower()

        # 预处理：使用统一的标点符号清理配置
        query_clean = Config.clean_text(query_lower)

        # 从配置文件获取主题关键词映射
        topic_keywords = Config.get_topic_keywords()

        # 扩展查询关键词（同义词、近义词）
        query_expansions = self._expand_query_keywords(query_clean)

        logger.debug(f"主题搜索 - 查询: '{query}', 清理后: '{query_clean}', 扩展关键词: {query_expansions}")

        for fact in facts:
            logger.debug(f"检查事实: {fact.topic} - {fact.sub_topic} - {fact.memo}")

            # 检查查询是否与事实主题相关
            topic_keywords_list = topic_keywords.get(fact.topic, [])

            # 1. 直接主题匹配（优化：降低匹配要求）
            if any(keyword in query_clean for keyword in topic_keywords_list):
                logger.debug(f"直接主题匹配成功: {fact.sub_topic}")
                relevant_facts.append(fact)
                continue

            # 1.1 扩展匹配：检查查询中的任何词是否在主题关键词中
            query_words = query_clean.split()
            if any(word in topic_keywords_list for word in query_words):
                logger.debug(f"扩展主题匹配成功: {fact.sub_topic}")
                relevant_facts.append(fact)
                continue

            # 2. 子主题直接匹配（新增）
            if fact.sub_topic.lower() in query_clean:
                logger.debug(f"子主题直接匹配成功: {fact.sub_topic}")
                relevant_facts.append(fact)
                continue

            # 3. 扩展关键词匹配
            if any(expanded in fact.topic.lower() or expanded in fact.sub_topic.lower()
                   for expanded in query_expansions):
                logger.debug(f"扩展关键词匹配成功: {fact.sub_topic}")
                relevant_facts.append(fact)
                continue

            # 4. 内容相关性判断
            if self._is_content_relevant(fact, query_clean):
                logger.debug(f"内容相关性匹配成功: {fact.sub_topic}")
                relevant_facts.append(fact)

        logger.debug(f"主题搜索找到 {len(relevant_facts)} 条相关事实")
        return relevant_facts

    def _expand_query_keywords(self, query: str) -> List[str]:
        """扩展查询关键词（同义词、近义词）"""
        expanded = [query]

        # 从配置文件获取同义词映射
        synonyms = Config.get_synonyms_mapping()

        for original, synonym_list in synonyms.items():
            if original in query:
                expanded.extend(synonym_list)
            for synonym in synonym_list:
                if synonym in query:
                    expanded.append(original)

        return expanded

    def _is_content_relevant(self, fact: FactDocument, query: str) -> bool:
        """判断事实内容是否与查询相关（优化后降低匹配要求）"""
        fact_text = f"{fact.topic} {fact.sub_topic} {fact.memo}".lower()
        query_lower = query.lower()

        # 预处理：使用统一的标点符号清理配置
        query_clean = Config.clean_text(query_lower)
        fact_clean = Config.clean_text(fact_text)

        # 1. 词汇重叠度计算（优化：降低阈值）
        query_words = set(query_clean.split())
        fact_words = set(fact_clean.split())

        if len(query_words) > 0:
            overlap = len(query_words.intersection(fact_words))
            # 降低阈值：只要有1个词重叠就认为相关
            if overlap > 0:
                return True

        # 2. 同义词匹配（使用配置中的同义词）
        synonyms_mapping = Config.get_synonyms_mapping()

        # 检查查询和事实内容中的同义词匹配
        for query_word in query_words:
            if query_word in synonyms_mapping:
                synonyms = synonyms_mapping[query_word]
                if any(synonym in fact_clean for synonym in synonyms):
                    return True

        # 检查事实内容中的词汇是否在查询中（通过同义词映射）
        for fact_word in fact_clean.split():
            if fact_word in synonyms_mapping:
                synonyms = synonyms_mapping[fact_word]
                if any(synonym in query_clean for synonym in synonyms):
                    return True

        # 3. 语义相关性判断（基于关键词组合）
        # 从配置文件获取语义模式
        semantic_patterns = Config.get_semantic_patterns()

        for main_topic, related_topics in semantic_patterns:
            if main_topic in query_clean:
                if any(related in fact_clean for related in related_topics):
                    return True

        # 4. 直接关键词匹配（优化：更精确的匹配）
        for word in query_words:
            if word in fact_clean:
                return True
            # 支持部分匹配：但要求匹配长度至少为2个字符，避免单字符误匹配
            if len(word) >= 2:
                for fact_word in fact_clean.split():
                    if len(fact_word) >= 2 and (word in fact_word or fact_word in word):
                        # 额外检查：确保不是偶然的部分匹配
                        if word == fact_word or (len(word) >= 3 and len(fact_word) >= 3):
                            return True

        # 5. 反向匹配：检查查询是否包含事实内容中的关键词
        fact_keywords = fact_clean.split()
        for keyword in fact_keywords:
            if keyword in query_clean:
                return True
            # 支持部分匹配：但要求匹配长度至少为2个字符
            if len(keyword) >= 2:
                for query_word in query_words:
                    if len(query_word) >= 2 and (keyword in query_word or query_word in keyword):
                        # 额外检查：确保不是偶然的部分匹配
                        if keyword == query_word or (len(keyword) >= 3 and len(query_word) >= 3):
                            return True

        # 6. 特殊身份关键词匹配（针对"你是谁"查询）
        identity_keywords = ["小智", "三岁", "四岁", "助手", "AI", "机器人", "年龄", "岁"]
        if any(keyword in fact_clean for keyword in identity_keywords):
            # 如果事实包含身份相关信息，且查询是身份相关的问题
            identity_queries = ["你是谁", "你叫什么", "你的名字", "你多大了", "你几岁了"]
            if any(identity_query in query_clean for identity_query in identity_queries):
                return True

        # 7. 称呼相关匹配（更精确的匹配逻辑）
        call_related_queries = ["怎么称呼你", "如何称呼你", "叫你什么", "你的称呼", "你叫什么名字"]
        if any(call_query in query_clean for call_query in call_related_queries):
            # 只有当事实明确包含称呼相关信息时才匹配
            call_related_facts = ["称呼", "名字", "姓名", "小智", "助手"]
            if any(call_fact in fact_clean for call_fact in call_related_facts):
                # 进一步检查：确保事实内容确实与称呼相关
                if "称呼" in fact_clean and ("助手" in fact_clean or "名字" in fact_clean or "姓名" in fact_clean):
                    return True

        return False

    def _keyword_search(self, facts: List[FactDocument], query: str) -> List[FactDocument]:
        """关键词搜索（辅助搜索）"""
        relevant_facts = []
        query_lower = query.lower()

        # 预处理：使用统一的标点符号清理配置
        query_clean = Config.clean_text(query_lower)
        query_words = set(query_clean.split())

        # 从配置文件获取关键词搜索阈值
        threshold = Config.get_search_threshold("keyword_similarity")

        for fact in facts:
            fact_text = f"{fact.topic} {fact.sub_topic} {fact.memo}".lower()
            fact_clean = Config.clean_text(fact_text)
            fact_words = set(fact_clean.split())

            # 计算词汇重叠度
            overlap = len(query_words.intersection(fact_words))
            total_unique = len(query_words.union(fact_words))

            if total_unique > 0:
                similarity = overlap / total_unique
                if similarity > threshold:
                    relevant_facts.append(fact)

        return relevant_facts

    def _semantic_relevance_search(self, facts: List[FactDocument], query: str) -> List[FactDocument]:
        """语义相关性搜索"""
        relevant_facts = []
        query_lower = query.lower()

        # 预处理：使用统一的标点符号清理配置
        query_clean = Config.clean_text(query_lower)

        # 从配置文件获取语义搜索阈值
        threshold = Config.get_search_threshold("semantic_similarity")

        for fact in facts:
            # 基于语义模式的相似性判断
            if self._calculate_semantic_similarity(query_clean, fact) >= threshold:
                relevant_facts.append(fact)

        return relevant_facts

    def _calculate_semantic_similarity(self, query: str, fact: FactDocument) -> float:
        """计算语义相似度"""
        fact_text = f"{fact.topic} {fact.sub_topic} {fact.memo}".lower()

        # 预处理：使用统一的标点符号清理配置
        fact_clean = Config.clean_text(fact_text)

        # 基于语义模式的相似性计算
        semantic_patterns = Config.get_semantic_patterns()
        max_similarity = 0.0

        for main_topic, related_topics in semantic_patterns:
            if main_topic in query:
                # 计算与相关主题的匹配度
                matches = sum(1 for topic in related_topics if topic in fact_clean)
                if matches > 0:
                    similarity = matches / len(related_topics)
                    max_similarity = max(max_similarity, similarity)

        return max_similarity

    def _llm_semantic_search(self, facts: List[FactDocument], query: str) -> List[FactDocument]:
        """LLM语义搜索 - 使用LLM进行智能语义匹配"""
        try:
            # 导入LLM语义搜索服务
            from services.llm_semantic_search_service import LLMSemanticSearchService

            # 使用异步上下文管理器
            import asyncio

            async def _async_search():
                async with LLMSemanticSearchService() as search_service:
                    return await search_service.search_with_fallback(facts, query, 10)

            # 检查是否已有事件循环在运行
            try:
                loop = asyncio.get_running_loop()
                # 如果已有事件循环，使用线程池执行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(self._run_async_search, facts, query)
                    return future.result()
            except RuntimeError:
                # 没有运行中的事件循环，创建新的
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    results = loop.run_until_complete(_async_search())
                    return results
                finally:
                    loop.close()

        except Exception as e:
            logger.error(f"LLM语义搜索异常: {e}")
            return []

    def _run_async_search(self, facts: List[FactDocument], query: str) -> List[FactDocument]:
        """在线程池中运行异步搜索"""
        import asyncio
        from services.llm_semantic_search_service import LLMSemanticSearchService

        async def _async_search():
            async with LLMSemanticSearchService() as search_service:
                return await search_service.search_with_fallback(facts, query, 10)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(_async_search())
        finally:
            loop.close()

    def _rank_facts_by_relevance(self, facts: List[FactDocument], query: str) -> List[FactDocument]:
        """按相关性排序事实"""
        if not facts:
            return facts

        try:
            scored_facts = []
            query_lower = query.lower()

            # 预处理：使用统一的标点符号清理配置
            query_clean = Config.clean_text(query_lower)

            for fact in facts:
                score = 0.0
                fact_text = f"{fact.topic} {fact.sub_topic} {fact.memo}".lower()
                fact_clean = Config.clean_text(fact_text)

                # 1. 主题匹配分数
                if query_clean in fact.topic.lower():
                    score += Config.get_search_weight("topic_match")
                elif query_clean in fact.sub_topic.lower():
                    score += Config.get_search_weight("sub_topic_match")

                # 2. 内容匹配分数
                if query_clean in fact.memo.lower():
                    score += Config.get_search_weight("content_match")

                # 3. 词汇重叠分数
                query_words = set(query_clean.split())
                fact_words = set(fact_clean.split())
                overlap = len(query_words.intersection(fact_words))
                score += overlap * Config.get_search_weight("keyword_overlap")

                # 4. 时间新鲜度分数（如果启用）
                if Config.get_search_strategy("enable_time_ranking"):
                    days_old = (datetime.now() - fact.timestamp).days
                    if days_old <= 7:
                        score += Config.get_search_weight("time_freshness_7d")
                    elif days_old <= 30:
                        score += Config.get_search_weight("time_freshness_30d")

                scored_facts.append((fact, score))

            # 按分数排序
            scored_facts.sort(key=lambda x: x[1], reverse=True)

            return [fact for fact, score in scored_facts]

        except Exception as e:
            logger.error(f"事实排序失败: {e}")
            return facts

    def delete_fact(self, user_id: str, topic: str, sub_topic: str,
                   agent_id: Optional[str] = None) -> bool:
        """删除事实"""
        try:
            key = self._get_facts_key(user_id, agent_id)
            sub_topic_key = f"{topic}:{sub_topic}"

            # 删除事实
            self.redis.hdel(key, sub_topic_key)
            
            logger.info(f"删除事实: {sub_topic_key}")
            return True
            
        except Exception as e:
            logger.error(f"删除事实失败: {e}")
            return False
    
    async def delete_fact_by_chat_id(self, user_id: str, chat_id: str, 
                                   agent_id: Optional[str] = None) -> bool:
        """根据chat_id删除事实"""
        try:
            key = self._get_facts_key(user_id, agent_id)
            facts = await self.cache.get_user_facts(key) or {}
            
            # 查找匹配chat_id的事实
            fact_to_delete = None
            for fact_key, fact_data in facts.items():
                if fact_data.get("chat_id") == chat_id:
                    fact_to_delete = fact_key
                    break
            
            if fact_to_delete:
                del facts[fact_to_delete]
                await self.cache.set_user_facts(key, facts)
                logger.info(f"根据chat_id删除事实成功: {fact_key}")
                return True
            else:
                logger.warning(f"未找到chat_id为{chat_id}的事实")
                return False
        except Exception as e:
            logger.error(f"根据chat_id删除事实失败: {e}")
            return False
    
    async def delete_all_facts(self, user_id: str, agent_id: Optional[str] = None) -> bool:
        """删除用户所有事实"""
        try:
            key = self._get_facts_key(user_id, agent_id)
            await self.cache.set_user_facts(key, {})
            logger.info(f"删除用户所有事实成功: {key}")
            return True
        except Exception as e:
            logger.error(f"删除用户所有事实失败: {e}")
            return False
    
    async def update_fact_by_chat_id(self, user_id: str, chat_id: str, 
                                   new_memo: str, agent_id: Optional[str] = None,
                                   new_topic: Optional[str] = None, new_sub_topic: Optional[str] = None) -> bool:
        """根据chat_id更新事实的memo、topic和sub_topic"""
        try:
            key = self._get_facts_key(user_id, agent_id)
            facts = await self.cache.get_user_facts(key) or {}
            
            # 查找匹配chat_id的事实
            fact_to_update = None
            for fact_key, fact_data in facts.items():
                if fact_data.get("chat_id") == chat_id:
                    fact_to_update = fact_key
                    break
            
            if fact_to_update:
                # 更新memo
                facts[fact_to_update]["memo"] = new_memo
                
                # 如果提供了新的topic和sub_topic，需要更新
                if new_topic and new_sub_topic:
                    # 删除旧的事实键
                    old_fact_data = facts[fact_to_update].copy()
                    del facts[fact_to_update]
                    
                    # 创建新的事实键
                    new_fact_key = f"{new_topic}:{new_sub_topic}"
                    facts[new_fact_key] = old_fact_data
                    facts[new_fact_key]["topic"] = new_topic
                    facts[new_fact_key]["sub_topic"] = new_sub_topic
                    fact_to_update = new_fact_key
                elif new_topic:
                    # 只更新topic，保持sub_topic不变
                    facts[fact_to_update]["topic"] = new_topic
                elif new_sub_topic:
                    # 只更新sub_topic，保持topic不变
                    facts[fact_to_update]["sub_topic"] = new_sub_topic
                    # 需要更新事实键
                    old_fact_data = facts[fact_to_update].copy()
                    del facts[fact_to_update]
                    new_fact_key = f"{old_fact_data['topic']}:{new_sub_topic}"
                    facts[new_fact_key] = old_fact_data
                    fact_to_update = new_fact_key
                
                # 更新时间戳
                facts[fact_to_update]["updated_at"] = datetime.now().isoformat()
                facts[fact_to_update]["timestamp"] = facts[fact_to_update]["updated_at"]  # 保持兼容性
                
                await self.cache.set_user_facts(key, facts)
                logger.info(f"根据chat_id更新事实成功: {fact_to_update}")
                return True
            else:
                logger.warning(f"未找到chat_id为{chat_id}的事实")
                return False
        except Exception as e:
            logger.error(f"根据chat_id更新事实失败: {e}")
            return False
    
    def get_facts_by_topic(self, user_id: str, topic: str, 
                          agent_id: Optional[str] = None) -> List[FactDocument]:
        """根据主题获取事实"""
        try:
            facts = self.get_facts(user_id, agent_id)
            return [fact for fact in facts if fact.topic == topic]
        except Exception as e:
            logger.error(f"根据主题获取事实失败: {e}")
            return []
    
    def get_facts_count(self, user_id: str, agent_id: Optional[str] = None) -> int:
        """获取用户事实数量"""
        try:
            key = self._get_facts_key(user_id, agent_id)
            return self.redis.hlen(key)
        except Exception as e:
            logger.error(f"获取事实数量失败: {e}")
            return 0
    
    async def _llm_filter_facts(self, facts: List[FactDocument], query: str) -> List[FactDocument]:
        """使用LLM智能过滤事实"""
        try:
            logger.info(f"开始LLM智能过滤: query='{query}', facts_count={len(facts)}")
            
            # 构建事实列表字符串
            facts_list = []
            for i, fact in enumerate(facts):
                facts_list.append(f"{i}. [{fact.topic} - {fact.sub_topic}] {fact.memo}")
            
            facts_text = "\n".join(facts_list)
            
            # 构建用户提示词
            user_prompt = FACT_SEARCH_FILTER_USER_PROMPT.format(
                query=query,
                facts_list=facts_text
            )
            
            # 调用LLM
            response = await llm_service.call_llm_async(
                system_prompt=FACT_SEARCH_FILTER_PROMPT,
                user_prompt=user_prompt
            )
            
            if not response:
                logger.warning("LLM调用失败，返回原始事实列表")
                return facts
            
            # 解析LLM响应
            try:
                result = json.loads(response)
                relevant_facts = result.get("relevant_facts", [])
                
                # 根据索引获取相关事实
                filtered_facts = []
                for item in relevant_facts:
                    index = item.get("index", -1)
                    if 0 <= index < len(facts):
                        filtered_facts.append(facts[index])
                        logger.info(f"选择事实 {index}: {facts[index].topic} - {facts[index].sub_topic} (相关性: {item.get('relevance_score', 0)})")
                
                logger.info(f"LLM智能过滤完成: 从 {len(facts)} 条事实中筛选出 {len(filtered_facts)} 条相关事实")
                return filtered_facts
                
            except json.JSONDecodeError as e:
                logger.error(f"解析LLM响应失败: {e}")
                return facts
                
        except Exception as e:
            logger.error(f"LLM智能过滤失败: {e}")
            return facts

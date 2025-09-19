"""
异步记忆服务 V2 - 优化版本
使用chat_id作为关联，简化并发逻辑
"""

import asyncio
import aiohttp
import json
import hashlib
import time
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
from models.es_models import ESService, ChatDocument
from models.redis_models import RedisService, FactDocument
from services.unified_cache_service import unified_cache_service
from services.async_logging_service import async_logging_service, log_info, log_error, log_warning
from services.llm_service import llm_service
from services.embedding_service import embedding_service
from services.fact_extraction_service import fact_extraction_service
from config import Config
from logging_config import get_logger

logger = get_logger(__name__)

class AsyncMemoryServiceV2:
    """异步记忆服务类 V2 - 优化版本"""
    
    def __init__(self):
        self.es_service = ESService()
        self.redis_service = RedisService()
        self.cache_service = unified_cache_service  # 使用统一缓存服务
        self.llm_service = llm_service  # 添加LLM服务
        
        # 异步HTTP客户端
        self.session = None
        
        # 性能统计
        self.stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "avg_response_time": 0.0
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    
    async def async_extract_facts(self, question: str) -> Dict:
        """异步提取事实 - 使用LLM服务"""
        try:
            await log_info("fact_extraction", f"🔍 开始事实提取: question={question[:50]}...")
            
            # 使用LLM服务
            result = await llm_service.extract_facts(question)
            
            if result and result.get("contains_facts"):
                await log_info("fact_extraction", f"✅ 事实提取成功: {len(result.get('facts', []))}个事实")
            else:
                await log_info("fact_extraction", f"ℹ️ 未提取到事实")
            
            return result
            
        except Exception as e:
            await log_error("fact_extraction", f"❌ 事实提取失败: {e}")
            return {"contains_facts": False, "facts": []}
    
    
    async def async_get_embedding(self, text: str) -> List[float]:
        """异步获取embedding - 使用embedding服务"""
        try:
            # 使用embedding服务
            embedding = await embedding_service.get_embedding(text)
            
            if embedding:
                self.stats["cache_hits"] += 1
            else:
                self.stats["cache_misses"] += 1
            
            return embedding
            
        except Exception as e:
            await log_error("embedding", f"Embedding获取失败: {e}")
            return []
    
    
    async def add_memory_async(self, user_id: str, agent_id: Optional[str], 
                              question: str, answer: str) -> Dict:
        """异步添加记忆 - 优化并发执行，使用chat_id作为关联"""
        start_time = time.time()
        self.stats["total_requests"] += 1
        
        try:
            await log_info("memory", f"🔄 开始添加记忆: user_id={user_id}, question={question[:50]}...")
            
            # 1. 答案质量检测（根据配置决定是否启用）
            quality_config = Config.get_quality_check_config()
            if quality_config["enabled"]:
                quality_check = await self._check_answer_quality(question, answer, quality_config)
                if not quality_check["is_valid"]:
                    await log_warning("memory", f"答案质量检测失败: {quality_check['reason']}")
                    return {
                        "success": False,
                        "error": f"答案质量不符合要求: {quality_check['reason']}",
                        "processing_time": time.time() - start_time,
                        "quality_check": quality_check
                    }
            else:
                quality_check = {"is_valid": True, "reason": "质量检测已禁用", "score": 1.0}
            
            # 并行执行：问题embedding生成、ES存储
            tasks = [
                self.async_get_embedding(question),
                self._store_chat_to_es(user_id, agent_id, question, answer)
            ]
            
            # 等待embedding和ES存储完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            question_embedding = results[0] if not isinstance(results[1], Exception) else []
            chat_id = results[1] if not isinstance(results[1], Exception) else None
            
            if not chat_id:
                raise Exception("ES存储失败，无法获取chat_id")
            
            await log_info("es", f"✅ 对话已存储到ES: chat_id={chat_id}")
            
            # 处理embedding（如果ES存储时没有获取到）
            if not question_embedding:
                await log_info("es", f"🔄 更新ES记录embedding: chat_id={chat_id}")
                # 只使用问题的embedding
                if question_embedding:
                    self.es_service.update_chat_embedding(chat_id, question_embedding)
            
            # 使用两阶段事实提取服务
            await log_info("fact_processing", f"🔍 开始两阶段事实提取: question={question[:50]}...")
            
            fact_result = await fact_extraction_service.extract_facts_two_stage(
                user_id, agent_id, question, answer, chat_id
            )
            
            facts_added = []
            if fact_result.get("success", False):
                stage1_facts = fact_result.get("stage1_facts", [])
                stage2_actions = fact_result.get("stage2_actions", [])
                final_facts = fact_result.get("final_facts", [])
                
                await log_info("fact_processing", f"✅ 两阶段事实提取完成:")
                await log_info("fact_processing", f"  📋 第一阶段提取: {len(stage1_facts)} 个事实")
                await log_info("fact_processing", f"  🔄 第二阶段操作: {len(stage2_actions)} 个操作")
                await log_info("fact_processing", f"  📝 最终结果: {len(final_facts)} 个事实")
                
                # 为最终事实设置chat_id
                for fact_info in final_facts:
                    fact_info["chat_id"] = chat_id
                    facts_added.append(fact_info)
                
                # 记录详细的操作日志
                for i, action in enumerate(stage2_actions):
                    action_type = action.get("action", "unknown")
                    if action_type == "add":
                        await log_info("fact_processing", f"  ✅ 操作 {i+1}: 添加事实 - {action.get('fact', {}).get('topic', 'N/A')}")
                    elif action_type == "update":
                        await log_info("fact_processing", f"  🔄 操作 {i+1}: 更新事实 - {action.get('new_fact', {}).get('topic', 'N/A')}")
                    elif action_type == "skip":
                        await log_info("fact_processing", f"  ⏭️ 操作 {i+1}: 跳过事实 - {action.get('fact', {}).get('topic', 'N/A')} (原因: {action.get('reason', '未知')})")
            else:
                await log_info("fact_processing", f"ℹ️ 两阶段事实提取未成功: {fact_result.get('message', '未知原因')}")
            
            total_time = time.time() - start_time
            self.stats["avg_response_time"] = (
                (self.stats["avg_response_time"] * (self.stats["total_requests"] - 1) + total_time) 
                / self.stats["total_requests"]
            )
            
            # 记录性能日志
            await async_logging_service.log_performance("add_memory", total_time, True, {
                "user_id": user_id,
                "chat_id": chat_id,
                "facts_count": len(facts_added),
                "cache_hits": self.stats["cache_hits"],
                "cache_misses": self.stats["cache_misses"]
            })
            
            await log_info("memory", f"记忆添加完成: {total_time:.3f}秒, chat_id={chat_id}, {len(facts_added)}个事实")
            
            return {
                "success": True,
                "chat_id": chat_id,
                "facts_added": facts_added,
                "total_facts": len(facts_added),
                "processing_time": total_time,
                "cache_hits": self.stats["cache_hits"],
                "cache_misses": self.stats["cache_misses"]
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            await log_error("memory", f"记忆添加失败: {e}, 耗时: {total_time:.3f}秒")
            
            # 记录错误性能日志
            await async_logging_service.log_performance("add_memory", total_time, False, {
                "user_id": user_id,
                "error": str(e)
            })
            
            return {
                "success": False,
                "error": str(e),
                "processing_time": total_time
            }
    
    async def _store_chat_to_es(self, user_id: str, agent_id: Optional[str], 
                               question: str, answer: str) -> Optional[str]:
        """存储聊天记录到ES"""
        try:
            # 只生成问题的embedding（因为搜索时只有问题）
            question_embedding = await self.async_get_embedding(question)
            
            # 创建聊天文档
            chat_doc = ChatDocument(user_id, agent_id, question, answer)
            chat_doc.embedding = question_embedding  # 只使用问题的embedding
            
            # 存储到ES
            chat_id = self.es_service.add_chat(chat_doc)
            return chat_id
            
        except Exception as e:
            await log_error("es", f"ES存储失败: {e}")
            return None
    
    async def _check_answer_quality(self, question: str, answer: str, config: Dict = None) -> Dict:
        """检查答案质量，过滤脏数据"""
        try:
            if config is None:
                config = Config.get_quality_check_config()
            
            # 优化后的长度检查：更智能的长度判断
            min_length = config["min_answer_length"]
            answer_len = len(answer.strip())
            
            if answer_len < min_length:
                # 检查是否为简单问题或有意义的简短回答
                if self._is_simple_question(question) or self._is_meaningful_answer(answer):
                    # 对于简单问题或有意义的回答，降低长度要求
                    min_length = max(2, min_length // 3)  # 最少2个字符
                    if answer_len >= min_length:
                        await log_info("quality_check", f"允许简短但有意义的回答: 问题='{question}', 答案='{answer}', 长度={answer_len}")
                    else:
                        return {
                            "is_valid": False,
                            "reason": f"答案过短，少于{min_length}个字符",
                            "score": 0.0
                        }
                else:
                    # 对于复杂问题，如果答案太短则可能质量不高
                    if answer_len < 3:  # 少于3个字符的答案通常质量不高
                        return {
                            "is_valid": False,
                            "reason": f"答案过短，少于3个字符",
                            "score": 0.0
                        }
                    else:
                        # 3-9个字符的答案，通过LLM进一步判断
                        await log_info("quality_check", f"短答案通过LLM判断: 问题='{question}', 答案='{answer}', 长度={answer_len}")
            
            # 优化后的重复内容检查：排除格式符号
            if self._has_excessive_repetition(answer, config["max_repetition_ratio"]):
                # 再次检查，排除格式符号后的重复率
                if not self._has_excessive_repetition_without_formatting(answer, config["max_repetition_ratio"]):
                    await log_info("quality_check", f"格式符号导致的重复检测，允许通过: 问题='{question[:30]}...', 答案='{answer[:50]}...'")
                else:
                    return {
                        "is_valid": False,
                        "reason": f"答案包含过多重复内容，超过{config['max_repetition_ratio']*100}%",
                        "score": 0.0
                    }
            
            # 使用LLM进行综合质量评估
            quality_score = await self._llm_quality_check(question, answer)
            
            if quality_score < config["min_llm_score"]:
                return {
                    "is_valid": False,
                    "reason": f"LLM质量评估分数过低，低于{config['min_llm_score']}",
                    "score": quality_score
                }
            
            return {
                "is_valid": True,
                "reason": "答案质量良好",
                "score": quality_score
            }
            
        except Exception as e:
            await log_error("quality_check", f"答案质量检测失败: {e}")
            return {
                "is_valid": True,  # 出错时默认通过
                "reason": f"质量检测异常: {e}",
                "score": 0.5
            }
    
    def _is_simple_question(self, question: str) -> bool:
        """判断是否为简单问题，允许简短回答"""
        simple_patterns = [
            # 年龄相关
            "你多大了", "你几岁了", "多大", "几岁", "年龄", "how old",
            # 身份相关
            "你叫什么", "你是谁", "叫什么", "是谁", "什么名字", "what's your name", "who are you",
            # 问候相关
            "你好", "再见", "hello", "hi", "bye",
            # 状态相关
            "怎么样", "如何", "如何", "how", "what",
            # 习惯相关
            "每天", "习惯", "喜欢", "爱好", "经常"
        ]
        
        question_lower = question.lower().strip()
        return any(pattern in question_lower for pattern in simple_patterns)
    
    def _is_meaningful_answer(self, answer: str) -> bool:
        """判断答案是否有意义，即使很短"""
        # 检查是否包含有意义的词汇
        meaningful_words = [
            "好", "棒", "不错", "可以", "喜欢", "习惯", "经常", "每天", "总是",
            "岁", "年", "名字", "叫", "是", "有", "会", "能", "可以",
            "good", "great", "nice", "like", "love", "yes", "no", "ok"
        ]
        
        answer_lower = answer.lower().strip()
        return any(word in answer_lower for word in meaningful_words)
    
    def _has_excessive_repetition_without_formatting(self, text: str, max_ratio: float = 0.3) -> bool:
        """检查重复内容，排除格式符号"""
        import re
        
        # 移除常见的格式符号
        text_clean = re.sub(r'[*_\-=+#@$%^&|~`]', '', text)
        text_clean = re.sub(r'\s+', ' ', text_clean)  # 合并多个空格
        
        words = text_clean.split()
        if len(words) < 10:
            return False
        
        # 检查是否有超过指定比例的重复词汇
        word_count = {}
        for word in words:
            if len(word) > 1:  # 忽略单字符
                word_count[word] = word_count.get(word, 0) + 1
        
        if not word_count:
            return False
            
        max_repeat = max(word_count.values())
        return max_repeat > len(words) * max_ratio

    def _has_excessive_repetition(self, text: str, max_ratio: float = 0.3) -> bool:
        """检查是否包含过多重复内容"""
        words = text.split()
        if len(words) < 10:
            return False
        
        # 检查是否有超过指定比例的重复词汇
        word_count = {}
        for word in words:
            word_count[word] = word_count.get(word, 0) + 1
        
        max_repeat = max(word_count.values())
        return max_repeat > len(words) * max_ratio
    
    def _is_only_interjections(self, text: str, max_ratio: float = 0.7) -> bool:
        """检查是否只包含语气助词"""
        # 更严格的语气助词定义，排除有意义的词汇
        interjections = {
            "嗯", "啊", "哦", "额", "呃", "呀", "吧", "呢", "吗", "嘛",
            "哈哈", "呵呵", "嘿嘿", "嘻嘻", "嗯嗯", "啊啊", "哦哦",
            "嗯嗯嗯", "啊啊啊", "哦哦哦", "额额", "呃呃"
        }
        
        words = text.strip().split()
        
        # 对于3个词以上的情况，按比例判断
        interjection_count = sum(1 for word in words if word in interjections)
        
        # 额外检查：如果文本主要由重复的单个字符组成，也认为是语气助词
        if len(words) > 5:  # 只对较长的文本进行此检查
            # 检查是否主要由重复的单个字符组成
            char_counts = {}
            for word in words:
                if len(word) == 1:  # 单字符词
                    char_counts[word] = char_counts.get(word, 0) + 1
            
            if char_counts:
                max_char_count = max(char_counts.values())
                # 如果超过70%的词都是同一个单字符，认为是语气助词
                if max_char_count > len(words) * max_ratio:
                    return True
        
        # 特殊检查：如果文本是连续重复的单个字符（如"嗯嗯嗯嗯嗯嗯"），也认为是语气助词
        if len(text.strip()) > 3:  # 只对较长的文本进行此检查
            # 检查是否主要由同一个字符重复组成
            char_freq = {}
            for char in text.strip():
                if char not in [' ', '\t', '\n']:  # 排除空白字符
                    char_freq[char] = char_freq.get(char, 0) + 1
            
            if char_freq:
                max_char_freq = max(char_freq.values())
                total_chars = sum(char_freq.values())
                # 如果超过70%的字符都是同一个字符，认为是语气助词
                if max_char_freq > total_chars * max_ratio:
                    return True
        
        # 如果连续重复字符检测没有触发，则使用词汇检测
        return interjection_count > len(words) * max_ratio
    
    async def _check_relevance(self, question: str, answer: str) -> float:
        """检查答案与问题的相关性"""
        try:
            # 改进的相关性检查，支持中文文本
            def extract_keywords(text):
                """提取关键词，支持中英文"""
                import re
                # 移除标点符号，转换为小写
                text = re.sub(r'[^\w\s]', ' ', text.lower())
                # 分词（支持中英文）
                words = []
                for word in text.split():
                    if len(word) > 1:  # 过滤单字符
                        words.append(word)
                return set(words)
            
            question_words = extract_keywords(question)
            answer_words = extract_keywords(answer)
            
            if not question_words:
                return 0.5
            
            # 计算词汇重叠度
            overlap = len(question_words.intersection(answer_words))
            relevance = overlap / len(question_words)
            
            # 如果重叠度很低，尝试字符级别的相似度
            if relevance < 0.1:
                # 计算字符级别的相似度
                question_chars = set(question.lower())
                answer_chars = set(answer.lower())
                char_overlap = len(question_chars.intersection(answer_chars))
                char_relevance = char_overlap / max(len(question_chars), 1)
                # 字符相似度权重较低
                relevance = max(relevance, char_relevance * 0.3)
            
            return min(relevance * 2, 1.0)  # 放大相关性分数
            
        except Exception as e:
            await log_error("relevance_check", f"相关性检查失败: {e}")
            return 0.5
    
    async def _llm_quality_check(self, question: str, answer: str) -> float:
        """使用LLM进行答案质量评估"""
        try:
            from prompts.fact_extraction import ANSWER_QUALITY_EVALUATION_PROMPT
            user_prompt = ANSWER_QUALITY_EVALUATION_PROMPT.format(
                question=question,
                answer=answer
            )
            
            result = await self.llm_service.call_llm_async(
                "你是一个专业的答案质量评估助手。",
                user_prompt
            )
            
            # 尝试提取数字
            import re
            numbers = re.findall(r'0\.\d+|1\.0|1', result)
            if numbers:
                return float(numbers[0])
            else:
                return 0.5  # 默认分数
                
        except Exception as e:
            await log_error("llm_quality_check", f"LLM质量检查失败: {e}")
            return 0.5
    
    async def search_memory_async(self, user_id: str, agent_id: Optional[str], 
                                 query: str, limit: int = 10) -> Dict:
        """异步搜索记忆"""
        start_time = time.time()
        
        try:
            await log_info("search", f"🔍 开始搜索记忆: user_id={user_id}, query={query[:50]}...")
            
            # 并行执行：Redis事实搜索、ES对话搜索、最近对话获取
            tasks = [
                self._search_facts_async(user_id, query, agent_id, limit),
                self._search_chats_async(user_id, query, agent_id, limit),
                self._get_recent_chats_async(user_id, agent_id, limit=Config.get_search_strategies()["recent_chats_limit"])  # 获取最近对话
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            facts_result = results[0] if not isinstance(results[0], Exception) else {"success": False, "facts": []}
            chats_result = results[1] if not isinstance(results[1], Exception) else {"success": False, "chats": []}
            recent_chats_result = results[2] if not isinstance(results[2], Exception) else {"success": False, "chats": []}
            
            # 合并结果
            relevant_facts = facts_result.get("facts", []) if facts_result.get("success") else []
            similar_chats = chats_result.get("chats", []) if chats_result.get("success") else []
            recent_chats = recent_chats_result.get("chats", []) if recent_chats_result.get("success") else []
            
            total_time = time.time() - start_time
            
            await log_info("search", f"搜索完成: {len(relevant_facts)}个事实, {len(similar_chats)}个相似对话, {len(recent_chats)}个最近对话, 耗时: {total_time:.3f}秒")
            
            return {
                "success": True,
                # "facts": relevant_facts,
                # "chats": similar_chats,
                # "recent_chats": recent_chats,
                "search_results": {
                    "relevant_facts": relevant_facts,
                    "similar_chats": similar_chats,
                    "recent_chats": recent_chats
                },
                "processing_time": total_time
            }
            
        except Exception as e:
            total_time = time.time() - start_time
            await log_error("search", f"搜索失败: {e}, 耗时: {total_time:.3f}秒")
            
            return {
                "success": False,
                "error": str(e),
                "processing_time": total_time
            }
    
    async def _search_facts_async(self, user_id: str, query: str, 
                                 agent_id: Optional[str], limit: int) -> Dict:
        """异步搜索事实"""
        try:
            facts = await self.redis_service.search_facts(user_id, query, agent_id)
            
            # 转换为字典格式 - 统一使用简化格式
            facts_dict = []
            for fact in facts[:limit]:
                fact_dict = fact.to_simple_dict()
                facts_dict.append(fact_dict)
            
            return {
                "success": True,
                "facts": facts_dict
            }
            
        except Exception as e:
            await log_error("search_facts", f"事实搜索失败: {e}")
            return {"success": False, "facts": []}
    
    async def _search_chats_async(self, user_id: str, query: str, 
                                 agent_id: Optional[str], limit: int) -> Dict:
        """异步搜索对话 - 带超时处理"""
        try:
            # 获取查询的embedding
            query_embedding = await self.async_get_embedding(query)
            
            # 设置ES查询超时时间（秒）
            es_timeout = Config.get_search_strategies().get("es_search_timeout", 2)

            # # 根据查询复杂度动态调整超时时间
            # if len(query) > 1000:  # 长查询需要更多时间
            #     es_timeout = min(es_timeout * 1.5, 30)
            # elif len(query) < 50:   # 短查询可以更快超时
            #     es_timeout = max(es_timeout * 0.7, 10)
            
            if not query_embedding:
                # 如果没有embedding，使用纯关键词搜索
                similar_chats = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, 
                        self.es_service.search_similar_chats_by_question_only,
                        user_id, query, limit
                    ),
                    timeout=es_timeout
                )
            else:
                # 使用混合搜索（关键词 + 向量相似度）
                similar_chats = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        self.es_service.search_similar_chats,
                        user_id, query, query_embedding, agent_id, limit
                    ),
                    timeout=es_timeout
                )
            
            # 格式化结果
            chats_formatted = []
            for chat in similar_chats:
                chats_formatted.append({
                    "question": chat["question"],
                    "answer": chat["answer"],
                    "timestamp": chat["timestamp"],
                    "agent_id": chat.get("agent_id"),
                    "_score": chat.get("_score", 0.0)  # 包含相关性分数
                })
            
            return {
                "success": True,
                "chats": chats_formatted
            }
            
        except asyncio.TimeoutError:
            await log_warning("search_chats", f"ES查询超时 ({es_timeout}秒)，返回空结果")
            return {"success": False, "chats": [], "error": "ES查询超时"}
        except Exception as e:
            await log_error("search_chats", f"对话搜索失败: {e}")
            return {"success": False, "chats": [], "error": str(e)}
    
    async def _get_recent_chats_async(self, user_id: str, agent_id: Optional[str], 
                                    limit: int = 20) -> Dict:
        """获取最近N轮对话 - 带超时处理"""
        try:
            await log_info("recent_chats", f"获取最近{limit}轮对话: user_id={user_id}")
            
            # 设置ES查询超时时间（秒）
            es_timeout = Config.get_search_strategies().get("es_search_timeout", 10)
            
            # 从ES获取最近对话
            recent_chats = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    self.es_service.get_recent_chats,
                    user_id, agent_id, limit
                ),
                timeout=es_timeout
            )
            
            # 格式化结果
            chats_formatted = []
            for chat in recent_chats:
                chats_formatted.append({
                    "question": chat["question"],
                    "answer": chat["answer"],
                    "timestamp": chat["timestamp"],
                    "chat_id": chat.get("chat_id", ""),
                    # "topics": chat.get("topics", [])
                })
            
            await log_info("recent_chats", f"获取到{len(chats_formatted)}个最近对话")
            
            return {
                "success": True,
                "chats": chats_formatted
            }
            
        except asyncio.TimeoutError:
            await log_warning("recent_chats", f"ES查询超时 ({es_timeout}秒)，返回空结果")
            return {"success": False, "chats": [], "error": "ES查询超时"}
        except Exception as e:
            await log_error("recent_chats", f"获取最近对话失败: {e}")
            return {"success": False, "chats": [], "error": str(e)}
    
    async def cleanup_dirty_data_async(self, user_id: str = None, agent_id: str = None, 
                                      test_limit: int = 100, dry_run: bool = False) -> Dict:
        """清理ES中的脏数据 - 支持按用户ID或代理ID过滤"""
        try:
            mode = "预览模式" if dry_run else "删除模式"
            filter_info = ""
            if user_id:
                filter_info = f"用户ID: {user_id}"
            elif agent_id:
                filter_info = f"代理ID: {agent_id}"
            else:
                filter_info = "全部数据"
            
            await log_info("cleanup", f"🧹 开始清理脏数据 ({mode}，{filter_info}，限制{test_limit}条)")
            
            # 获取对话记录，支持按用户ID或代理ID过滤
            if user_id or agent_id:
                all_chats = await self._get_chats_by_filter(user_id, agent_id, test_limit)
            else:
                all_chats = self.es_service.get_all_chats()[:test_limit]
            
            dirty_chats = []
            
            await log_info("cleanup", f"开始检查{len(all_chats)}条记录...")
            
            for i, chat in enumerate(all_chats):
                question = chat.get("question", "")
                answer = chat.get("answer", "")
                chat_id = chat.get("chat_id", "")
                chat_user_id = chat.get("user_id", "")
                chat_agent_id = chat.get("agent_id", "")
                
                # 检查是否为脏数据
                quality_check = await self._check_answer_quality(question, answer)
                if not quality_check["is_valid"]:
                    dirty_chat_info = {
                        "chat_id": chat_id,
                        "user_id": chat_user_id,
                        "agent_id": chat_agent_id,
                        "question": question,
                        "answer": answer,
                        "reason": quality_check["reason"],
                        "score": quality_check.get("score", 0.0)
                    }
                    dirty_chats.append(dirty_chat_info)
                    
                    # 打印要删除的脏数据详细信息
                    await log_info("cleanup", f"发现脏数据 [{i+1}/{len(all_chats)}] - chat_id: {chat_id}")
                    await log_info("cleanup", f"  用户ID: {chat_user_id}, 代理ID: {chat_agent_id}")
                    await log_info("cleanup", f"  问题: {question}")
                    await log_info("cleanup", f"  答案: {answer}")
                    await log_info("cleanup", f"  原因: {quality_check['reason']}")
                    await log_info("cleanup", f"  分数: {quality_check.get('score', 0.0)}")
                    await log_info("cleanup", f"  {'='*50}")
            
            await log_info("cleanup", f"检查完成: 检查了{len(all_chats)}条记录，发现{len(dirty_chats)}条脏数据")
            
            cleaned_count = 0
            
            if dry_run:
                # 预览模式：只打印，不删除
                await log_info("cleanup", f"预览模式：发现{len(dirty_chats)}条脏数据，但不会实际删除")
                for i, dirty_chat in enumerate(dirty_chats):
                    await log_info("cleanup", f"预览删除 [{i+1}/{len(dirty_chats)}]: chat_id={dirty_chat['chat_id']}, 原因: {dirty_chat['reason']}")
            else:
                # 删除模式：实际删除脏数据
                if len(dirty_chats) > 0:
                    await log_info("cleanup", f"开始删除{len(dirty_chats)}条脏数据...")
                    
                    for i, dirty_chat in enumerate(dirty_chats):
                        try:
                            chat_id = dirty_chat["chat_id"]
                            if not chat_id or chat_id.strip() == "":
                                await log_warning("cleanup", f"跳过空chat_id的脏数据: {dirty_chat['reason']}")
                                continue
                                
                            success = self.es_service.delete_chat(chat_id)
                            if success:
                                cleaned_count += 1
                                await log_info("cleanup", f"成功删除脏数据 [{i+1}/{len(dirty_chats)}]: chat_id={chat_id}, 原因: {dirty_chat['reason']}")
                            else:
                                await log_warning("cleanup", f"删除脏数据失败: chat_id={chat_id}")
                        except Exception as e:
                            await log_error("cleanup", f"删除脏数据异常: chat_id={dirty_chat.get('chat_id', 'unknown')}, 错误: {e}")
            
            await log_info("cleanup", f"清理完成: 检查了{len(all_chats)}条记录，发现{len(dirty_chats)}条脏数据，{'预览' if dry_run else '实际清理'}{cleaned_count}条")
            
            return {
                "success": True,
                "cleaned_count": cleaned_count,
                "total_checked": len(all_chats),
                "dirty_found": len(dirty_chats),
                "dry_run": dry_run,
                "filter": filter_info,
                "dirty_chats": dirty_chats[:10]  # 只返回前10条作为示例
            }
            
        except Exception as e:
            await log_error("cleanup", f"脏数据清理失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "cleaned_count": 0
            }
    
    async def _get_chats_by_filter(self, user_id: str = None, agent_id: str = None, limit: int = 100) -> List[Dict]:
        """根据用户ID或代理ID获取对话记录"""
        try:
            # 构建查询条件
            must_conditions = []
            if user_id:
                must_conditions.append({"term": {"user_id": user_id}})
            if agent_id:
                must_conditions.append({"term": {"agent_id": agent_id}})
            
            if not must_conditions:
                return self.es_service.get_all_chats()[:limit]
            
            query = {
                "query": {
                    "bool": {
                        "must": must_conditions
                    }
                },
                "size": limit,
                "sort": [{"timestamp": {"order": "desc"}}]
            }
            
            response = self.es_service.es.search(
                index=Config.get_es_chat_index(),
                body=query
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                results.append({
                    "question": source.get("question", ""),
                    "answer": source.get("answer", ""),
                    "chat_id": hit["_id"],
                    "user_id": source.get("user_id", ""),
                    "agent_id": source.get("agent_id", ""),
                    "timestamp": source.get("timestamp", "")
                })
            
            await log_info("cleanup", f"按条件查询到{len(results)}条对话记录")
            return results
            
        except Exception as e:
            await log_error("cleanup", f"按条件查询对话记录失败: {e}")
            return []
    
    async def clear_all_data_async(self, user_id: str = None, agent_id: str = None, dry_run: bool = True) -> Dict:
        """清空ES中的所有数据 - 支持按用户ID或代理ID过滤"""
        try:
            mode = "预览模式" if dry_run else "删除模式"
            filter_info = ""
            if user_id:
                filter_info = f"用户ID: {user_id}"
            elif agent_id:
                filter_info = f"代理ID: {agent_id}"
            else:
                filter_info = "全部数据"
            
            await log_info("clear", f"🗑️ 开始清空ES数据 ({mode}，{filter_info})")
            
            # 获取要清空的数据
            if user_id or agent_id:
                all_chats = await self._get_chats_by_filter(user_id, agent_id, limit=10000)  # 设置较大的限制
            else:
                all_chats = self.es_service.get_all_chats()
            
            await log_info("clear", f"找到{len(all_chats)}条记录待清空")
            
            if dry_run:
                # 预览模式：只打印，不删除
                await log_info("clear", f"预览模式：将清空{len(all_chats)}条记录，但不会实际删除")
                
                # 按用户ID和代理ID分组显示
                user_stats = {}
                agent_stats = {}
                
                for chat in all_chats:
                    chat_user_id = chat.get("user_id", "unknown")
                    chat_agent_id = chat.get("agent_id", "unknown")
                    
                    user_stats[chat_user_id] = user_stats.get(chat_user_id, 0) + 1
                    if chat_agent_id != "unknown":
                        agent_stats[chat_agent_id] = agent_stats.get(chat_agent_id, 0) + 1
                
                await log_info("clear", f"用户统计: {dict(list(user_stats.items())[:10])}")  # 只显示前10个
                await log_info("clear", f"代理统计: {dict(list(agent_stats.items())[:10])}")  # 只显示前10个
                
                # 显示前5条记录的详细信息
                for i, chat in enumerate(all_chats[:5]):
                    await log_info("clear", f"预览清空 [{i+1}/5] - chat_id: {chat.get('chat_id', '')}")
                    await log_info("clear", f"  用户ID: {chat.get('user_id', '')}, 代理ID: {chat.get('agent_id', '')}")
                    await log_info("clear", f"  问题: {chat.get('question', '')[:50]}...")
                    await log_info("clear", f"  答案: {chat.get('answer', '')[:50]}...")
                
                if len(all_chats) > 5:
                    await log_info("clear", f"  ... 还有{len(all_chats) - 5}条记录")
                
                cleared_count = 0
            else:
                # 删除模式：实际删除数据
                cleared_count = 0
                total_count = len(all_chats)
                
                await log_info("clear", f"开始删除{total_count}条记录...")
                
                for i, chat in enumerate(all_chats):
                    try:
                        chat_id = chat.get("chat_id", "")
                        if not chat_id or chat_id.strip() == "":
                            await log_warning("clear", f"跳过空chat_id的记录")
                            continue
                        
                        success = self.es_service.delete_chat(chat_id)
                        if success:
                            cleared_count += 1
                            if cleared_count % 100 == 0:  # 每100条记录打印一次进度
                                await log_info("clear", f"已删除{cleared_count}/{total_count}条记录")
                        else:
                            await log_warning("clear", f"删除记录失败: chat_id={chat_id}")
                    except Exception as e:
                        await log_error("clear", f"删除记录异常: chat_id={chat.get('chat_id', 'unknown')}, 错误: {e}")
            
            await log_info("clear", f"清空完成: {'预览' if dry_run else '实际清空'}{cleared_count}条记录")
            
            return {
                "success": True,
                "cleared_count": cleared_count,
                "total_found": len(all_chats),
                "dry_run": dry_run,
                "filter": filter_info
            }
            
        except Exception as e:
            await log_error("clear", f"清空ES数据失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "cleared_count": 0
            }
    
    async def query_facts_async(self, user_id: str, agent_id: Optional[str] = None, 
                               limit: int = 50, offset: int = 0) -> Dict:
        """查询事实"""
        try:
            facts = await self.redis_service.get_facts(user_id, agent_id)
            
            # 分页处理
            total_facts = len(facts)
            paginated_facts = facts[offset:offset + limit]
            
            # 转换为字典格式
            facts_dict = []
            for fact in paginated_facts:
                fact_dict = fact.to_dict()
                facts_dict.append(fact_dict)
            
            return {
                "success": True,
                "facts": facts_dict,
                "summary": {
                    "total_facts": total_facts,
                    "returned_facts": len(facts_dict),
                    "offset": offset,
                    "limit": limit
                }
            }
            
        except Exception as e:
            await log_error("query_facts", f"查询事实失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "facts": []
            }
    
    async def add_or_update_memory_async(self, user_id: str, topic: str, sub_topic: str, 
                                        memo: str, agent_id: Optional[str] = None, 
                                        chat_id: Optional[str] = None) -> Dict:
        """添加或更新记忆 - 支持指定主题和小主题"""
        try:
            await log_info("memory_management", f"🔄 开始添加或更新记忆: user_id={user_id}, topic={topic}, sub_topic={sub_topic}")
            
            # 构建事实键
            fact_key = f"{topic}:{sub_topic}"
            
            # 检查是否已存在该事实
            facts = await self.redis_service.get_facts(user_id, agent_id)
            existing_fact = None
            
            for fact in facts:
                if fact.topic == topic and fact.sub_topic == sub_topic:
                    existing_fact = fact
                    break
            
            if existing_fact:
                # 更新现有事实
                await log_info("memory_management", f"📝 更新现有记忆: {fact_key}")
                update_data = {
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "memo": memo,
                    "updated_at": datetime.now().isoformat(),
                    "chat_id": chat_id or existing_fact.chat_id  # 保持原有chat_id或使用新的
                }
                
                success = await self.redis_service.update_fact(fact_key, update_data)
                if not success:
                    raise Exception("更新记忆失败")
                
                return {
                    "success": True,
                    "action": "update",
                    "message": "记忆更新成功",
                    "fact": {
                        "topic": topic,
                        "sub_topic": sub_topic,
                        "memo": memo,
                        "created_at": existing_fact.created_at.isoformat(),
                        "updated_at": update_data["updated_at"],
                        "chat_id": update_data["chat_id"]
                    }
                }
            else:
                # 添加新事实
                await log_info("memory_management", f"➕ 添加新记忆: {fact_key}")
                current_time = datetime.now()
                new_fact = FactDocument(
                    user_id=user_id,
                    agent_id=agent_id,
                    topic=topic,
                    sub_topic=sub_topic,
                    memo=memo,
                    created_at=current_time,
                    updated_at=current_time,
                    chat_id=chat_id
                )
                
                success = await self.redis_service.add_fact(new_fact)
                if not success:
                    raise Exception("添加记忆失败")
                
                return {
                    "success": True,
                    "action": "add",
                    "message": "记忆添加成功",
                    "fact": {
                        "topic": topic,
                        "sub_topic": sub_topic,
                        "memo": memo,
                        "created_at": current_time.isoformat(),
                        "updated_at": current_time.isoformat(),
                        "chat_id": chat_id
                    }
                }
                
        except Exception as e:
            await log_error("memory_management", f"添加或更新记忆失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "添加或更新记忆失败"
            }
    
    async def update_fact_async(self, user_id: str, topic: str, sub_topic: str, 
                               new_memo: str, agent_id: Optional[str] = None) -> Dict:
        """更新事实 - 只能修改指定用户/agent的事实"""
        try:
            # 构建事实键
            fact_key = f"{topic}:{sub_topic}"
            
            # 先验证该事实确实属于该用户
            facts = await self.redis_service.get_facts(user_id, agent_id)
            fact_to_update = None
            
            for fact in facts:
                if fact.topic == topic and fact.sub_topic == sub_topic:
                    fact_to_update = fact
                    break
            
            if not fact_to_update:
                return {
                    "success": False,
                    "error": "未找到要更新的事实",
                    "message": f"未找到主题为'{topic}'，子主题为'{sub_topic}'的事实，或该事实不属于用户'{user_id}'"
                }
            
            # 验证权限：确保事实确实属于该用户和agent
            if fact_to_update.user_id != user_id:
                return {
                    "success": False,
                    "error": "权限不足",
                    "message": "只能修改自己的事实"
                }
            
            if fact_to_update.agent_id != agent_id:
                return {
                    "success": False,
                    "error": "权限不足", 
                    "message": "只能修改指定agent的事实"
                }
            
            # 使用新的update_fact方法更新事实
            update_data = {
                "user_id": user_id,
                "agent_id": agent_id,
                "memo": new_memo,
                "timestamp": datetime.now().isoformat(),
                "chat_id": fact_to_update.chat_id  # 保持原有的chat_id
            }
            
            success = await self.redis_service.update_fact(fact_key, update_data)
            if not success:
                raise Exception("更新事实失败")
            
            return {
                "success": True,
                "message": "事实更新成功",
                "updated_fact": {
                    "topic": topic,
                    "sub_topic": sub_topic,
                    "memo": new_memo,
                    "chat_id": fact_to_update.chat_id,
                    "timestamp": update_data["timestamp"]
                }
            }
            
        except Exception as e:
            await log_error("update_fact", f"更新事实失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "事实更新失败"
            }
    
    async def get_performance_stats(self) -> Dict:
        """获取性能统计"""
        return {
            "stats": self.stats,
            "cache_stats": await self.cache_service.get_stats()
        }
    
    async def clear_cache(self):
        """清理当前项目的所有缓存数据 - 使用统一缓存服务"""
        try:
            # 使用统一缓存服务清理所有项目缓存
            deleted_count = await self.cache_service.clear_all_project_cache()
            
            # 重置统计
            self.stats = {
                "total_requests": 0,
                "cache_hits": 0,
                "cache_misses": 0,
                "avg_response_time": 0.0
            }
            
            await log_info("cache", f"🎉 缓存清理完成: 总计删除{deleted_count}个键")
            
            return {
                "success": True,
                "message": f"已清理项目所有缓存数据",
                "deleted_count": deleted_count
            }
            
        except Exception as e:
            await log_error("cache", f"清理缓存失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "清理缓存失败"
            }
    
    async def _clear_project_cache(self) -> int:
        """清理项目缓存数据 - 使用精确的前缀"""
        try:
            # 获取Redis客户端
            redis_client = self.cache_service.redis_client
            
            # 查找所有 yaxin_memo:cache: 开头的键
            cache_keys = redis_client.keys("yaxin_memo:cache:*")
            
            if cache_keys:
                deleted_count = redis_client.delete(*cache_keys)
                await log_info("cache", f"清理项目缓存: 找到{len(cache_keys)}个键，删除{deleted_count}个")
                return deleted_count
            else:
                await log_info("cache", "未找到项目缓存数据")
                return 0
                
        except Exception as e:
            await log_error("cache", f"清理项目缓存失败: {e}")
            return 0
    
    async def _clear_redis_facts(self) -> int:
        """清理Redis中的事实数据"""
        try:
            # 获取Redis客户端
            redis_client = self.redis_service.redis
            
            # 查找所有facts:开头的键
            fact_keys = redis_client.keys("facts:*")
            
            if fact_keys:
                deleted_count = redis_client.delete(*fact_keys)
                await log_info("cache", f"清理Redis事实数据: 找到{len(fact_keys)}个键，删除{deleted_count}个")
                return deleted_count
            else:
                await log_info("cache", "未找到Redis事实数据")
                return 0
                
        except Exception as e:
            await log_error("cache", f"清理Redis事实数据失败: {e}")
            return 0
    
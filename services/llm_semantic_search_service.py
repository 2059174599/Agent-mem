"""
LLM语义搜索服务 - 参考memobase设计
使用LLM进行智能语义搜索，替换关键词匹配
"""

import asyncio
import aiohttp
import json
from typing import List, Dict, Optional, Any
from datetime import datetime
from models.redis_models import FactDocument
from config import Config
from logging_config import get_logger

logger = get_logger(__name__)

class LLMSemanticSearchService:
    """LLM语义搜索服务类"""
    
    def __init__(self):
        self.session = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def search_relevant_facts(self, facts: List[FactDocument], query: str, 
                                  max_results: int = 10) -> List[FactDocument]:
        """
        使用LLM进行语义搜索，找出与查询最相关的事实
        
        Args:
            facts: 所有用户事实列表
            query: 搜索查询
            max_results: 最大返回结果数
            
        Returns:
            相关的事实列表
        """
        if not facts:
            logger.info("没有事实可供搜索")
            return []
        
        try:
            logger.info(f"开始LLM语义搜索: query='{query}', facts_count={len(facts)}")
            
            # 构建LLM提示词
            system_prompt = self._get_semantic_search_system_prompt()
            user_prompt = self._build_search_prompt(facts, query, max_results)
            
            # 调用LLM
            response = await self._call_llm_async(system_prompt, user_prompt)
            
            if not response:
                logger.warning("LLM调用失败，返回空结果")
                return []
            
            # 解析LLM响应
            relevant_fact_indices = self._parse_llm_response(response)
            
            # 根据索引获取相关事实
            relevant_facts = []
            for idx in relevant_fact_indices:
                if 0 <= idx < len(facts):
                    relevant_facts.append(facts[idx])
            
            logger.info(f"LLM语义搜索完成: 找到 {len(relevant_facts)} 条相关事实")
            
            # 记录搜索结果详情
            for i, fact in enumerate(relevant_facts):
                logger.info(f"相关事实 {i+1}: {fact.topic} - {fact.sub_topic} - {fact.memo[:50]}...")
            
            return relevant_facts
            
        except Exception as e:
            logger.error(f"LLM语义搜索失败: {e}")
            return []
    
    def _get_semantic_search_system_prompt(self) -> str:
        """获取语义搜索系统提示词"""
        return """你是一个专业的记忆搜索助手，负责从用户的事实记忆中找出与查询最相关的内容。

你的任务：
1. 分析用户的查询意图和语义
2. 从提供的事实列表中找出语义相关的事实
3. 理解查询和事实之间的语义关联，而不是简单的关键词匹配
4. 特别关注以下类型的语义关联：
   - 同义词和近义词（如"多大了"和"年龄"）
   - 语义相关概念（如"称呼"和"名字"）
   - 上下文相关（如"你"指代助手）
   - 隐含含义（如询问年龄时，需要年龄相关的设定信息）

重要原则：
- 优先选择语义最相关的事实
- 考虑查询的隐含含义和上下文
- 不要过度依赖关键词匹配
- 理解用户真正想要了解的信息

请严格按照JSON格式返回结果，只返回相关事实的索引列表。"""
    
    def _build_search_prompt(self, facts: List[FactDocument], query: str, max_results: int) -> str:
        """构建搜索提示词"""
        # 构建事实列表
        facts_list = []
        for i, fact in enumerate(facts):
            facts_list.append({
                "index": i,
                "topic": fact.topic,
                "sub_topic": fact.sub_topic,
                "memo": fact.memo,
                "timestamp": fact.timestamp.isoformat()
            })
        
        # 构建查询上下文
        query_context = self._analyze_query_context(query)
        
        prompt = f"""请分析以下查询，从事实列表中找出最相关的事实。

查询: {query}
查询分析: {query_context}

事实列表:
{json.dumps(facts_list, ensure_ascii=False, indent=2)}

请按照以下格式返回JSON：
{{
    "reason": "选择这些事实的原因说明",
    "relevant_indices": [相关事实的索引列表],
    "max_results": {max_results}
}}

规则说明：
1. 只返回最相关的事实索引，最多{max_results}个
2. 按相关性排序，最相关的排在前面
3. 考虑语义关联，不仅仅是关键词匹配
4. 理解查询的隐含含义和上下文

示例分析：
- 查询"你多大了？"应该匹配包含年龄设定的事实
- 查询"你叫什么名字？"应该匹配包含称呼设定的事实
- 查询"怎么称呼你？"应该匹配包含称呼偏好的事实

请确保返回的是有效的JSON格式。"""
        
        return prompt
    
    def _analyze_query_context(self, query: str) -> str:
        """分析查询上下文"""
        query_lower = query.lower().strip()
        
        # 年龄相关查询
        age_queries = ["多大了", "几岁了", "岁数", "年纪", "年龄", "多大岁数", "你几岁", "你多大"]
        if any(age_q in query_lower for age_q in age_queries):
            return "用户询问年龄相关信息，需要查找包含年龄设定、岁数描述的事实"
        
        # 称呼相关查询
        name_queries = ["叫什么", "名字", "称呼", "如何称呼", "叫你什么", "你叫什么"]
        if any(name_q in query_lower for name_q in name_queries):
            return "用户询问称呼相关信息，需要查找包含称呼设定、名字偏好的事实"
        
        # 身份相关查询
        identity_queries = ["你是谁", "你是什么", "你的身份", "介绍自己"]
        if any(identity_q in query_lower for identity_q in identity_queries):
            return "用户询问身份相关信息，需要查找包含身份设定、自我介绍的事实"
        
        # 偏好相关查询
        preference_queries = ["喜欢", "偏好", "习惯", "爱好", "兴趣"]
        if any(pref_q in query_lower for pref_q in preference_queries):
            return "用户询问偏好相关信息，需要查找包含兴趣爱好、个人偏好的事实"
        
        # 个人信息查询
        personal_queries = ["工作", "职业", "住址", "联系方式", "个人信息"]
        if any(personal_q in query_lower for personal_q in personal_queries):
            return "用户询问个人信息，需要查找包含个人背景、职业信息的事实"
        
        return f"通用查询，需要查找与'{query}'语义相关的事实"
    
    async def _call_llm_async(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """异步调用LLM"""
        try:
            payload = {
                "model": Config.get_llm_model(),
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.1  # 低温度确保结果稳定
            }
            
            headers = {
                "Authorization": f"Bearer {Config.get_llm_api_key()}",
                "Content-Type": "application/json"
            }
            
            logger.info(f"调用LLM进行语义搜索: {len(user_prompt)}字符的提示词")
            
            async with self.session.post(
                Config.get_llm_base_url(),
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]
                    logger.info(f"LLM语义搜索响应: {content}")
                    return content
                else:
                    response_text = await response.text()
                    logger.error(f"LLM调用失败，状态码: {response.status}, 响应: {response_text[:200]}")
                    return None
                    
        except Exception as e:
            logger.error(f"LLM调用异常: {e}")
            return None
    
    def _parse_llm_response(self, response: str) -> List[int]:
        """解析LLM响应，提取相关事实索引"""
        try:
            # 尝试解析JSON
            data = json.loads(response)
            
            if isinstance(data, dict) and "relevant_indices" in data:
                indices = data["relevant_indices"]
                if isinstance(indices, list):
                    # 确保索引都是整数
                    valid_indices = []
                    for idx in indices:
                        try:
                            valid_indices.append(int(idx))
                        except (ValueError, TypeError):
                            continue
                    return valid_indices
            
            # 如果格式不正确，尝试从文本中提取数字
            import re
            numbers = re.findall(r'\d+', response)
            return [int(n) for n in numbers if n.isdigit()]
            
        except json.JSONDecodeError as e:
            logger.warning(f"LLM响应不是有效JSON: {e}")
            logger.warning(f"原始响应: {response[:200]}...")
            
            # 尝试从文本中提取数字
            import re
            numbers = re.findall(r'\d+', response)
            return [int(n) for n in numbers if n.isdigit()]
        
        except Exception as e:
            logger.error(f"解析LLM响应失败: {e}")
            return []
    
    async def search_with_fallback(self, facts: List[FactDocument], query: str, 
                                 max_results: int = 10) -> List[FactDocument]:
        """
        带降级策略的搜索
        如果LLM搜索失败，降级到关键词匹配
        """
        try:
            # 首先尝试LLM语义搜索
            relevant_facts = await self.search_relevant_facts(facts, query, max_results)
            
            if relevant_facts:
                logger.info(f"LLM语义搜索成功: 找到 {len(relevant_facts)} 条相关事实")
                return relevant_facts
            else:
                logger.warning("LLM语义搜索未找到结果，尝试关键词匹配降级")
                return self._fallback_keyword_search(facts, query, max_results)
                
        except Exception as e:
            logger.error(f"LLM语义搜索异常，降级到关键词匹配: {e}")
            return self._fallback_keyword_search(facts, query, max_results)
    
    def _fallback_keyword_search(self, facts: List[FactDocument], query: str, 
                               max_results: int) -> List[FactDocument]:
        """关键词匹配降级策略"""
        try:
            query_lower = query.lower()
            relevant_facts = []
            
            # 简单的关键词匹配
            for fact in facts:
                fact_text = f"{fact.topic} {fact.sub_topic} {fact.memo}".lower()
                
                # 检查是否有词汇重叠
                query_words = set(query_lower.split())
                fact_words = set(fact_text.split())
                
                if query_words.intersection(fact_words):
                    relevant_facts.append(fact)
            
            # 按时间排序
            relevant_facts.sort(key=lambda x: x.timestamp, reverse=True)
            
            logger.info(f"关键词匹配降级: 找到 {len(relevant_facts)} 条相关事实")
            return relevant_facts[:max_results]
            
        except Exception as e:
            logger.error(f"关键词匹配降级失败: {e}")
            return []

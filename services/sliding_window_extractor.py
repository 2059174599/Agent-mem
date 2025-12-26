"""
滑动窗口事实提取器 - 替代第一阶段提取，但保持输出格式一致
利用最近N轮对话作为上下文，提高提取准确率
"""

import asyncio
from typing import Dict, List, Optional
from config import Config
from services.async_logging_service import log_info, log_error, log_warning
from prompts.fact_extraction import (
    SLIDING_WINDOW_SYSTEM_PROMPT,
    SLIDING_WINDOW_USER_PROMPT
)


class SlidingWindowExtractor:
    """滑动窗口事实提取器"""
    
    def __init__(self):
        # 使用 fact_extraction_service 的 LLM 调用方法
        from services.fact_extraction_service import fact_extraction_service
        self.fact_service = fact_extraction_service
        
    def _should_extract(self, question: str, answer: str) -> bool:
        """
        简单规则过滤：判断是否值得提取
        保留原有的规则逻辑
        """
        # 规则1：问题和回答都不能为空
        if not question or not answer:
            return False
        
        # 规则2：回答长度至少5个字符
        if len(answer.strip()) < 5:
            return False
        
        # 规则3：过滤客套话（不提取记忆）
        polite_answers = [
            "好的", "谢谢", "知道了", "明白了", "收到", "可以",
            "没问题", "行", "OK", "ok", "好", "嗯", "哦"
        ]
        if answer.strip() in polite_answers:
            return False
        
        return True
    
    async def extract_facts_with_context(
        self, 
        user_id: str, 
        agent_id: Optional[str],
        current_question: str, 
        current_answer: str,
        es_service
    ) -> Dict:
        """
        滑动窗口事实提取（第一阶段）
        
        返回格式与原_extract_conversation_facts一致：
        {
            "contains_facts": true/false,
            "facts": [
                {
                    "topic": "主题",
                    "sub_topic": "子主题",
                    "memo": "内容",
                    "action": "add/update",
                    "confidence": 0.0-1.0
                }
            ]
        }
        """
        try:
            # 简单规则过滤
            if not self._should_extract(current_question, current_answer):
                await log_info("sliding_window", f"未通过简单规则，跳过提取")
                return {
                    "success": True,
                    "contains_facts": False,
                    "facts": [],
                    "reason": "未通过简单规则过滤"
                }
            
            # 获取滑动窗口大小
            window_size = Config.get_sliding_window_size()
            
            # 获取最近N轮对话（从conversation_cache_service）
            from services.conversation_cache_service import conversation_cache_service
            recent_conversations = await conversation_cache_service.get_recent_conversations(
                user_id=user_id,
                agent_id=agent_id,
                limit=window_size,
                es_service=es_service
            )
            
            # 构建对话历史字符串（排除当前对话）
            conversation_history = ""
            if recent_conversations:
                for i, conv in enumerate(recent_conversations, 1):
                    conversation_history += f"{i}. Q: {conv['question']}\n   A: {conv['answer']}\n"
            else:
                conversation_history = "（无对话历史）"
            
            await log_info("sliding_window", f"使用{len(recent_conversations)}轮对话上下文进行提取")
            
            # 获取主题配置
            topics_dict = Config.get_predefined_topics()
            topics_str = "\n".join([f"{topic}: {', '.join(sub_topics)}" for topic, sub_topics in topics_dict.items()])
            
            # 构建提示词
            user_prompt = SLIDING_WINDOW_USER_PROMPT.format(
                window_size=window_size,
                conversation_history=conversation_history,
                current_question=current_question,
                current_answer=current_answer,
                topics=topics_str
            )
            
            # 调用LLM（使用fact_extraction_service的带重试方法）
            result = await self.fact_service._call_llm_with_retry(
                system_prompt=SLIDING_WINDOW_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                retry_count=Config.get_llm_retry_count()
            )
            
            if not result:
                await log_warning("sliding_window", "LLM返回空结果")
                return {
                    "success": True,
                    "contains_facts": False,
                    "facts": [],
                    "reason": "LLM返回空结果"
                }
            
            # 验证返回格式
            contains_facts = result.get("contains_facts", False)
            facts = result.get("facts", [])
            
            if contains_facts and facts:
                await log_info("sliding_window", f"✅ 滑动窗口提取到{len(facts)}个事实")
                if result.get("extraction_notes"):
                    await log_info("sliding_window", f"提取说明: {result['extraction_notes']}")
            else:
                await log_info("sliding_window", f"ℹ️ 滑动窗口未提取到事实")
            
            # 返回与第一阶段相同的格式
            return {
                "success": True,
                "contains_facts": contains_facts,
                "facts": facts
            }
            
        except Exception as e:
            await log_error("sliding_window", f"滑动窗口提取失败: {e}")
            return {
                "success": True,
                "contains_facts": False,
                "facts": [],
                "error": str(e)
            }


# 全局单例
sliding_window_extractor = SlidingWindowExtractor()

"""
事实提取服务 - 实现两阶段事实提取逻辑
1. 第一阶段：提取问答对中的用户事实
2. 第二阶段：与user_facts对比，决定添加或修改
"""

import asyncio
import aiohttp
import json
import random
from typing import Dict, List, Optional, Any
from datetime import datetime
from config import Config
from services.async_logging_service import log_info, log_error, log_warning
from services.unified_cache_service import unified_cache_service
from models.redis_models import RedisService, FactDocument
from prompts.fact_extraction import (
    FACT_EXTRACTION_SYSTEM_PROMPT, 
    FACT_EXTRACTION_USER_PROMPT,
    FACT_MERGE_PROMPT,
    MEMORY_UPDATE_DECISION_PROMPT
)

# 延迟导入压缩服务(避免循环依赖)
_compression_service = None

def get_compression_service():
    global _compression_service
    if _compression_service is None:
        from services.content_compression_service import content_compression_service
        _compression_service = content_compression_service
    return _compression_service

class FactExtractionService:
    """事实提取服务 - 两阶段事实提取"""
    
    def __init__(self):
        self.session = None
        self.cache_service = unified_cache_service
        self.redis_service = RedisService()
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    def _get_cache_key(self, text: str, cache_type: str = "fact") -> str:
        """生成缓存键"""
        return self.cache_service.generate_cache_key(cache_type, text)
    
    def _get_fact_cache_ttl(self) -> int:
        """获取事实缓存的随机TTL（3-7天）"""
        min_ttl = 3 * 24 * 3600  # 3天
        max_ttl = 7 * 24 * 3600  # 7天
        return random.randint(min_ttl, max_ttl)
    
    async def extract_facts_two_stage(self, user_id: str, agent_id: Optional[str], 
                                    question: str, answer: str, chat_id: str = "") -> Dict:
        """两阶段事实提取"""
        try:
            await log_info("fact_extraction", f"🔍 开始两阶段事实提取: user_id={user_id}, question={question[:50]}...")
            
            # 第一阶段：提取问答对中的用户事实
            stage1_result = await self._extract_conversation_facts(question, answer)
            
            if not stage1_result.get("contains_facts", False):
                await log_info("fact_extraction", f"ℹ️ 第一阶段未提取到事实，跳过第二阶段")
                return {
                    "success": True,
                    "stage1_facts": [],
                    "stage2_actions": [],
                    "final_facts": [],
                    "message": "未提取到用户事实"
                }
            
            stage1_facts = stage1_result.get("facts", [])
            await log_info("fact_extraction", f"✅ 第一阶段提取到 {len(stage1_facts)} 个事实, 具体事实: {stage1_facts}")
            
            # 第二阶段：与user_facts对比并决定操作
            stage2_result = await self._compare_and_update_facts(
                user_id, agent_id, stage1_facts, question, answer, chat_id
            )
            
            return {
                "success": True,
                "stage1_facts": stage1_facts,
                "stage2_actions": stage2_result.get("actions", []),
                "final_facts": stage2_result.get("final_facts", []),
                "message": f"两阶段提取完成，第一阶段{len(stage1_facts)}个事实，第二阶段{len(stage2_result.get('actions', []))}个操作"
            }
            
        except Exception as e:
            await log_error("fact_extraction", f"❌ 两阶段事实提取失败: {e}")
            return {
                "success": False,
                "stage1_facts": [],
                "stage2_actions": [],
                "final_facts": [],
                "error": str(e)
            }
    
    async def _extract_conversation_facts(self, question: str, answer: str) -> Dict:
        """第一阶段：从问答对中提取用户事实（优先从问题中提取，必要时从AI回答中提取）"""
        try:
            # 检查缓存 - 只基于问题，不包含答案
            cache_key = self._get_cache_key(question, "fact")
            cached_result = await self.cache_service.get("fact", cache_key)
            
            if cached_result:
                await log_info("fact_extraction", f"第一阶段缓存命中: {question[:30]}...")
                return cached_result
            
            # 只使用用户问题，不包含AI回答
            # AI回答不代表用户的真实观点或事实，只从用户问题中提取事实
            await log_info("fact_extraction", f"🔍 从用户问题中提取事实: {question[:50]}...")
            
            # 获取主题配置
            topics_dict = Config.get_predefined_topics()
            topics_str = "\n".join([f"{topic}: {', '.join(sub_topics)}" for topic, sub_topics in topics_dict.items()])
            
            # 构建用户提示词 - 只传入用户问题
            user_prompt = FACT_EXTRACTION_USER_PROMPT.format(
                question=question,
                topics=topics_str
            )
            
            # 调用LLM
            result = await self._call_llm_with_retry(
                FACT_EXTRACTION_SYSTEM_PROMPT,
                user_prompt,
                Config.get_llm_retry_count()
            )
            
            if result:
                # 缓存结果
                ttl = self._get_fact_cache_ttl()
                await self.cache_service.set("fact", cache_key, result, ttl)
                await log_info("fact_extraction", f"第一阶段结果已缓存: TTL={ttl}秒")
            
            return result
            
        except Exception as e:
            await log_error("fact_extraction", f"第一阶段事实提取失败: {e}")
            return {"contains_facts": False, "facts": []}
    
    async def _compare_and_update_facts(self, user_id: str, agent_id: Optional[str], 
                                      new_facts: List[Dict], question: str, answer: str, chat_id: str = "") -> Dict:
        """第二阶段：与user_facts对比并决定操作"""
        try:
            await log_info("fact_extraction", f"🔄 开始第二阶段：对比现有事实")
            
            # 获取用户现有事实
            existing_facts = await self.redis_service.get_facts(user_id, agent_id)
            await log_info("fact_extraction", f"📋 用户现有事实数量: {len(existing_facts)}")
            
            actions = []
            final_facts = []
            
            for new_fact in new_facts:
                action_result = await self._decide_fact_action(
                    new_fact, existing_facts, question, answer
                )
                
                if action_result["action"] == "add":
                    # 添加新事实 - 集成自动压缩
                    memo = new_fact["memo"]
                    
                    # 检查是否需要压缩
                    if Config.get_compression_enabled():
                        compression_service = get_compression_service()
                        if compression_service.should_compress(new_fact["topic"], memo):
                            await log_info("fact_extraction", f"🗜️ 内容过长，自动压缩: {len(memo)}字符")
                            compress_result = await compression_service.compress_content(
                                new_fact["topic"], 
                                new_fact["sub_topic"], 
                                memo
                            )
                            memo = compress_result["compressed"]
                            await log_info("fact_extraction", 
                                f"✅ 压缩完成: {compress_result['original_length']}→{compress_result['compressed_length']}字符")
                    
                    fact_doc = FactDocument(
                        user_id=user_id,
                        agent_id=agent_id,
                        topic=new_fact["topic"],
                        sub_topic=new_fact["sub_topic"],
                        memo=memo,  # 使用压缩后的内容
                        chat_id=chat_id,
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    
                    success = await self.redis_service.add_fact(fact_doc)
                    if success:
                        actions.append({
                            "action": "add",
                            "fact": new_fact,
                            "success": True
                        })
                        final_facts.append(new_fact)
                        await log_info("fact_extraction", f"✅ 添加新事实: {new_fact['topic']} - {new_fact['sub_topic']}")
                    else:
                        actions.append({
                            "action": "add",
                            "fact": new_fact,
                            "success": False,
                            "error": "Redis存储失败"
                        })
                        await log_error("fact_extraction", f"❌ 添加事实失败: {new_fact['topic']} - {new_fact['sub_topic']}")
                
                elif action_result["action"] == "update":
                    # 更新或合并现有事实 - 集成自动压缩
                    existing_fact = action_result["existing_fact"]
                    updated_memo = action_result["updated_memo"]
                    
                    # 检查是否需要压缩
                    if Config.get_compression_enabled():
                        compression_service = get_compression_service()
                        if compression_service.should_compress(new_fact["topic"], updated_memo):
                            await log_info("fact_extraction", f"🗜️ 合并后内容过长，自动压缩: {len(updated_memo)}字符")
                            compress_result = await compression_service.compress_content(
                                new_fact["topic"], 
                                new_fact["sub_topic"], 
                                updated_memo
                            )
                            updated_memo = compress_result["compressed"]
                            await log_info("fact_extraction", 
                                f"✅ 压缩完成: {compress_result['original_length']}→{compress_result['compressed_length']}字符")
                    
                    # 更新Redis中的事实
                    success = await self.redis_service.update_fact(
                        existing_fact.fact_key, 
                        {
                            "user_id": user_id,
                            "agent_id": agent_id,
                            "memo": updated_memo, 
                            "timestamp": datetime.now().isoformat()
                        }
                    )
                    
                    if success:
                        actions.append({
                            "action": "update",
                            "old_fact": {
                                "topic": existing_fact.topic,
                                "sub_topic": existing_fact.sub_topic,
                                "memo": existing_fact.memo
                            },
                            "new_fact": {
                                "topic": new_fact["topic"],
                                "sub_topic": new_fact["sub_topic"],
                                "memo": updated_memo
                            },
                            "success": True
                        })
                        final_facts.append({
                            "topic": new_fact["topic"],
                            "sub_topic": new_fact["sub_topic"],
                            "memo": updated_memo
                        })
                        await log_info("fact_extraction", f"✅ 更新事实: {new_fact['topic']} - {new_fact['sub_topic']}")
                    else:
                        actions.append({
                            "action": "update",
                            "old_fact": {
                                "topic": existing_fact.topic,
                                "sub_topic": existing_fact.sub_topic,
                                "memo": existing_fact.memo
                            },
                            "new_fact": new_fact,
                            "success": False,
                            "error": "Redis更新失败"
                        })
                        await log_error("fact_extraction", f"❌ 更新事实失败: {new_fact['topic']} - {new_fact['sub_topic']}")
                
                elif action_result["action"] == "skip":
                    await log_info("fact_extraction", f"⏭️ 跳过事实: {new_fact['topic']} - {new_fact['sub_topic']} (原因: {action_result.get('reason', '未知')})")
                    actions.append({
                        "action": "skip",
                        "fact": new_fact,
                        "reason": action_result.get("reason", "未知")
                    })
            
            return {
                "actions": actions,
                "final_facts": final_facts
            }
            
        except Exception as e:
            await log_error("fact_extraction", f"第二阶段事实对比失败: {e}")
            return {"actions": [], "final_facts": []}
    
    async def _decide_fact_action(self, new_fact: Dict, existing_facts: List[FactDocument], 
                                 question: str, answer: str) -> Dict:
        """决定事实操作：添加、更新或跳过"""
        try:
            # 查找相同主题和子主题的现有事实
            matching_facts = [
                fact for fact in existing_facts
                if fact.topic == new_fact["topic"] and fact.sub_topic == new_fact["sub_topic"]
            ]
            
            if not matching_facts:
                # 没有匹配的事实，直接添加
                await log_info("fact_extraction", f"没有找到匹配的事实，直接添加: {new_fact['topic']} - {new_fact['sub_topic']}")
                return {"action": "add"}
            
            # 有匹配的事实，需要判断是否需要更新或合并
            existing_fact = matching_facts[0]  # 取第一个匹配的事实
            
            # 先进行简单的冲突检测
            conflict_result = await self._detect_conflict(new_fact, existing_fact)
            if conflict_result["is_conflict"]:
                await log_info("fact_extraction", f"检测到冲突，需要替换: {new_fact['topic']} - {new_fact['sub_topic']}")
                return {
                    "action": "update",
                    "existing_fact": existing_fact,
                    "updated_memo": new_fact["memo"],
                    "reason": conflict_result["reason"]
                }
            
            # 使用LLM判断是否需要合并
            decision_result = await self._llm_decide_update(
                new_fact, existing_fact, question, answer
            )
            await log_info("fact_extraction", f"llm 判断事实结果: {decision_result} 新旧事实: {new_fact} - {existing_fact}")
            
            # 优先检查update_type，如果明确指定了操作类型，则执行对应操作
            update_type = decision_result.get("update_type")
            if update_type == "merge":
                # 合并事实
                merged_memo = await self._merge_facts(existing_fact.memo, new_fact["memo"])
                await log_info("fact_extraction", f"合并事实: {existing_fact.memo} + {new_fact['memo']} = {merged_memo}")
                return {
                    "action": "update",
                    "existing_fact": existing_fact,
                    "updated_memo": merged_memo,
                    "reason": decision_result.get("reason", "合并相似事实")
                }
            elif update_type == "update":
                # 替换事实
                await log_info("fact_extraction", f"替换事实: {existing_fact.memo} -> {new_fact['memo']}")
                return {
                    "action": "update",
                    "existing_fact": existing_fact,
                    "updated_memo": new_fact["memo"],
                    "reason": decision_result.get("reason", "替换冲突事实")
                }
            elif decision_result.get("needs_update", False):
                # 需要更新但没有指定类型，默认替换
                await log_info("fact_extraction", f"默认替换事实: {existing_fact.memo} -> {new_fact['memo']}")
                return {
                    "action": "update",
                    "existing_fact": existing_fact,
                    "updated_memo": new_fact["memo"],
                    "reason": decision_result.get("reason", "更新事实")
                }
            else:
                # 不需要更新
                return {
                    "action": "skip",
                    "reason": decision_result.get("reason", "内容相似，无需更新")
                }
                
        except Exception as e:
            await log_error("fact_extraction", f"决定事实操作失败: {e}")
            return {"action": "add"}  # 出错时默认添加
    
    async def _detect_conflict(self, new_fact: Dict, existing_fact: FactDocument) -> Dict:
        """检测新事实与现有事实是否存在冲突"""
        try:
            # 简单的关键词冲突检测
            conflict_keywords = {
                "喜欢": ["不喜欢", "讨厌", "厌恶"],
                "不喜欢": ["喜欢", "爱", "热爱"],
                "讨厌": ["喜欢", "爱", "热爱"],
                "厌恶": ["喜欢", "爱", "热爱"],
                "会": ["不会", "不懂", "不擅长"],
                "不会": ["会", "懂", "擅长"],
                "懂": ["不懂", "不会", "不擅长"],
                "不懂": ["懂", "会", "擅长"],
                "擅长": ["不擅长", "不会", "不懂"],
                "不擅长": ["擅长", "会", "懂"]
            }
            
            new_memo = new_fact["memo"].lower()
            existing_memo = existing_fact.memo.lower()
            
            # 检查是否存在明显的态度冲突
            for positive, negatives in conflict_keywords.items():
                if positive in new_memo:
                    for negative in negatives:
                        if negative in existing_memo:
                            return {
                                "is_conflict": True,
                                "reason": f"检测到态度冲突：新事实包含'{positive}'，现有事实包含'{negative}'"
                            }
                elif positive in existing_memo:
                    for negative in negatives:
                        if negative in new_memo:
                            return {
                                "is_conflict": True,
                                "reason": f"检测到态度冲突：现有事实包含'{positive}'，新事实包含'{negative}'"
                            }
            
            return {"is_conflict": False, "reason": "未检测到明显冲突"}
            
        except Exception as e:
            await log_error("fact_extraction", f"冲突检测失败: {e}")
            return {"is_conflict": False, "reason": f"冲突检测失败: {e}"}
    
    async def _llm_decide_update(self, new_fact: Dict, existing_fact: FactDocument, 
                               question: str, answer: str) -> Dict:
        """使用LLM判断是否需要更新事实"""
        try:
            # 构建决策提示词
            current_conversation = f"用户问题：{question}\nAI回答：{answer}"
            user_facts = f"主题：{existing_fact.topic}\n子主题：{existing_fact.sub_topic}\n内容：{existing_fact.memo}"
            
            user_prompt = MEMORY_UPDATE_DECISION_PROMPT.format(
                current_conversation=current_conversation,
                user_facts=user_facts
            )
            
            result = await self._call_llm_with_retry(
                "你是一个专业的事实更新决策助手，负责判断用户的新信息是否需要更新现有记忆。",
                user_prompt,
                1  # 只重试1次
            )
            
            return result if result else {"needs_update": False, "reason": "LLM调用失败"}
            
        except Exception as e:
            await log_error("fact_extraction", f"LLM决策失败: {e}")
            return {"needs_update": False, "reason": f"决策失败: {e}"}
    
    async def _merge_facts(self, existing_memo: str, new_memo: str) -> str:
        """合并两个事实内容"""
        try:
            user_prompt = FACT_MERGE_PROMPT.format(
                existing_fact=existing_memo,
                new_memo=new_memo
            )
            
            result = await self._call_llm_with_retry(
                "你是一个专业的事实合并助手，负责将相关的事实信息进行智能合并。",
                user_prompt,
                1  # 只重试1次
            )
            
            if result and "merged_content" in result:
                return result["merged_content"]
            else:
                # 如果合并失败，返回新内容
                return f"{existing_memo}；{new_memo}"
                
        except Exception as e:
            await log_error("fact_extraction", f"事实合并失败: {e}")
            return f"{existing_memo}；{new_memo}"
    
    async def _call_llm_with_retry(self, system_prompt: str, user_prompt: str, retry_count: int) -> Dict:
        """带重试机制的LLM调用"""
        for attempt in range(retry_count + 1):
            try:
                if not self.session:
                    self.session = aiohttp.ClientSession()
                
                payload = {
                    "model": Config.get_llm_model(),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    "temperature": Config.get_llm_temperature()
                }
                
                async with self.session.post(
                    Config.get_llm_base_url(),
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {Config.get_llm_api_key()}",
                        "Content-Type": "application/json"
                    },
                    timeout=aiohttp.ClientTimeout(total=Config.get_llm_timeout())
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        content = result["choices"][0]["message"]["content"]
                        
                        # 解析JSON响应
                        try:
                            # 处理markdown格式的JSON
                            if content.strip().startswith('```json'):
                                lines = content.strip().split('\n')
                                json_lines = []
                                in_json = False
                                for line in lines:
                                    if line.strip() == '```json':
                                        in_json = True
                                        continue
                                    elif line.strip() == '```':
                                        in_json = False
                                        break
                                    elif in_json:
                                        json_lines.append(line)
                                content = '\n'.join(json_lines)
                            elif content.strip().startswith('```'):
                                lines = content.strip().split('\n')
                                json_lines = []
                                in_json = False
                                for line in lines:
                                    if line.strip().startswith('```'):
                                        if not in_json:
                                            in_json = True
                                        else:
                                            in_json = False
                                            break
                                    elif in_json:
                                        json_lines.append(line)
                                content = '\n'.join(json_lines)
                            
                            parsed_result = json.loads(content)
                            if attempt > 0:
                                await log_info("llm", f"LLM调用成功 (重试第{attempt}次)")
                            return parsed_result
                        except json.JSONDecodeError as e:
                            await log_error("llm", f"LLM返回格式错误: {e}, 内容: {content[:200]}...")
                            if attempt < retry_count:
                                await log_warning("llm", f"LLM返回格式错误，准备重试 (第{attempt + 1}次)")
                                await asyncio.sleep(Config.get_llm_retry_delay() * (attempt + 1))
                                continue
                            else:
                                await log_error("llm", f"LLM返回格式错误，已重试{retry_count}次")
                                return {}
                    else:
                        if attempt < retry_count:
                            await log_warning("llm", f"LLM调用失败，状态码: {response.status}，准备重试 (第{attempt + 1}次)")
                            await asyncio.sleep(Config.get_llm_retry_delay() * (attempt + 1))
                            continue
                        else:
                            await log_error("llm", f"LLM调用失败，状态码: {response.status}，已重试{retry_count}次")
                            return {}
            except asyncio.TimeoutError:
                if attempt < retry_count:
                    await log_warning("llm", f"LLM调用超时，准备重试 (第{attempt + 1}次)")
                    await asyncio.sleep(Config.get_llm_retry_delay() * (attempt + 1))
                    continue
                else:
                    await log_error("llm", f"LLM调用超时，已重试{retry_count}次")
                    return {}
            except Exception as e:
                if attempt < retry_count:
                    await log_warning("llm", f"LLM调用异常: {e}，准备重试 (第{attempt + 1}次)")
                    await asyncio.sleep(Config.get_llm_retry_delay() * (attempt + 1))
                    continue
                else:
                    await log_error("llm", f"LLM调用异常: {e}，已重试{retry_count}次")
                    return {}
        return {}

# 创建全局实例
fact_extraction_service = FactExtractionService()

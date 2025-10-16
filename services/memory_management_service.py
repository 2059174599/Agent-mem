"""
记忆管理服务 - 处理记忆的增删改查业务逻辑
"""
import time
from typing import Dict, Any, Optional
from fastapi.responses import JSONResponse
from models.redis_models import FactDocument
from models.es_models import ChatDocument, ESService
from services.async_logging_service import log_info, log_error
from config import Config
from services.async_memory_service_v2 import AsyncMemoryServiceV2
import asyncio

class MemoryManagementService:
    """记忆管理服务类"""

    def __init__(self, redis_service, cache_service):
        self.redis_service = redis_service
        self.cache_service = cache_service
        self.es_service = ESService()
        self.AsyncMemoryServiceV2 = AsyncMemoryServiceV2()

    async def _store_to_es(self, user_id: str, agent_id: Optional[str],
                          question: str, answer: str) -> Optional[str]:
        """公共方法：ES存储和embedding生成"""
        try:
            # 并行执行：问题embedding生成、ES存储
            tasks = [
                self.AsyncMemoryServiceV2.async_get_embedding(question),
                self.AsyncMemoryServiceV2._store_chat_to_es(user_id, agent_id, question, answer)
            ]

            # 等待embedding和ES存储完成
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # question_embedding = results[0] if not isinstance(results[1], Exception) else []
            chat_id = results[1] if not isinstance(results[1], Exception) else None

            if not chat_id:
                raise Exception("ES存储失败，无法获取chat_id")

            await log_info("es", f"✅ 对话已存储到ES: chat_id={chat_id}")
            return chat_id

        except Exception as e:
            await log_error("es", f"❌ ES存储失败: {e}")
            return None

    async def _store_to_es_and_redis(self, user_id: str, agent_id: Optional[str],
                                   question: str, answer: str, fact: FactDocument,
                                   request_id: str, operation: str) -> Dict[str, Any]:
        """公共方法：并行执行ES存储和Redis操作"""
        start_time = time.time()

        try:
            if operation == "add":
                # 调用公共ES存储方法
                chat_id = await self._store_to_es(user_id, agent_id, question, answer)
                if not chat_id:
                    raise Exception("ES存储失败")
                
                fact.chat_id = chat_id
                redis_task = self.redis_service.add_fact(fact)

            elif operation == "update":
                # 异步获取原有事实
                old_chat_id = fact.chat_id  # 保存原来的chat_id
                fact_ = await self.redis_service.get_facts_by_id(user_id, old_chat_id, agent_id)
                if not fact_:
                    await log_error("memory_management", f"未找到chat_id={old_chat_id}的事实")
                    # 使用默认问答
                    question = f"用户更新事实为: {fact.memo}"
                    answer = f"好的，用户已更新成功"
                else:
                    question = f"用户更新事实:{fact_.get('memo', '')} 为 {fact.memo}"
                    answer = f"好的，用户已更新成功"
                
                # 调用公共ES存储方法
                chat_id = await self._store_to_es(user_id, agent_id, question, answer)
                if not chat_id:
                    raise Exception("ES存储失败")
                
                # 更新Redis：使用old_chat_id查找，chat_id作为新的chat_id
                redis_task = self.redis_service.update_fact_by_chat_id(
                    user_id, old_chat_id, chat_id, fact.memo, agent_id, fact.topic, fact.sub_topic
                )
                # 更新fact对象的chat_id为新的chat_id
                fact.chat_id = chat_id

            elif operation == "delete":
                # 异步获取原有事实
                old_chat_id = fact.chat_id  # 保存原来的chat_id
                fact_ = await self.redis_service.get_facts_by_id(user_id, old_chat_id, agent_id)
                if not fact_:
                    await log_error("memory_management", f"未找到chat_id={old_chat_id}的事实")
                    # 使用默认问答
                    question = f"用户删除事实: chat_id={old_chat_id}"
                    answer = f"好的，用户删除事实成功"
                else:
                    question = f"用户删除事实:{fact_.get('memo', '')}"
                    answer = f"好的，用户删除事实成功"
                
                # 调用公共ES存储方法
                chat_id = await self._store_to_es(user_id, agent_id, question, answer)
                if not chat_id:
                    raise Exception("ES存储失败")
                
                # 删除Redis中的事实（使用原来的chat_id）
                redis_task = self.redis_service.delete_fact_by_chat_id(
                    user_id, old_chat_id, agent_id
                )
                # 更新fact对象的chat_id为新的ES记录ID
                fact.chat_id = chat_id

            elif operation == "delete_all":
                # 这个目前先不支持
                raise Exception("目前暂不支持此功能")
                # redis_task = self.redis_service.delete_all_facts(user_id, agent_id)

            else:
                raise Exception(f"不支持的操作类型: {operation}")

            # 等待Redis操作完成
            success = await redis_task

            processing_time = time.time() - start_time

            return {
                "success": success,
                "chat_id": chat_id if operation != "delete_all" else None,
                "processing_time": processing_time
            }

        except Exception as e:
            processing_time = time.time() - start_time
            await log_error("memory_management", f"❌ [{request_id}] {operation}操作异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time
            }
    
    async def get_predefined_topics(self) -> Dict[str, list]:
        """获取预定义主题，优先从Redis读取，失败则从配置读取"""
        try:
            predefined_topics = await self.cache_service.get("temp", "predefined_topics")
            
            if predefined_topics:
                return predefined_topics
            else:
                # 如果Redis中没有，从配置文件读取
                predefined_topics = Config.get_predefined_topics()
                # 重新存储到Redis
                await self.cache_service.set("temp", "predefined_topics", predefined_topics, 86400)
                return predefined_topics
                
        except Exception as e:
            log_error("memory_management", f"从Redis获取预定义主题失败，使用配置文件: {e}")
            return Config.get_predefined_topics()
    
    async def validate_topic_and_subtopic(self, topic: Optional[str], sub_topic: Optional[str]) -> tuple[bool, str]:
        """验证主题和子主题是否在预定义列表中"""
        if not topic and not sub_topic:
            return True, ""
        
        predefined_topics = await self.get_predefined_topics()
        
        # 如果提供了topic，验证是否在预定义列表中
        if topic and topic not in predefined_topics:
            return False, f"主题 '{topic}' 不在预定义列表中"
        
        # 如果提供了subTopic，需要同时提供topic并验证
        if sub_topic:
            if not topic:
                return False, "提供subTopic必须同时提供topic"
            
            if sub_topic not in predefined_topics.get(topic, []):
                return False, f"子主题 '{sub_topic}' 不在主题 '{topic}' 的子主题列表中"
        
        return True, ""
    
    async def add_memory(self, user_id: str, agent_id: Optional[str], topic: str,
                        sub_topic: str, memo: str, memory_id: Optional[str] = None) -> Dict[str, Any]:
        """添加记忆 - 异步版本，同时存储到Redis和ES"""
        start_time = time.time()
        request_id = f"add_{int(time.time() * 1000)}"

        try:
            await log_info("memory_management", f"🔧 [{request_id}] 开始添加记忆: user_id={user_id}, topic={topic}, sub_topic={sub_topic}")

            # 验证主题和子主题
            is_valid, error_msg = await self.validate_topic_and_subtopic(topic, sub_topic)
            if not is_valid:
                return {
                    "success": False,
                    "error": error_msg,
                    "processing_time": time.time() - start_time
                }

            # 准备ES对话内容
            question = f"添加记忆 - {topic}:{sub_topic}:{memo}"
            answer = f"用户添加了新记忆：{memo}"

            # 创建fact对象
            chat_id = memory_id or f"{user_id}_{int(time.time())}"
            fact = FactDocument(
                user_id=user_id,
                agent_id=agent_id,
                topic=topic,
                sub_topic=sub_topic,
                memo=memo,
                chat_id=chat_id
            )

            # 使用公共方法执行ES存储和Redis操作
            result = await self._store_to_es_and_redis(
                user_id, agent_id, question, answer, fact, request_id, "add"
            )

            if result["success"]:
                await log_info("memory_management", f"✅ [{request_id}] 记忆添加成功: {fact.topic}:{fact.sub_topic}, chat_id={result['chat_id']}, 耗时: {result['processing_time']:.3f}秒")
                return {
                    "success": True,
                    "message": "记忆添加成功",
                    "data": fact.to_dict(),
                    # "chat_id": result["chat_id"],
                    "processing_time": result["processing_time"]
                }
            else:
                await log_error("memory_management", f"❌ [{request_id}] 记忆添加失败: {fact.topic}:{fact.sub_topic}")
                return {
                    "success": False,
                    "error": result.get("error", "记忆添加失败"),
                    "processing_time": result["processing_time"]
                }

        except Exception as e:
            processing_time = time.time() - start_time
            await log_error("memory_management", f"❌ [{request_id}] 添加记忆异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time
            }
    
    async def update_memory(self, user_id: str, agent_id: Optional[str], memory_id: str,
                           memo: str, topic: Optional[str] = None, sub_topic: Optional[str] = None) -> Dict[str, Any]:
        """更新记忆 - 异步版本，同时存储到Redis和ES"""
        start_time = time.time()
        request_id = f"update_{int(time.time() * 1000)}"

        try:
            await log_info("memory_management", f"🔧 [{request_id}] 开始更新记忆: user_id={user_id}, memory_id={memory_id}")

            # 如果提供了topic和subTopic，需要验证
            if topic or sub_topic:
                is_valid, error_msg = await self.validate_topic_and_subtopic(topic, sub_topic)
                if not is_valid:
                    return {
                        "success": False,
                        "error": error_msg,
                        "processing_time": time.time() - start_time
                    }
            else:
                return {
                    "success": False,
                    "error": "topic or sub_topic is need",
                    "processing_time": time.time() - start_time
                }

            # 创建fact对象（用于更新操作）
            fact = FactDocument(
                user_id=user_id,
                agent_id=agent_id,
                topic=topic,
                sub_topic=sub_topic,
                memo=memo,
                chat_id=memory_id  # 使用原有的chat_id
            )

            # 使用公共方法执行ES存储和Redis操作（question和answer将在公共方法中生成）
            result = await self._store_to_es_and_redis(
                user_id, agent_id, "", "", fact, request_id, "update"
            )

            if result["success"]:
                await log_info("memory_management", f"✅ [{request_id}] 记忆更新成功: chat_id={memory_id}, es_chat_id={result['chat_id']}, 耗时: {result['processing_time']:.3f}秒")
                return {
                    "success": True,
                    "message": "记忆更新成功",
                    "chat_id": result["chat_id"],
                    "processing_time": result["processing_time"]
                }
            else:
                await log_error("memory_management", f"❌ [{request_id}] 记忆更新失败: chat_id={memory_id}")
                return {
                    "success": False,
                    "error": result.get("error", f"记忆更新失败memoryId：{memory_id}"),
                    "processing_time": result["processing_time"]
                }

        except Exception as e:
            processing_time = time.time() - start_time
            await log_error("memory_management", f"❌ [{request_id}] 更新记忆异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time
            }
    
    async def delete_memory(self, user_id: str, agent_id: Optional[str], memory_id: Optional[str] = None,
                           delete_all: bool = False) -> Dict[str, Any]:
        """删除记忆 - 异步版本，同时存储到Redis和ES"""
        start_time = time.time()
        request_id = f"delete_{int(time.time() * 1000)}"

        try:
            await log_info("memory_management", f"🔧 [{request_id}] 开始删除记忆: user_id={user_id}, memory_id={memory_id}, delete_all={delete_all}")

            # 确定删除操作类型
            if delete_all:
                # 删除所有记忆的特殊处理（不需要特定的chat_id）
                return {
                    "success": False,
                    "error": "目前暂不支持删除所有记忆",
                    "processing_time": time.time() - start_time
                }
                # question = "删除所有记忆"
                # answer = "用户删除了所有记忆"
                #
                # # 并行执行：问题embedding生成、ES存储
                # tasks = [
                #     self.AsyncMemoryServiceV2.async_get_embedding(question),
                #     self.AsyncMemoryServiceV2._store_chat_to_es(user_id, agent_id, question, answer)
                # ]
                #
                # # 等待embedding和ES存储完成
                # results = await asyncio.gather(*tasks, return_exceptions=True)
                # chat_id = results[1] if not isinstance(results[1], Exception) else None
                #
                # if not chat_id:
                #     raise Exception("ES存储失败，无法获取chat_id")
                #
                # await log_info("es", f"✅ 对话已存储到ES: chat_id={chat_id}")
                #
                # # 执行Redis删除操作
                # success = await self.redis_service.delete_all_facts(user_id, agent_id)
                # message = "所有记忆删除成功"
                #
                # processing_time = time.time() - start_time
                #
                # if success:
                #     await log_info("memory_management", f"✅ [{request_id}] {message}, es_chat_id={chat_id}, 耗时: {processing_time:.3f}秒")
                #     return {
                #         "success": True,
                #         "message": message,
                #         "es_chat_id": chat_id,
                #         "processing_time": processing_time
                #     }
                # else:
                #     await log_error("memory_management", f"❌ [{request_id}] 记忆删除失败")
                #     return {
                #         "success": False,
                #         "error": "记忆删除失败",
                #         "processing_time": processing_time
                #     }

            elif memory_id:
                # 删除指定记忆，使用公共方法
                # 创建fact对象（用于删除操作）
                fact = FactDocument(
                    user_id=user_id,
                    agent_id=agent_id,
                    topic="",  # 删除操作不需要topic
                    sub_topic="",
                    memo="",  # 删除操作不需要memo
                    chat_id=memory_id
                )

                # 使用公共方法执行ES存储和Redis操作（question和answer将在公共方法中生成）
                result = await self._store_to_es_and_redis(
                    user_id, agent_id, "", "", fact, request_id, "delete"
                )

                message = f"记忆删除成功: chat_id={memory_id}"

                if result["success"]:
                    await log_info("memory_management", f"✅ [{request_id}] {message}, es_chat_id={result['chat_id']}, 耗时: {result['processing_time']:.3f}秒")
                    return {
                        "success": True,
                        "message": message,
                        "es_chat_id": result["chat_id"],
                        "processing_time": result["processing_time"]
                    }
                else:
                    await log_error("memory_management", f"❌ [{request_id}] 记忆删除失败")
                    return {
                        "success": False,
                        "error": result.get("error", "记忆删除失败"),
                        "processing_time": result["processing_time"]
                    }
            else:
                return {
                    "success": False,
                    "error": "删除记忆需要提供memoryId或设置deleteAll=true",
                    "processing_time": time.time() - start_time
                }

        except Exception as e:
            processing_time = time.time() - start_time
            await log_error("memory_management", f"❌ [{request_id}] 删除记忆异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time
            }
    
    async def query_memory(self, user_id: str, agent_id: Optional[str], topic: Optional[str] = None,
                          limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """查询记忆"""
        start_time = time.time()
        request_id = f"query_{int(time.time() * 1000)}"
        
        try:
            await log_info("memory_management", f"🔍 [{request_id}] 开始查询记忆: user_id={user_id}, agent_id={agent_id}")
            
            # 查询记忆
            facts = await self.redis_service.get_facts(user_id, agent_id)
            
            # 按主题过滤（如果指定）
            if topic:
                facts = [fact for fact in facts if fact.topic == topic]
            
            # 应用分页
            start_idx = offset
            end_idx = offset + limit
            paginated_facts = facts[start_idx:end_idx]
            
            # 转换为字典格式
            facts_list = []
            for fact in paginated_facts:
                fact_dict = fact.to_dict()
                facts_list.append(fact_dict)
            
            processing_time = time.time() - start_time
            await log_info("memory_management", f"✅ [{request_id}] 记忆查询成功: {len(facts_list)}个事实, 耗时: {processing_time:.3f}秒")
            
            return {
                "success": True,
                "data": {
                    "facts": facts_list,
                    "total": len(facts),
                    "offset": offset,
                    "limit": limit
                },
                "processing_time": processing_time
            }
                
        except Exception as e:
            processing_time = time.time() - start_time
            await log_error("memory_management", f"❌ [{request_id}] 查询记忆异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "processing_time": processing_time
            }

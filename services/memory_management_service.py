"""
记忆管理服务 - 处理记忆的增删改查业务逻辑
"""
import time
from typing import Dict, Any, Optional
from fastapi.responses import JSONResponse
from models.redis_models import FactDocument
from services.async_logging_service import log_info, log_error
from config import Config


class MemoryManagementService:
    """记忆管理服务类"""
    
    def __init__(self, redis_service, cache_service):
        self.redis_service = redis_service
        self.cache_service = cache_service
    
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
        """添加记忆"""
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
            
            # 创建事实文档
            fact = FactDocument(
                user_id=user_id,
                agent_id=agent_id,
                topic=topic,
                sub_topic=sub_topic,
                memo=memo,
                chat_id=memory_id or f"{user_id}_{int(time.time())}"
            )
            
            # 添加事实
            success = await self.redis_service.add_fact(fact)
            
            processing_time = time.time() - start_time
            
            if success:
                await log_info("memory_management", f"✅ [{request_id}] 记忆添加成功: {fact.topic}:{fact.sub_topic}, 耗时: {processing_time:.3f}秒")
                return {
                    "success": True,
                    "message": "记忆添加成功",
                    "data": fact.to_dict(),
                    "processing_time": processing_time
                }
            else:
                await log_error("memory_management", f"❌ [{request_id}] 记忆添加失败: {fact.topic}:{fact.sub_topic}")
                return {
                    "success": False,
                    "error": "记忆添加失败",
                    "processing_time": processing_time
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
        """更新记忆"""
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
            
            # 根据chat_id更新事实
            success = await self.redis_service.update_fact_by_chat_id(
                user_id, 
                memory_id, 
                memo, 
                agent_id,
                topic,
                sub_topic
            )
            
            processing_time = time.time() - start_time
            
            if success:
                await log_info("memory_management", f"✅ [{request_id}] 记忆更新成功: chat_id={memory_id}, 耗时: {processing_time:.3f}秒")
                return {
                    "success": True,
                    "message": "记忆更新成功",
                    "processing_time": processing_time
                }
            else:
                await log_error("memory_management", f"❌ [{request_id}] 记忆更新失败: chat_id={memory_id}")
                return {
                    "success": False,
                    "error": f"记忆更新失败memoryId：{memory_id}",
                    "processing_time": processing_time
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
        """删除记忆"""
        start_time = time.time()
        request_id = f"delete_{int(time.time() * 1000)}"
        
        try:
            await log_info("memory_management", f"🔧 [{request_id}] 开始删除记忆: user_id={user_id}, memory_id={memory_id}, delete_all={delete_all}")
            
            if delete_all:
                # 删除用户所有记忆
                success = await self.redis_service.delete_all_facts(user_id, agent_id)
                message = "所有记忆删除成功"
            elif memory_id:
                # 删除指定记忆
                success = await self.redis_service.delete_fact_by_chat_id(
                    user_id, 
                    memory_id, 
                    agent_id
                )
                message = f"记忆删除成功: chat_id={memory_id}"
            else:
                return {
                    "success": False,
                    "error": "删除记忆需要提供memoryId或设置deleteAll=true",
                    "processing_time": time.time() - start_time
                }
            
            processing_time = time.time() - start_time
            
            if success:
                await log_info("memory_management", f"✅ [{request_id}] {message}, 耗时: {processing_time:.3f}秒")
                return {
                    "success": True,
                    "message": message,
                    "processing_time": processing_time
                }
            else:
                await log_error("memory_management", f"❌ [{request_id}] 记忆删除失败")
                return {
                    "success": False,
                    "error": "记忆删除失败",
                    "processing_time": processing_time
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

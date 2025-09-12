#!/usr/bin/env python3
"""
ES数据清理API测试文件
测试通过API删除ES数据的功能，包括指定用户和全部删除
"""

import asyncio
import sys
import os
import json
import time
from typing import Dict, List, Optional

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from config import Config
from services.async_memory_service_v2 import AsyncMemoryServiceV2
from models.es_models import ESService
from logging_config import get_logger

# 设置日志
logger = get_logger(__name__)

class ClearESAPITester:
    """ES数据清理API测试类"""
    
    def __init__(self, base_url: str = "http://localhost:5010"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_user_id = "test_user_clear_es"
        self.test_agent_id = "test_agent_clear_es"
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def setup_test_data(self) -> Dict:
        """设置测试数据 - 添加一些记忆到ES"""
        logger.info("🔧 开始设置测试数据...")
        
        test_memories = [
            {
                "user_id": self.test_user_id,
                "agent_id": self.test_agent_id,
                "question": "我喜欢吃苹果",
                "answer": "苹果是一种很健康的水果，富含维生素C和纤维。"
            },
            {
                "user_id": self.test_user_id,
                "agent_id": self.test_agent_id,
                "question": "我每天跑步30分钟",
                "answer": "跑步是很好的有氧运动，有助于提高心肺功能。"
            },
            {
                "user_id": "other_user",
                "agent_id": "other_agent",
                "question": "我喜欢游泳",
                "answer": "游泳是全身运动，对关节友好。"
            }
        ]
        
        added_chats = []
        async with AsyncMemoryServiceV2() as memory_service:
            for memory in test_memories:
                try:
                    result = await memory_service.add_memory_async(
                        user_id=memory["user_id"],
                        agent_id=memory["agent_id"],
                        question=memory["question"],
                        answer=memory["answer"]
                    )
                    if result.get("success"):
                        added_chats.append({
                            "chat_id": result.get("chat_id"),
                            "user_id": memory["user_id"],
                            "agent_id": memory["agent_id"],
                            "question": memory["question"]
                        })
                        logger.info(f"✅ 添加测试记忆: {memory['question'][:20]}... -> {result.get('chat_id')}")
                    else:
                        logger.error(f"❌ 添加测试记忆失败: {memory['question'][:20]}... -> {result.get('error')}")
                except Exception as e:
                    logger.error(f"❌ 添加测试记忆异常: {memory['question'][:20]}... -> {e}")
        
        logger.info(f"📊 测试数据设置完成，共添加 {len(added_chats)} 条记录")
        return {"added_chats": added_chats}
    
    async def verify_es_data(self, expected_count: int = None, user_id: str = None, agent_id: str = None) -> Dict:
        """验证ES中的数据"""
        logger.info(f"🔍 验证ES数据 - 期望数量: {expected_count}, 用户ID: {user_id}, 代理ID: {agent_id}")
        
        try:
            es_service = ESService()
            if user_id or agent_id:
                # 获取指定用户/代理的数据
                all_chats = es_service.get_all_chats()
                filtered_chats = []
                for chat in all_chats:
                    if user_id and chat.get("user_id") != user_id:
                        continue
                    if agent_id and chat.get("agent_id") != agent_id:
                        continue
                    filtered_chats.append(chat)
                actual_count = len(filtered_chats)
                logger.info(f"📊 指定条件的数据数量: {actual_count}")
            else:
                # 获取全部数据
                all_chats = es_service.get_all_chats()
                actual_count = len(all_chats)
                logger.info(f"📊 ES总数据数量: {actual_count}")
            
            if expected_count is not None:
                if actual_count == expected_count:
                    logger.info(f"✅ 数据验证通过: 实际数量 {actual_count} = 期望数量 {expected_count}")
                    return {"success": True, "count": actual_count}
                else:
                    logger.warning(f"⚠️ 数据验证不匹配: 实际数量 {actual_count} ≠ 期望数量 {expected_count}")
                    return {"success": False, "count": actual_count, "expected": expected_count}
            else:
                logger.info(f"📊 当前ES数据数量: {actual_count}")
                return {"success": True, "count": actual_count}
                
        except Exception as e:
            logger.error(f"❌ 验证ES数据失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_clear_by_user_id_preview(self) -> Dict:
        """测试按用户ID清理ES数据（预览模式）"""
        logger.info("🧪 测试按用户ID清理ES数据（预览模式）")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/memory/clear",
                params={
                    "user_id": self.test_user_id,
                    "dry_run": True
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ 预览模式成功: {json.dumps(result, ensure_ascii=False, indent=2)}")
                return {"success": True, "result": result}
            else:
                logger.error(f"❌ 预览模式失败: {response.status_code} - {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"❌ 预览模式异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_clear_by_user_id_actual(self) -> Dict:
        """测试按用户ID清理ES数据（实际删除）"""
        logger.info("🧪 测试按用户ID清理ES数据（实际删除）")
        
        # 先验证删除前的数据
        before_result = await self.verify_es_data(user_id=self.test_user_id)
        if not before_result["success"]:
            return before_result
        
        before_count = before_result["count"]
        logger.info(f"📊 删除前数据数量: {before_count}")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/memory/clear",
                headers={
                    "Authorization": f"Bearer yixinagentmemory",
                },
                params={
                    "user_id": self.test_user_id,
                    "dry_run": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ 实际删除成功: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # 验证删除后的数据
                after_result = await self.verify_es_data(user_id=self.test_user_id)
                if after_result["success"]:
                    after_count = after_result["count"]
                    logger.info(f"📊 删除后数据数量: {after_count}")
                    if after_count == 0:
                        logger.info("✅ 用户数据完全清理成功")
                    else:
                        logger.warning(f"⚠️ 用户数据未完全清理，剩余 {after_count} 条")
                
                return {"success": True, "result": result, "before_count": before_count, "after_count": after_result.get("count", 0)}
            else:
                logger.error(f"❌ 实际删除失败: {response.status_code} - {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"❌ 实际删除异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_clear_by_agent_id_preview(self) -> Dict:
        """测试按代理ID清理ES数据（预览模式）"""
        logger.info("🧪 测试按代理ID清理ES数据（预览模式）")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/memory/clear",
                params={
                    "agent_id": self.test_agent_id,
                    "dry_run": True
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ 预览模式成功: {json.dumps(result, ensure_ascii=False, indent=2)}")
                return {"success": True, "result": result}
            else:
                logger.error(f"❌ 预览模式失败: {response.status_code} - {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"❌ 预览模式异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_clear_all_preview(self) -> Dict:
        """测试清理所有ES数据（预览模式）"""
        logger.info("🧪 测试清理所有ES数据（预览模式）")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/memory/clear",
                params={
                    "dry_run": True
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ 预览模式成功: {json.dumps(result, ensure_ascii=False, indent=2)}")
                return {"success": True, "result": result}
            else:
                logger.error(f"❌ 预览模式失败: {response.status_code} - {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"❌ 预览模式异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_clear_all_actual(self) -> Dict:
        """测试清理所有ES数据（实际删除）"""
        logger.info("🧪 测试清理所有ES数据（实际删除）")
        
        # 先验证删除前的数据
        before_result = await self.verify_es_data()
        if not before_result["success"]:
            return before_result
        
        before_count = before_result["count"]
        logger.info(f"📊 删除前总数据数量: {before_count}")
        
        try:
            response = await self.client.post(
                f"{self.base_url}/memory/clear",
                headers={
                    "Authorization": f"Bearer yixinagentmemory",
                },
                params={
                    "dry_run": False
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ 实际删除成功: {json.dumps(result, ensure_ascii=False, indent=2)}")
                
                # 验证删除后的数据
                after_result = await self.verify_es_data()
                if after_result["success"]:
                    after_count = after_result["count"]
                    logger.info(f"📊 删除后总数据数量: {after_count}")
                    if after_count == 0:
                        logger.info("✅ 所有数据完全清理成功")
                    else:
                        logger.warning(f"⚠️ 数据未完全清理，剩余 {after_count} 条")
                
                return {"success": True, "result": result, "before_count": before_count, "after_count": after_count}
            else:
                logger.error(f"❌ 实际删除失败: {response.status_code} - {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            logger.error(f"❌ 实际删除异常: {e}")
            return {"success": False, "error": str(e)}
    
    async def test_api_health(self) -> bool:
        """测试API健康状态"""
        logger.info("🏥 测试API健康状态")
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                logger.info("✅ API健康检查通过")
                return True
            else:
                logger.error(f"❌ API健康检查失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"❌ API健康检查异常: {e}")
            return False

async def main():
    """主测试函数"""
    logger.info("🚀 开始ES数据清理API测试")
    
    async with ClearESAPITester() as tester:
        # # 1. 检查API健康状态
        # if not await tester.test_api_health():
        #     logger.error("❌ API不可用，测试终止")
        #     return
        #
        # # 2. 设置测试数据
        # setup_result = await tester.setup_test_data()
        # if not setup_result.get("added_chats"):
        #     logger.error("❌ 测试数据设置失败，测试终止")
        #     return
        #
        # # 等待一下确保数据写入完成
        # await asyncio.sleep(2)
        #
        # # 3. 测试按用户ID清理（预览模式）
        # logger.info("\n" + "="*50)
        # await tester.test_clear_by_user_id_preview()
        #
        # # 4. 测试按代理ID清理（预览模式）
        # logger.info("\n" + "="*50)
        # await tester.test_clear_by_agent_id_preview()
        #
        # # 5. 测试清理所有数据（预览模式）
        # logger.info("\n" + "="*50)
        # await tester.test_clear_all_preview()
        #
        # # 6. 测试按用户ID清理（实际删除）
        # logger.info("\n" + "="*50)
        # await tester.test_clear_by_user_id_actual()
        #
        # 7. 测试清理所有数据（实际删除）
        logger.info("\n" + "="*50)
        await tester.test_clear_all_actual()

        logger.info("\n🎉 ES数据清理API测试完成")

if __name__ == "__main__":
    asyncio.run(main())

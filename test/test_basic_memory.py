#!/usr/bin/env python3
"""
基本记忆功能测试
简化版本，重点测试核心功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from models.redis_models import RedisService
from models.es_models import ESService
from logging_config import get_logger

logger = get_logger(__name__)

async def test_basic_add_and_search():
    """测试基本添加和搜索功能"""
    logger.info("🧪 测试基本记忆添加和搜索")
    
    user_id = "basic_test_user"
    agent_id = "basic_test_agent"
    
    try:
        # 1. 添加记忆
        logger.info("📝 步骤1: 添加记忆")
        async with AsyncMemoryServiceV2() as memory_service:
            add_result = await memory_service.add_memory_async(
                user_id=user_id,
                agent_id=agent_id,
                question="我喜欢吃苹果",
                answer="苹果富含维生素C，对健康很有好处。"
            )
            
            if not add_result.get("success"):
                logger.error(f"❌ 记忆添加失败: {add_result.get('error')}")
                return False
            
            logger.info(f"✅ 记忆添加成功: chat_id={add_result.get('chat_id')}")
            logger.info(f"📊 提取事实数量: {add_result.get('total_facts', 0)}")
            
            # 等待数据写入
            await asyncio.sleep(3)
            
            # 2. 直接检查Redis中的事实
            logger.info("\n🔍 步骤2: 检查Redis中的事实")
            redis_service = RedisService()
            facts = await redis_service.get_facts(user_id, agent_id)
            logger.info(f"📊 Redis中的事实数量: {len(facts)}")
            
            for i, fact in enumerate(facts):
                logger.info(f"  事实 {i+1}: {fact.topic} - {fact.sub_topic} - {fact.memo}")
            
            # 3. 直接检查ES中的对话
            logger.info("\n🔍 步骤3: 检查ES中的对话")
            es_service = ESService()
            recent_chats = es_service.get_recent_chats(user_id, agent_id, 5)
            logger.info(f"📊 ES中的对话数量: {len(recent_chats)}")
            
            for i, chat in enumerate(recent_chats):
                logger.info(f"  对话 {i+1}: {chat.get('question', '')}")
                logger.info(f"        答案: {chat.get('answer', '')[:50]}...")
            
            # 4. 测试记忆搜索
            logger.info("\n🔍 步骤4: 测试记忆搜索")
            search_result = await memory_service.search_memory_async(
                user_id=user_id,
                agent_id=agent_id,
                query="我喜欢吃什么水果",
                limit=5
            )
            
            if not search_result.get("success"):
                logger.error(f"❌ 记忆搜索失败: {search_result.get('error')}")
                return False
            
            # 分析搜索结果
            facts = search_result.get("facts", [])
            chats = search_result.get("chats", [])
            recent_chats = search_result.get("recent_chats", [])
            
            logger.info(f"📊 搜索结果:")
            logger.info(f"  - 事实数量: {len(facts)}")
            logger.info(f"  - 相似对话: {len(chats)}")
            logger.info(f"  - 最近对话: {len(recent_chats)}")
            
            # 显示事实详情
            if facts:
                logger.info("📋 搜索到的事实:")
                for i, fact in enumerate(facts):
                    logger.info(f"  {i+1}. {fact.get('topic', '')} - {fact.get('sub_topic', '')} - {fact.get('memo', '')}")
            
            # 显示相似对话
            if chats:
                logger.info("💬 搜索到的相似对话:")
                for i, chat in enumerate(chats):
                    logger.info(f"  {i+1}. Q: {chat.get('question', '')}")
                    logger.info(f"     A: {chat.get('answer', '')[:100]}...")
            
            # 5. 验证相关性
            logger.info("\n📈 步骤5: 验证相关性")
            relevance_found = 0
            
            # 检查事实中的相关性
            for fact in facts:
                fact_text = f"{fact.get('memo', '')}".lower()
                if "苹果" in fact_text or "水果" in fact_text:
                    relevance_found += 1
                    logger.info(f"✅ 事实相关: {fact.get('memo', '')}")
            
            # 检查对话中的相关性
            for chat in chats:
                chat_text = f"{chat.get('question', '')} {chat.get('answer', '')}".lower()
                if "苹果" in chat_text or "水果" in chat_text:
                    relevance_found += 1
                    logger.info(f"✅ 对话相关: {chat.get('question', '')}")
            
            logger.info(f"📊 找到相关结果: {relevance_found} 个")
            
            if relevance_found > 0:
                logger.info("✅ 基本记忆功能测试成功！")
                return True
            else:
                logger.warning("⚠️ 未找到相关结果，需要检查搜索逻辑")
                return False
                
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_user_isolation():
    """测试用户隔离"""
    logger.info("\n🧪 测试用户隔离")
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            # 为不同用户添加不同记忆
            await memory_service.add_memory_async(
                user_id="user_1",
                agent_id="agent_1",
                question="我喜欢红色",
                answer="红色是很有活力的颜色。"
            )
            
            await memory_service.add_memory_async(
                user_id="user_2",
                agent_id="agent_1", 
                question="我喜欢蓝色",
                answer="蓝色是平静的颜色。"
            )
            
            await asyncio.sleep(3)
            
            # 搜索用户1的记忆
            result1 = await memory_service.search_memory_async(
                user_id="user_1",
                agent_id="agent_1",
                query="我喜欢什么颜色",
                limit=5
            )
            
            # 搜索用户2的记忆
            result2 = await memory_service.search_memory_async(
                user_id="user_2",
                agent_id="agent_1",
                query="我喜欢什么颜色",
                limit=5
            )
            
            # 分析结果
            facts1 = result1.get("facts", [])
            facts2 = result2.get("facts", [])
            
            logger.info(f"📊 用户1搜索结果: {len(facts1)} 个事实")
            logger.info(f"📊 用户2搜索结果: {len(facts2)} 个事实")
            
            # 检查隔离效果
            user1_has_red = any("红色" in str(fact) for fact in facts1)
            user2_has_blue = any("蓝色" in str(fact) for fact in facts2)
            
            if user1_has_red and user2_has_blue:
                logger.info("✅ 用户隔离测试成功！")
                return True
            else:
                logger.warning("⚠️ 用户隔离效果不佳")
                return False
                
    except Exception as e:
        logger.error(f"❌ 隔离测试异常: {e}")
        return False

async def main():
    """主测试函数"""
    logger.info("🚀 开始基本记忆功能测试")
    logger.info("=" * 50)
    
    # 运行测试
    test1_result = await test_basic_add_and_search()
    test2_result = await test_user_isolation()
    
    # 总结
    logger.info("\n" + "=" * 50)
    logger.info("📊 测试结果总结")
    logger.info("=" * 50)
    
    tests = [
        ("基本记忆功能", test1_result),
        ("用户隔离", test2_result)
    ]
    
    passed = 0
    for test_name, result in tests:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed += 1
    
    success_rate = passed / len(tests)
    logger.info(f"\n📈 成功率: {success_rate:.1%} ({passed}/{len(tests)})")
    
    if success_rate == 1.0:
        logger.info("🎉 所有测试通过！基本记忆功能正常")
    else:
        logger.warning("⚠️ 部分测试失败，需要检查")

if __name__ == "__main__":
    asyncio.run(main())

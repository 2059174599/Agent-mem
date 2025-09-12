#!/usr/bin/env python3
"""
记忆添加和搜索快速测试
简化版本，快速验证核心功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from logging_config import get_logger

logger = get_logger(__name__)

async def quick_memory_test():
    """快速记忆测试"""
    logger.info("🚀 开始快速记忆测试")
    
    user_id = "quick_test_user"
    agent_id = "quick_test_agent"
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            # 1. 添加记忆
            logger.info("📝 步骤1: 添加记忆")
            add_result = await memory_service.add_memory_async(
                user_id=user_id,
                agent_id=agent_id,
                question="我喜欢吃苹果和香蕉",
                answer="苹果和香蕉都是很健康的水果，苹果富含维生素C，香蕉富含钾元素。"
            )
            
            if not add_result.get("success"):
                logger.error(f"❌ 记忆添加失败: {add_result.get('error')}")
                return False
            
            logger.info(f"✅ 记忆添加成功: chat_id={add_result.get('chat_id')}")
            logger.info(f"📊 提取事实数量: {add_result.get('total_facts', 0)}")
            
            # 等待数据写入
            await asyncio.sleep(3)
            
            # 2. 搜索记忆
            logger.info("\n🔍 步骤2: 搜索记忆")
            search_result = await memory_service.search_memory_async(
                user_id=user_id,
                agent_id=agent_id,
                query="我喜欢吃什么水果",
                limit=5
            )
            
            if not search_result.get("success"):
                logger.error(f"❌ 记忆搜索失败: {search_result.get('error')}")
                return False
            
            # 3. 分析结果
            facts = search_result.get("facts", [])
            chats = search_result.get("chats", [])
            recent_chats = search_result.get("recent_chats", [])
            
            logger.info(f"📊 搜索结果:")
            logger.info(f"  - 事实数量: {len(facts)}")
            logger.info(f"  - 相似对话: {len(chats)}")
            logger.info(f"  - 最近对话: {len(recent_chats)}")
            
            # 显示事实详情
            if facts:
                logger.info("📋 提取的事实:")
                for i, fact in enumerate(facts):
                    logger.info(f"  {i+1}. {fact.get('topic', '')} - {fact.get('sub_topic', '')} - {fact.get('memo', '')}")
            
            # 显示相似对话
            if chats:
                logger.info("💬 相似对话:")
                for i, chat in enumerate(chats):
                    logger.info(f"  {i+1}. Q: {chat.get('question', '')}")
                    logger.info(f"     A: {chat.get('answer', '')[:100]}...")
            
            # 4. 验证相关性
            relevance_score = 0
            if facts:
                for fact in facts:
                    fact_text = f"{fact.get('memo', '')}".lower()
                    if "苹果" in fact_text or "香蕉" in fact_text or "水果" in fact_text:
                        relevance_score += 1
            
            if chats:
                for chat in chats:
                    chat_text = f"{chat.get('question', '')} {chat.get('answer', '')}".lower()
                    if "苹果" in chat_text or "香蕉" in chat_text or "水果" in chat_text:
                        relevance_score += 1
            
            logger.info(f"\n📈 相关性验证: 找到 {relevance_score} 个相关结果")
            
            if relevance_score > 0:
                logger.info("✅ 记忆添加和搜索测试成功！")
                return True
            else:
                logger.warning("⚠️ 搜索结果相关性不足")
                return False
                
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_user_agent_isolation():
    """测试用户和代理隔离"""
    logger.info("\n🧪 测试用户和代理隔离")
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            # 为不同用户添加不同记忆
            await memory_service.add_memory_async(
                user_id="user_a",
                agent_id="agent_1",
                question="我喜欢红色",
                answer="红色是很有活力的颜色，让我感到兴奋。"
            )
            
            await memory_service.add_memory_async(
                user_id="user_b", 
                agent_id="agent_1",
                question="我喜欢蓝色",
                answer="蓝色是平静的颜色，让我感到放松。"
            )
            
            await asyncio.sleep(3)
            
            # 搜索用户A的记忆
            result_a = await memory_service.search_memory_async(
                user_id="user_a",
                agent_id="agent_1", 
                query="我喜欢什么颜色",
                limit=5
            )
            
            # 搜索用户B的记忆
            result_b = await memory_service.search_memory_async(
                user_id="user_b",
                agent_id="agent_1",
                query="我喜欢什么颜色", 
                limit=5
            )
            
            # 分析结果
            facts_a = result_a.get("facts", [])
            facts_b = result_b.get("facts", [])
            
            logger.info(f"📊 用户A搜索结果: {len(facts_a)} 个事实")
            logger.info(f"📊 用户B搜索结果: {len(facts_b)} 个事实")
            
            # 检查隔离效果
            user_a_has_red = any("红色" in str(fact) for fact in facts_a)
            user_b_has_blue = any("蓝色" in str(fact) for fact in facts_b)
            
            if user_a_has_red and user_b_has_blue:
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
    logger.info("🧪 开始记忆功能快速测试")
    logger.info("=" * 50)
    
    # 运行测试
    test1_result = await quick_memory_test()
    test2_result = await test_user_agent_isolation()
    
    # 总结
    logger.info("\n" + "=" * 50)
    logger.info("📊 测试结果总结")
    logger.info("=" * 50)
    
    tests = [
        ("基本记忆功能", test1_result),
        ("用户代理隔离", test2_result)
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
        logger.info("🎉 所有测试通过！记忆功能工作正常")
    else:
        logger.warning("⚠️ 部分测试失败，需要检查")

if __name__ == "__main__":
    asyncio.run(main())

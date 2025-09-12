#!/usr/bin/env python3
"""
测试搜索问题：搜索"推荐一下有跑道的公园"时返回不相关结果
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from models.es_models import ESService
from logging_config import get_logger

logger = get_logger(__name__)

async def test_search_issue():
    """测试搜索问题"""
    logger.info("🧪 开始测试搜索问题")
    
    user_id = "44e8e103-efed-4a48-94ad-1b1d0ac0548a"
    query = "推荐一下有跑道的公园"
    
    try:
        # 1. 先查看ES中有什么数据
        logger.info("1️⃣ 查看ES中的数据")
        es_service = ESService()
        all_chats = es_service.get_all_chats()
        
        logger.info(f"📊 ES中总共有 {len(all_chats)} 条记录")
        for i, chat in enumerate(all_chats):
            logger.info(f"  记录 {i+1}:")
            logger.info(f"    user_id: {chat.get('user_id', '')}")
            logger.info(f"    question: {chat.get('question', '')}")
            logger.info(f"    answer: {chat.get('answer', '')[:100]}...")
        
        # 2. 测试关键词搜索
        logger.info(f"\n2️⃣ 测试关键词搜索: '{query}'")
        keyword_results = es_service.search_similar_chats_by_question_only(user_id, query, 5)
        logger.info(f"📊 关键词搜索返回 {len(keyword_results)} 条记录")
        
        for i, chat in enumerate(keyword_results):
            logger.info(f"  结果 {i+1}:")
            logger.info(f"    question: {chat.get('question', '')}")
            logger.info(f"    answer: {chat.get('answer', '')[:100]}...")
            logger.info(f"    score: {chat.get('_score', 'N/A')}")
        
        # 3. 测试混合搜索
        logger.info(f"\n3️⃣ 测试混合搜索: '{query}'")
        async with AsyncMemoryServiceV2() as memory_service:
            # 获取embedding
            query_embedding = await memory_service.async_get_embedding(query)
            logger.info(f"📊 查询embedding长度: {len(query_embedding) if query_embedding else 0}")
            
            if query_embedding:
                mixed_results = es_service.search_similar_chats(user_id, query, query_embedding, None, 5)
                logger.info(f"📊 混合搜索返回 {len(mixed_results)} 条记录")
                
                for i, chat in enumerate(mixed_results):
                    logger.info(f"  结果 {i+1}:")
                    logger.info(f"    question: {chat.get('question', '')}")
                    logger.info(f"    answer: {chat.get('answer', '')[:100]}...")
                    logger.info(f"    score: {chat.get('_score', 'N/A')}")
            else:
                logger.warning("⚠️ 无法获取查询embedding，跳过混合搜索测试")
        
        # 4. 测试异步搜索方法
        logger.info(f"\n4️⃣ 测试异步搜索方法: '{query}'")
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service._search_chats_async(user_id, query, None, 5)
            
            if result.get("success"):
                chats = result.get("chats", [])
                logger.info(f"📊 异步搜索返回 {len(chats)} 条记录")
                
                for i, chat in enumerate(chats):
                    logger.info(f"  结果 {i+1}:")
                    logger.info(f"    question: {chat.get('question', '')}")
                    logger.info(f"    answer: {chat.get('answer', '')[:100]}...")
            else:
                logger.error(f"❌ 异步搜索失败: {result}")
        
        logger.info("\n🎉 搜索问题测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search_issue())

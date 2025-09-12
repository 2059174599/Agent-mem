#!/usr/bin/env python3
"""
测试获取最近对话功能
验证chat_id是否正确获取ES的_id
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

async def test_recent_chats():
    """测试获取最近对话功能"""
    logger.info("🧪 开始测试获取最近对话功能")
    
    try:
        # 1. 直接测试ES服务
        logger.info("1️⃣ 测试ES服务get_recent_chats方法")
        es_service = ESService()
        
        # 获取一些测试数据
        recent_chats = es_service.get_recent_chats("test_user", None, 5)
        logger.info(f"📊 ES服务返回 {len(recent_chats)} 条记录")
        
        for i, chat in enumerate(recent_chats):
            logger.info(f"  记录 {i+1}:")
            logger.info(f"    chat_id: '{chat.get('chat_id', 'EMPTY')}'")
            logger.info(f"    question: {chat.get('question', '')[:50]}...")
            logger.info(f"    answer: {chat.get('answer', '')[:50]}...")
            logger.info(f"    timestamp: {chat.get('timestamp', '')}")
        
        # 2. 测试异步内存服务
        logger.info("\n2️⃣ 测试AsyncMemoryServiceV2的_get_recent_chats_async方法")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service._get_recent_chats_async("test_user", None, 5)
            
            if result.get("success"):
                chats = result.get("chats", [])
                logger.info(f"📊 异步服务返回 {len(chats)} 条记录")
                
                for i, chat in enumerate(chats):
                    logger.info(f"  记录 {i+1}:")
                    logger.info(f"    chat_id: '{chat.get('chat_id', 'EMPTY')}'")
                    logger.info(f"    question: {chat.get('question', '')[:50]}...")
                    logger.info(f"    answer: {chat.get('answer', '')[:50]}...")
                    logger.info(f"    timestamp: {chat.get('timestamp', '')}")
            else:
                logger.error(f"❌ 异步服务调用失败: {result}")
        
        # 3. 检查chat_id是否为空
        logger.info("\n3️⃣ 检查chat_id是否为空")
        empty_count = 0
        for chat in recent_chats:
            if not chat.get('chat_id') or chat.get('chat_id') == '':
                empty_count += 1
        
        if empty_count == 0:
            logger.info("✅ 所有chat_id都有值")
        else:
            logger.warning(f"⚠️ 有 {empty_count} 个chat_id为空")
        
        logger.info("\n🎉 测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_recent_chats())

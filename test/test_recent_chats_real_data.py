#!/usr/bin/env python3
"""
使用真实数据测试获取最近对话功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.es_models import ESService
from logging_config import get_logger

logger = get_logger(__name__)

def test_real_data():
    """使用真实数据测试"""
    logger.info("🧪 开始测试真实数据")
    
    try:
        es_service = ESService()
        
        # 1. 获取所有数据看看有什么
        logger.info("1️⃣ 获取所有ES数据")
        all_chats = es_service.get_all_chats()
        logger.info(f"📊 ES中总共有 {len(all_chats)} 条记录")
        
        if len(all_chats) > 0:
            # 显示前几条记录的信息
            for i, chat in enumerate(all_chats[:3]):
                logger.info(f"  记录 {i+1}:")
                logger.info(f"    chat_id: '{chat.get('chat_id', 'EMPTY')}'")
                logger.info(f"    user_id: '{chat.get('user_id', 'EMPTY')}'")
                logger.info(f"    agent_id: '{chat.get('agent_id', 'EMPTY')}'")
                logger.info(f"    question: {chat.get('question', '')[:50]}...")
                logger.info(f"    answer: {chat.get('answer', '')[:50]}...")
                logger.info(f"    timestamp: {chat.get('timestamp', '')}")
            
            # 2. 使用第一个记录的用户ID测试get_recent_chats
            first_chat = all_chats[0]
            user_id = first_chat.get('user_id')
            agent_id = first_chat.get('agent_id')
            
            logger.info(f"\n2️⃣ 使用真实用户ID测试: user_id={user_id}, agent_id={agent_id}")
            recent_chats = es_service.get_recent_chats(user_id, agent_id, 5)
            logger.info(f"📊 获取到 {len(recent_chats)} 条最近对话")
            
            for i, chat in enumerate(recent_chats):
                logger.info(f"  记录 {i+1}:")
                logger.info(f"    chat_id: '{chat.get('chat_id', 'EMPTY')}'")
                logger.info(f"    question: {chat.get('question', '')[:50]}...")
                logger.info(f"    answer: {chat.get('answer', '')[:50]}...")
                logger.info(f"    timestamp: {chat.get('timestamp', '')}")
            
            # 3. 检查chat_id是否为空
            logger.info("\n3️⃣ 检查chat_id是否为空")
            empty_count = 0
            for chat in recent_chats:
                if not chat.get('chat_id') or chat.get('chat_id') == '':
                    empty_count += 1
                    logger.warning(f"⚠️ 发现空的chat_id: {chat}")
            
            if empty_count == 0:
                logger.info("✅ 所有chat_id都有值")
            else:
                logger.warning(f"⚠️ 有 {empty_count} 个chat_id为空")
        else:
            logger.warning("⚠️ ES中没有数据，无法测试")
        
        logger.info("\n🎉 测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_real_data()

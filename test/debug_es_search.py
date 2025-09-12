#!/usr/bin/env python3
"""
调试ES搜索逻辑
检查混合搜索是否正常工作
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from models.es_models import ESService
from logging_config import get_logger

logger = get_logger(__name__)

async def debug_es_search():
    """调试ES搜索逻辑"""
    print("🔍 调试ES搜索逻辑...")
    
    # 初始化服务
    memory_service = AsyncMemoryServiceV2()
    es_service = memory_service.es_service
    
    test_user_id = "debug_search_user"
    test_agent_id = "debug_search_agent"
    
    try:
        # 1. 添加一个测试数据
        print("\n📝 添加测试数据...")
        result = await memory_service.add_memory_async(
            user_id=test_user_id,
            agent_id=test_agent_id,
            question="推荐一下有跑道的公园",
            answer="我推荐朝阳公园，那里有很好的跑道，环境优美，适合跑步。"
        )
        
        if result["success"]:
            print("✅ 测试数据添加成功")
        else:
            print(f"❌ 测试数据添加失败: {result.get('error', 'Unknown error')}")
            return
        
        # 等待数据存储完成
        await asyncio.sleep(2)
        
        # 2. 测试纯关键词搜索
        print("\n🔍 测试纯关键词搜索...")
        query = "推荐有跑道的公园"
        keyword_results = es_service.search_similar_chats_by_question_only(
            user_id=test_user_id,
            query=query,
            limit=5
        )
        
        print(f"关键词搜索结果数量: {len(keyword_results)}")
        for i, result in enumerate(keyword_results, 1):
            print(f"  {i}. 问题: {result.get('question', '')}")
            print(f"     分数: {result.get('_score', 0.0)}")
        
        # 3. 测试混合搜索
        print("\n🔍 测试混合搜索...")
        query_embedding = await memory_service.async_get_embedding(query)
        print(f"查询embedding长度: {len(query_embedding) if query_embedding else 0}")
        
        mixed_results = es_service.search_similar_chats(
            user_id=test_user_id,
            query=query,
            embedding=query_embedding,
            agent_id=test_agent_id,
            limit=5
        )
        
        print(f"混合搜索结果数量: {len(mixed_results)}")
        for i, result in enumerate(mixed_results, 1):
            print(f"  {i}. 问题: {result.get('question', '')}")
            print(f"     分数: {result.get('_score', 0.0)}")
        
        # 4. 测试向量搜索
        print("\n🔍 测试纯向量搜索...")
        vector_results = es_service.search_similar_chats_by_embedding_only(
            user_id=test_user_id,
            embedding=query_embedding,
            agent_id=test_agent_id,
            limit=5
        )
        
        print(f"向量搜索结果数量: {len(vector_results)}")
        for i, result in enumerate(vector_results, 1):
            print(f"  {i}. 问题: {result.get('question', '')}")
            print(f"     分数: {result.get('_score', 0.0)}")
        
        # 5. 检查ES索引中的数据
        print("\n🔍 检查ES索引中的数据...")
        all_chats = es_service.get_all_chats(user_id=test_user_id, agent_id=test_agent_id)
        print(f"ES中总共有 {len(all_chats)} 条记录")
        for i, chat in enumerate(all_chats, 1):
            print(f"  {i}. 问题: {chat.get('question', '')}")
            print(f"     embedding长度: {len(chat.get('embedding', []))}")
            print(f"     chat_id: {chat.get('chat_id', '')}")
        
        print("\n✅ 调试完成！")
        
    except Exception as e:
        print(f"❌ 调试失败: {e}")
        logger.error(f"ES搜索调试失败: {e}")
    finally:
        # 清理测试数据
        try:
            await memory_service.clear_all_data_async(user_id=test_user_id, agent_id=test_agent_id)
            print("🧹 测试数据已清理")
        except Exception as e:
            print(f"⚠️  清理测试数据失败: {e}")

if __name__ == "__main__":
    asyncio.run(debug_es_search())

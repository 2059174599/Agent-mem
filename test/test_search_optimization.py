#!/usr/bin/env python3
"""
测试搜索优化效果
验证：1.只使用问题embedding 2.提高精确度 3.减少不相关结果
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from services.llm_service import LLMService
from services.embedding_service import EmbeddingService
from services.unified_cache_service import UnifiedCacheService
from models.es_models import ESService
from logging_config import get_logger

logger = get_logger(__name__)

async def test_search_optimization():
    """测试搜索优化效果"""
    print("🔍 测试搜索优化效果...")
    
    # 初始化服务
    memory_service = AsyncMemoryServiceV2()
    
    test_user_id = "test_search_opt_user"
    test_agent_id = "test_search_opt_agent"
    
    try:
        # 1. 添加测试数据
        print("\n📝 添加测试数据...")
        test_qa_pairs = [
            ("推荐一下有跑道的公园", "我推荐朝阳公园，那里有很好的跑道，环境优美，适合跑步。"),
            ("你好", "你好！我是智语助手，有什么可以帮助您的吗？"),
            ("北京天气怎么样", "北京今天天气晴朗，温度适宜，适合外出。"),
            ("有什么好吃的餐厅推荐", "我推荐海底捞火锅，服务好，味道也不错。"),
            ("跑步有什么好处", "跑步可以增强心肺功能，提高免疫力，还能减肥塑形。"),
            ("公园里有什么设施", "公园通常有健身器材、儿童游乐设施、休息座椅等。")
        ]
        
        for question, answer in test_qa_pairs:
            result = await memory_service.add_memory_async(
                user_id=test_user_id,
                agent_id=test_agent_id,
                question=question,
                answer=answer
            )
            if result["success"]:
                print(f"✅ 添加成功: {question[:20]}...")
            else:
                print(f"❌ 添加失败: {question[:20]}... - {result.get('error', 'Unknown error')}")
        
        # 等待一下确保数据存储完成
        await asyncio.sleep(2)
        
        # 2. 测试搜索精确度
        print("\n🔍 测试搜索精确度...")
        test_queries = [
            "推荐有跑道的公园",  # 应该匹配第一个
            "你好",  # 应该匹配第二个
            "北京天气",  # 应该匹配第三个
            "餐厅推荐",  # 应该匹配第四个
            "跑步的好处",  # 应该匹配第五个
        ]
        
        for query in test_queries:
            print(f"\n查询: '{query}'")
            result = await memory_service.search_memory_async(
                user_id=test_user_id,
                agent_id=test_agent_id,
                query=query,
                limit=3
            )
            
            if result["success"]:
                chats = result.get("chats", [])
                print(f"  找到 {len(chats)} 个相关对话:")
                for i, chat in enumerate(chats, 1):
                    question = chat.get("question", "")
                    answer = chat.get("answer", "")
                    score = chat.get("_score", 0)
                    print(f"    {i}. 问题: {question}")
                    print(f"       答案: {answer[:50]}...")
                    print(f"       相关性分数: {score:.3f}")
            else:
                print(f"  ❌ 搜索失败: {result.get('error', 'Unknown error')}")
        
        # 3. 测试不相关结果过滤
        print("\n🚫 测试不相关结果过滤...")
        irrelevant_queries = [
            "数学公式",  # 应该没有匹配
            "编程代码",  # 应该没有匹配
            "历史事件",  # 应该没有匹配
        ]
        
        for query in irrelevant_queries:
            print(f"\n查询: '{query}' (应该没有相关结果)")
            result = await memory_service.search_memory_async(
                user_id=test_user_id,
                agent_id=test_agent_id,
                query=query,
                limit=3
            )
            
            if result["success"]:
                chats = result.get("chats", [])
                if len(chats) == 0:
                    print(f"  ✅ 正确：没有返回不相关结果")
                else:
                    print(f"  ⚠️  返回了 {len(chats)} 个结果（可能不相关）:")
                    for i, chat in enumerate(chats, 1):
                        question = chat.get("question", "")
                        score = chat.get("_score", 0)
                        print(f"    {i}. {question} (分数: {score:.3f})")
            else:
                print(f"  ❌ 搜索失败: {result.get('error', 'Unknown error')}")
        
        print("\n✅ 搜索优化测试完成！")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        logger.error(f"搜索优化测试失败: {e}")
    finally:
        # 清理测试数据
        try:
            await memory_service.clear_all_data_async(user_id=test_user_id, agent_id=test_agent_id)
            print("🧹 测试数据已清理")
        except Exception as e:
            print(f"⚠️  清理测试数据失败: {e}")

if __name__ == "__main__":
    asyncio.run(test_search_optimization())

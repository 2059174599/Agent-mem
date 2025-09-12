#!/usr/bin/env python3
"""
调试事实搜索问题
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.redis_models import RedisService
from config import Config
from logging_config import get_logger

logger = get_logger(__name__)

async def debug_search_facts():
    """调试事实搜索问题"""
    
    print("🔍 调试事实搜索问题")
    print("=" * 60)
    
    redis_service = RedisService()
    user_id = "test_memory_user_001"
    agent_id = "test_memory_agent_001"
    
    # 1. 查看所有事实
    print("\n📋 查看所有事实")
    print("-" * 30)
    facts = await redis_service.get_facts(user_id, agent_id)
    print(f"总事实数量: {len(facts)}")
    
    for i, fact in enumerate(facts, 1):
        print(f"事实 {i}: {fact.topic} - {fact.sub_topic} - {fact.memo}")
    
    # 2. 查看配置
    print("\n⚙️ 查看搜索配置")
    print("-" * 30)
    search_config = Config.get_search_strategies()
    print(f"redis_return_all_facts: {search_config.get('redis_return_all_facts')}")
    print(f"fact_count_threshold: {search_config.get('fact_count_threshold')}")
    print(f"enable_llm_semantic_search: {search_config.get('enable_llm_semantic_search')}")
    
    # 3. 测试搜索
    print("\n🔍 测试搜索")
    print("-" * 30)
    
    # 搜索生日
    print("搜索: 我的生日是什么时候")
    birthday_facts = await redis_service.search_facts(user_id, "我的生日是什么时候", agent_id)
    print(f"生日搜索结果数量: {len(birthday_facts)}")
    for i, fact in enumerate(birthday_facts, 1):
        print(f"  结果 {i}: {fact.topic} - {fact.sub_topic} - {fact.memo}")
    
    # 搜索颜色
    print("\n搜索: 我最喜欢的颜色")
    color_facts = await redis_service.search_facts(user_id, "我最喜欢的颜色", agent_id)
    print(f"颜色搜索结果数量: {len(color_facts)}")
    for i, fact in enumerate(color_facts, 1):
        print(f"  结果 {i}: {fact.topic} - {fact.sub_topic} - {fact.memo}")
    
    # 4. 测试不同的搜索策略
    print("\n🧪 测试不同搜索策略")
    print("-" * 30)
    
    # 测试关键词搜索
    print("测试关键词搜索:")
    keyword_results = redis_service._keyword_search(facts, "生日")
    print(f"关键词'生日'搜索结果: {len(keyword_results)}")
    for i, fact in enumerate(keyword_results, 1):
        print(f"  结果 {i}: {fact.topic} - {fact.sub_topic} - {fact.memo}")
    
    # 测试主题搜索
    print("\n测试主题搜索:")
    topic_results = redis_service._topic_relevance_search(facts, "生日")
    print(f"主题'生日'搜索结果: {len(topic_results)}")
    for i, fact in enumerate(topic_results, 1):
        print(f"  结果 {i}: {fact.topic} - {fact.sub_topic} - {fact.memo}")
    
    # 测试语义搜索
    print("\n测试语义搜索:")
    semantic_results = redis_service._semantic_relevance_search(facts, "生日")
    print(f"语义'生日'搜索结果: {len(semantic_results)}")
    for i, fact in enumerate(semantic_results, 1):
        print(f"  结果 {i}: {fact.topic} - {fact.sub_topic} - {fact.memo}")

async def main():
    """主函数"""
    try:
        await debug_search_facts()
        print("\n🎉 调试完成！")
    except Exception as e:
        print(f"\n❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

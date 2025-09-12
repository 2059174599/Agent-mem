#!/usr/bin/env python3
"""
调试记忆持久化问题
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from logging_config import get_logger

logger = get_logger(__name__)

async def debug_persistence_issue():
    """调试记忆持久化问题"""
    
    print("🔍 调试记忆持久化问题")
    print("=" * 60)
    
    async with AsyncMemoryServiceV2() as memory_service:
        user_id = "test_memory_user_001"
        agent_id = "test_memory_agent_001"
        
        # 1. 添加记忆
        print("\n📝 添加记忆测试")
        print("-" * 30)
        
        # 添加生日记忆
        result1 = await memory_service.add_memory_async(
            user_id=user_id,
            agent_id=agent_id,
            question="我的生日是6月15日",
            answer="我出生于1990年6月15日，是双子座。"
        )
        print(f"生日记忆添加结果: {result1}")
        
        # 添加颜色记忆
        result2 = await memory_service.add_memory_async(
            user_id=user_id,
            agent_id=agent_id,
            question="我最喜欢的颜色是蓝色",
            answer="蓝色让我感到平静和放松，我的很多衣服都是蓝色的。"
        )
        print(f"颜色记忆添加结果: {result2}")
        
        # 2. 直接查看Redis中的事实
        print("\n🔍 查看Redis中的事实")
        print("-" * 30)
        
        from models.redis_models import RedisService
        redis_service = RedisService()
        facts = await redis_service.get_facts(user_id, agent_id)
        print(f"Redis中事实数量: {len(facts)}")
        
        for i, fact in enumerate(facts, 1):
            print(f"事实 {i}: {fact.topic} - {fact.sub_topic} - {fact.memo}")
        
        # 3. 搜索测试
        print("\n🔍 搜索测试")
        print("-" * 30)
        
        # 搜索生日
        search_result1 = await memory_service.search_memory_async(
            user_id=user_id,
            agent_id=agent_id,
            query="我的生日是什么时候"
        )
        print(f"生日搜索结果: {search_result1}")
        
        # 搜索颜色
        search_result2 = await memory_service.search_memory_async(
            user_id=user_id,
            agent_id=agent_id,
            query="我最喜欢的颜色"
        )
        print(f"颜色搜索结果: {search_result2}")
        
        # 4. 分析搜索结果
        print("\n📊 分析搜索结果")
        print("-" * 30)
        
        def analyze_facts(facts, expected_keywords):
            """分析事实内容"""
            if not facts:
                return "没有事实"
            
            analysis = []
            for fact in facts:
                fact_text = f"{fact.get('topic', '')} {fact.get('sub_topic', '')} {fact.get('memo', '')}"
                found_keywords = []
                for keyword in expected_keywords:
                    if keyword.lower() in fact_text.lower():
                        found_keywords.append(keyword)
                analysis.append(f"事实: {fact_text} | 匹配关键词: {found_keywords}")
            
            return analysis
        
        # 分析生日搜索结果
        facts1 = search_result1.get("facts", [])
        print("生日搜索事实分析:")
        for line in analyze_facts(facts1, ["6月15日", "生日"]):
            print(f"  {line}")
        
        # 分析颜色搜索结果
        facts2 = search_result2.get("facts", [])
        print("\n颜色搜索事实分析:")
        for line in analyze_facts(facts2, ["蓝色", "颜色"]):
            print(f"  {line}")
        
        # 5. 检查事实提取过程
        print("\n🔍 检查事实提取过程")
        print("-" * 30)
        
        from services.fact_extraction_service import FactExtractionService
        async with FactExtractionService() as fact_service:
            # 测试生日问题的事实提取
            fact_result1 = await fact_service.extract_facts_two_stage(
                user_id=user_id,
                agent_id=agent_id,
                question="我的生日是6月15日",
                answer="我出生于1990年6月15日，是双子座。",
                chat_id="debug_001"
            )
            print(f"生日事实提取结果: {fact_result1}")
            
            # 测试颜色问题的事实提取
            fact_result2 = await fact_service.extract_facts_two_stage(
                user_id=user_id,
                agent_id=agent_id,
                question="我最喜欢的颜色是蓝色",
                answer="蓝色让我感到平静和放松，我的很多衣服都是蓝色的。",
                chat_id="debug_002"
            )
            print(f"颜色事实提取结果: {fact_result2}")

async def main():
    """主函数"""
    try:
        await debug_persistence_issue()
        print("\n🎉 调试完成！")
    except Exception as e:
        print(f"\n❌ 调试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

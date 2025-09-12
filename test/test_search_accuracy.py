#!/usr/bin/env python3
"""
测试搜索准确性 - 验证不同查询的搜索效果
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

async def test_search_accuracy():
    """测试搜索准确性"""
    logger.info("🧪 开始测试搜索准确性")
    
    user_id = "44e8e103-efed-4a48-94ad-1b1d0ac0548a"
    
    # 测试用例：查询 -> 期望的相关结果
    test_cases = [
        {
            "query": "推荐一下有跑道的公园",
            "expected_related": ["推荐一下有跑道的公园", "我喜欢跑步，在昌平居住"],
            "expected_unrelated": ["北京", "天气"]
        },
        {
            "query": "北京",
            "expected_related": ["北京"],
            "expected_unrelated": ["推荐一下有跑道的公园", "天气", "我喜欢跑步，在昌平居住"]
        },
        {
            "query": "天气",
            "expected_related": ["天气"],
            "expected_unrelated": ["推荐一下有跑道的公园", "北京", "我喜欢跑步，在昌平居住"]
        },
        {
            "query": "跑步",
            "expected_related": ["我喜欢跑步，在昌平居住", "推荐一下有跑道的公园"],
            "expected_unrelated": ["北京", "天气"]
        }
    ]
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            for i, test_case in enumerate(test_cases, 1):
                query = test_case["query"]
                expected_related = test_case["expected_related"]
                expected_unrelated = test_case["expected_unrelated"]
                
                logger.info(f"\n{i}️⃣ 测试查询: '{query}'")
                
                # 测试异步搜索方法
                result = await memory_service._search_chats_async(user_id, query, None, 10)
                
                if result.get("success"):
                    chats = result.get("chats", [])
                    questions = [chat.get("question", "") for chat in chats]
                    
                    logger.info(f"📊 搜索返回 {len(chats)} 条记录")
                    for j, chat in enumerate(chats):
                        logger.info(f"  结果 {j+1}: {chat.get('question', '')}")
                    
                    # 检查相关结果
                    related_found = []
                    for expected in expected_related:
                        if any(expected in q for q in questions):
                            related_found.append(expected)
                    
                    # 检查不相关结果
                    unrelated_found = []
                    for expected in expected_unrelated:
                        if any(expected in q for q in questions):
                            unrelated_found.append(expected)
                    
                    # 评估结果
                    logger.info(f"✅ 找到相关结果: {related_found}")
                    if unrelated_found:
                        logger.warning(f"⚠️ 找到不相关结果: {unrelated_found}")
                    else:
                        logger.info("✅ 没有不相关结果")
                    
                    # 计算准确性
                    related_accuracy = len(related_found) / len(expected_related) * 100
                    unrelated_accuracy = (len(expected_unrelated) - len(unrelated_found)) / len(expected_unrelated) * 100
                    overall_accuracy = (related_accuracy + unrelated_accuracy) / 2
                    
                    logger.info(f"📈 准确性评估:")
                    logger.info(f"  相关结果准确性: {related_accuracy:.1f}%")
                    logger.info(f"  不相关结果过滤: {unrelated_accuracy:.1f}%")
                    logger.info(f"  总体准确性: {overall_accuracy:.1f}%")
                    
                else:
                    logger.error(f"❌ 搜索失败: {result}")
        
        logger.info("\n🎉 搜索准确性测试完成")
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search_accuracy())

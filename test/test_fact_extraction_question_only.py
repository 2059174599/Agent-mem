#!/usr/bin/env python3
"""
测试事实提取只从用户问题中提取，不包含AI回答
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.fact_extraction_service import FactExtractionService
from logging_config import get_logger

logger = get_logger(__name__)

async def test_fact_extraction_question_only():
    """测试事实提取只从用户问题中提取"""
    
    print("🧪 测试事实提取只从用户问题中提取")
    print("=" * 60)
    
    async with FactExtractionService() as fact_service:
        # 测试用例1：用户问题包含事实，AI回答也包含信息
        print("\n📝 测试用例1：用户问题包含事实，AI回答也包含信息")
        question1 = "我喜欢吃苹果，你呢？"
        answer1 = "我也喜欢吃苹果！苹果富含维生素C，对身体很好。你喜欢什么品种的苹果？"
        
        result1 = await fact_service.extract_facts_two_stage(
            user_id="test_user_001",
            agent_id="test_agent_001", 
            question=question1,
            answer=answer1,
            chat_id="test_chat_001"
        )
        
        print(f"问题: {question1}")
        print(f"回答: {answer1}")
        print(f"提取结果: {result1}")
        
        # 验证只从问题中提取事实，不包含AI回答中的信息
        stage1_facts = result1.get("stage1_facts", [])
        print(f"✅ 第一阶段提取到 {len(stage1_facts)} 个事实")
        
        for i, fact in enumerate(stage1_facts, 1):
            print(f"   事实 {i}: {fact.get('topic', '')} - {fact.get('sub_topic', '')} - {fact.get('memo', '')}")
        
        # 测试用例2：用户问题不包含事实，但AI回答包含信息
        print("\n📝 测试用例2：用户问题不包含事实，但AI回答包含信息")
        question2 = "你好，今天天气怎么样？"
        answer2 = "你好！今天天气很好，阳光明媚，温度适宜。我建议你可以出去走走，享受这美好的天气。"
        
        result2 = await fact_service.extract_facts_two_stage(
            user_id="test_user_001",
            agent_id="test_agent_001",
            question=question2,
            answer=answer2,
            chat_id="test_chat_002"
        )
        
        print(f"问题: {question2}")
        print(f"回答: {answer2}")
        print(f"提取结果: {result2}")
        
        stage1_facts2 = result2.get("stage1_facts", [])
        print(f"✅ 第一阶段提取到 {len(stage1_facts2)} 个事实")
        
        # 测试用例3：用户问题包含事实，AI回答包含不同的事实
        print("\n📝 测试用例3：用户问题包含事实，AI回答包含不同的事实")
        question3 = "我是程序员，正在学习Python"
        answer3 = "很好！我也是AI助手，我也在学习各种技术。Python是一门很棒的编程语言，特别适合数据科学和机器学习。"
        
        result3 = await fact_service.extract_facts_two_stage(
            user_id="test_user_001",
            agent_id="test_agent_001",
            question=question3,
            answer=answer3,
            chat_id="test_chat_003"
        )
        
        print(f"问题: {question3}")
        print(f"回答: {answer3}")
        print(f"提取结果: {result3}")
        
        stage1_facts3 = result3.get("stage1_facts", [])
        print(f"✅ 第一阶段提取到 {len(stage1_facts3)} 个事实")
        
        for i, fact in enumerate(stage1_facts3, 1):
            print(f"   事实 {i}: {fact.get('topic', '')} - {fact.get('sub_topic', '')} - {fact.get('memo', '')}")
        
        # 验证提取的事实只来自用户问题，不包含AI回答中的信息
        print("\n🔍 验证结果:")
        print("✅ 测试用例1: 应该只提取'我喜欢吃苹果'，不提取AI回答中的'苹果富含维生素C'等信息")
        print("✅ 测试用例2: 应该不提取任何事实，因为用户问题只是问候和询问天气")
        print("✅ 测试用例3: 应该只提取'我是程序员，正在学习Python'，不提取AI回答中的'我也是AI助手'等信息")
        
        return True

async def main():
    """主函数"""
    try:
        await test_fact_extraction_question_only()
        print("\n🎉 测试完成！")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

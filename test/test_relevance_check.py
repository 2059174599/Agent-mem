#!/usr/bin/env python3
"""
相关性检查测试
测试答案与问题的相关性检查功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from config import Config

async def test_relevance_check():
    """测试相关性检查功能"""
    print("=" * 60)
    print("相关性检查测试")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "name": "高度相关",
            "question": "你喜欢什么运动？",
            "answer": "我喜欢跑步和游泳，这些运动对身体健康很有好处。",
            "expected_min": 0.2
        },
        {
            "name": "中等相关",
            "question": "今天天气怎么样？",
            "answer": "今天天气不错，阳光明媚，适合外出。",
            "expected_min": 0.2
        },
        {
            "name": "低相关",
            "question": "你喜欢什么颜色？",
            "answer": "今天中午吃了面条，味道还不错。",
            "expected_min": 0.0,
            "expected_max": 0.3
        },
        {
            "name": "完全不相关",
            "question": "你的名字是什么？",
            "answer": "嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯",
            "expected_min": 0.0,
            "expected_max": 0.2
        },
        {
            "name": "部分相关",
            "question": "请介绍一下Python编程语言",
            "answer": "Python是一种编程语言，它有很多优点。",
            "expected_min": 0.3
        },
        {
            "name": "空问题",
            "question": "",
            "answer": "这是一个答案。",
            "expected_min": 0.4,
            "expected_max": 0.6
        },
        {
            "name": "空答案",
            "question": "你好吗？",
            "answer": "",
            "expected_min": 0.0,
            "expected_max": 0.2
        },
        {
            "name": "关键词匹配",
            "question": "你喜欢看电影吗？",
            "answer": "是的，我经常看电影，特别是科幻片。",
            "expected_min": 0.2
        },
        {
            "name": "同义词相关",
            "question": "你的职业是什么？",
            "answer": "我是一名软件工程师，主要从事后端开发工作。",
            "expected_min": 0.05
        },
        {
            "name": "长文本相关",
            "question": "请解释一下机器学习的基本概念",
            "answer": "机器学习是人工智能的一个分支，它通过算法让计算机从数据中学习模式，而不需要明确编程。主要包括监督学习、无监督学习和强化学习三种类型。",
            "expected_min": 0.2
        }
    ]
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            print(f"测试配置:")
            quality_config = Config.get_quality_check_config()
            print(f"  最小相关性分数: {quality_config['min_relevance_score']}")
            print()
            
            passed_tests = 0
            total_tests = len(test_cases)
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"测试用例 {i}: {test_case['name']}")
                print(f"  问题: {test_case['question']}")
                print(f"  答案: {test_case['answer']}")
                
                # 调用相关性检查方法
                relevance_score = await memory_service._check_relevance(
                    test_case['question'], 
                    test_case['answer']
                )
                
                print(f"  相关性分数: {relevance_score:.3f}")
                
                # 判断测试是否通过
                test_passed = True
                if 'expected_min' in test_case:
                    if relevance_score < test_case['expected_min']:
                        test_passed = False
                        print(f"  ❌ 分数过低，期望 >= {test_case['expected_min']}")
                
                if 'expected_max' in test_case:
                    if relevance_score > test_case['expected_max']:
                        test_passed = False
                        print(f"  ❌ 分数过高，期望 <= {test_case['expected_max']}")
                
                if test_passed:
                    print(f"  ✅ 测试通过")
                    passed_tests += 1
                else:
                    print(f"  ❌ 测试失败")
                
                print("-" * 40)
            
            # 测试总结
            print(f"\n测试总结:")
            print(f"  总测试数: {total_tests}")
            print(f"  通过数: {passed_tests}")
            print(f"  失败数: {total_tests - passed_tests}")
            print(f"  通过率: {passed_tests/total_tests*100:.1f}%")
            
            # 测试边界情况
            print(f"\n边界情况测试:")
            print("=" * 40)
            
            edge_cases = [
                ("重复词汇", "你好你好你好", "你好", 0.5),
                ("特殊字符", "你好！@#$%", "你好", 0.5),
                ("数字", "123456", "123", 0.5),
                ("英文", "Hello world", "Hello", 0.5),
                ("混合语言", "你好Hello", "Hello你好", 0.5)
            ]
            
            for case_name, question, answer, expected_range in edge_cases:
                score = await memory_service._check_relevance(question, answer)
                print(f"  {case_name}: {score:.3f} (期望: {expected_range})")
                if abs(score - expected_range) < 0.3:  # 允许一定误差
                    print(f"    ✅ 在合理范围内")
                else:
                    print(f"    ❌ 超出预期范围")
    
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_relevance_check())

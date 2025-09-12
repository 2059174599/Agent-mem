#!/usr/bin/env python3
"""
LLM质量检查测试
测试使用LLM进行答案质量评估的功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from config import Config

async def test_llm_quality_check():
    """测试LLM质量检查功能"""
    print("=" * 60)
    print("LLM质量检查测试")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "name": "高质量回答",
            "question": "请介绍一下Python编程语言",
            "answer": "Python是一种高级编程语言，由Guido van Rossum在1991年创建。它具有简洁的语法、强大的标准库和丰富的第三方库生态系统。Python广泛应用于Web开发、数据科学、人工智能、自动化脚本等领域。",
            "expected_min": 0.7
        },
        {
            "name": "中等质量回答",
            "question": "你喜欢什么运动？",
            "answer": "我喜欢跑步和游泳，这些运动对身体健康很有好处。",
            "expected_min": 0.5
        },
        {
            "name": "低质量回答",
            "question": "请解释一下机器学习",
            "answer": "机器学习就是让机器学习。",
            "expected_min": 0.2,
            "expected_max": 0.6
        },
        {
            "name": "答非所问",
            "question": "今天天气怎么样？",
            "answer": "我喜欢吃苹果，苹果很甜。",
            "expected_min": 0.0,
            "expected_max": 0.3
        },
        {
            "name": "重复内容",
            "question": "你好",
            "answer": "你好你好你好你好你好你好你好你好你好你好",
            "expected_min": 0.0,
            "expected_max": 0.4
        },
        {
            "name": "语气助词",
            "question": "请介绍一下自己",
            "answer": "嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯",
            "expected_min": 0.0,
            "expected_max": 0.2
        },
        {
            "name": "空回答",
            "question": "你好吗？",
            "answer": "",
            "expected_min": 0.0,
            "expected_max": 0.2
        },
        {
            "name": "短回答",
            "question": "你的名字是什么？",
            "answer": "张三",
            "expected_min": 0.4
        },
        {
            "name": "完整回答",
            "question": "如何学习编程？",
            "answer": "学习编程需要掌握基础知识、多实践、阅读代码、参与项目。建议从基础语法开始，逐步学习算法和数据结构，最后学习框架和工具。",
            "expected_min": 0.6
        },
        {
            "name": "逻辑混乱",
            "question": "什么是人工智能？",
            "answer": "人工智能就是机器人，机器人会说话，说话需要嘴巴，嘴巴在脸上，脸上有眼睛，眼睛看东西，东西在桌子上。",
            "expected_min": 0.0,
            "expected_max": 0.3
        }
    ]
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            print(f"测试配置:")
            quality_config = Config.get_quality_check_config()
            print(f"  最小LLM评分: {quality_config['min_llm_score']}")
            print()
            
            passed_tests = 0
            total_tests = len(test_cases)
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"测试用例 {i}: {test_case['name']}")
                print(f"  问题: {test_case['question']}")
                print(f"  答案: {test_case['answer'][:50]}{'...' if len(test_case['answer']) > 50 else ''}")
                
                # 调用LLM质量检查方法
                quality_score = await memory_service._llm_quality_check(
                    test_case['question'], 
                    test_case['answer']
                )
                
                print(f"  LLM质量分数: {quality_score:.3f}")
                
                # 判断测试是否通过
                test_passed = True
                if 'expected_min' in test_case:
                    if quality_score < test_case['expected_min']:
                        test_passed = False
                        print(f"  ❌ 分数过低，期望 >= {test_case['expected_min']}")
                
                if 'expected_max' in test_case:
                    if quality_score > test_case['expected_max']:
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
                ("特殊字符", "你好！@#$%", "你好！@#$%", 0.0, 1.0),
                ("数字", "123456", "123456", 0.0, 1.0),
                ("英文", "Hello world", "Hello world", 0.0, 1.0),
                ("混合语言", "你好Hello", "你好Hello", 0.0, 1.0),
                ("长文本", "这是一个很长的文本" * 10, "这是一个很长的文本" * 10, 0.0, 1.0)
            ]
            
            for case_name, question, answer, expected_min, expected_max in edge_cases:
                score = await memory_service._llm_quality_check(question, answer)
                print(f"  {case_name}: {score:.3f} (期望: {expected_min}-{expected_max})")
                if expected_min <= score <= expected_max:
                    print(f"    ✅ 在合理范围内")
                else:
                    print(f"    ❌ 超出预期范围")
    
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_quality_check())

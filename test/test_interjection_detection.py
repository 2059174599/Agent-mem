#!/usr/bin/env python3
"""
语气助词检测测试
测试答案质量检测中的语气助词识别功能
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from config import Config

async def test_interjection_detection():
    """测试语气助词检测功能"""
    print("=" * 60)
    print("语气助词检测测试")
    print("=" * 60)
    
    # 测试用例
    test_cases = [
        {
            "name": "正常回答",
            "question": "你好，请介绍一下自己",
            "answer": "你好！智语助手在此，有什么可以帮您的吗？",
            "expected": False  # 不应该被识别为语气助词
        },
        {
            "name": "纯语气助词",
            "question": "你觉得怎么样？",
            "answer": "嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯",
            "expected": True  # 应该被识别为语气助词
        },
        {
            "name": "混合内容（语气助词较多）",
            "question": "请回答这个问题",
            "answer": "嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯好的好的好的",
            "expected": True  # 语气助词超过70%
        },
        {
            "name": "混合内容（语气助词较少）",
            "question": "请回答这个问题",
            "answer": "嗯嗯好的，我来回答这个问题。这是一个很好的问题，让我详细解释一下。",
            "expected": False  # 语气助词不超过70%
        },
        {
            "name": "短回答",
            "question": "你好",
            "answer": "嗯嗯",
            "expected": True  # 短回答且只有语气助词
        },
        {
            "name": "正常短回答",
            "question": "你好",
            "answer": "你好！",
            "expected": False  # 正常短回答
        }
    ]
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            print(f"测试配置:")
            quality_config = Config.get_quality_check_config()
            print(f"  质量检测启用: {quality_config['enabled']}")
            print(f"  最大语气助词比例: {quality_config['max_interjection_ratio']}")
            print(f"  最小答案长度: {quality_config['min_answer_length']}")
            print()
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"测试用例 {i}: {test_case['name']}")
                print(f"  问题: {test_case['question']}")
                print(f"  答案: {test_case['answer']}")
                
                # 直接调用语气助词检测方法
                is_interjection = memory_service._is_only_interjections(
                    test_case['answer'], 
                    quality_config['max_interjection_ratio']
                )
                
                print(f"  检测结果: {'是语气助词' if is_interjection else '不是语气助词'}")
                print(f"  期望结果: {'是语气助词' if test_case['expected'] else '不是语气助词'}")
                
                # 判断测试是否通过
                if is_interjection == test_case['expected']:
                    print(f"  ✅ 测试通过")
                else:
                    print(f"  ❌ 测试失败")
                
                print("-" * 40)
            
            # 测试完整的质量检测流程
            print("\n完整质量检测流程测试:")
            print("=" * 40)
            
            for i, test_case in enumerate(test_cases[:3], 1):  # 只测试前3个用例
                print(f"\n完整测试 {i}: {test_case['name']}")
                
                result = await memory_service.add_memory_async(
                    f"test_user_{i}", 
                    f"test_agent_{i}", 
                    test_case['question'], 
                    test_case['answer']
                )
                
                print(f"  添加结果: {'成功' if result.get('success') else '失败'}")
                if result.get('quality_check'):
                    quality_check = result['quality_check']
                    print(f"  质量检查: {quality_check['reason']}")
                    print(f"  质量分数: {quality_check['score']:.2f}")
                
                print("-" * 40)
    
    except Exception as e:
        print(f"测试异常: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_interjection_detection())

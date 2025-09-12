#!/usr/bin/env python3
"""
记忆功能测试运行器
统一运行所有记忆相关的测试
"""

import asyncio
import sys
import os
import subprocess

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_test_file(test_file: str, test_name: str) -> bool:
    """运行单个测试文件"""
    print(f"\n{'='*20} {test_name} {'='*20}")
    try:
        result = subprocess.run([
            sys.executable, test_file
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 运行 {test_name} 失败: {e}")
        return False

def main():
    """主函数"""
    print("🧪 记忆功能测试运行器")
    print("=" * 50)
    
    # 定义所有测试
    tests = [
        ("test_memory_quick.py", "快速记忆测试"),
        ("test_similar_qa_recall.py", "相似问答召回测试"),
        ("test_memory_add_and_search.py", "综合记忆测试"),
        ("test_search_accuracy.py", "搜索准确性测试"),
        ("test_recent_chats_real_data.py", "最近对话测试")
    ]
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        print("请选择测试类型:")
        print("1. quick     - 快速测试（推荐）")
        print("2. similar   - 相似问答召回测试")
        print("3. full      - 综合记忆测试")
        print("4. accuracy  - 搜索准确性测试")
        print("5. recent    - 最近对话测试")
        print("6. all       - 运行所有测试")
        print()
        test_type = input("请输入测试类型 (1-6): ").strip()
        
        if test_type == "1":
            test_type = "quick"
        elif test_type == "2":
            test_type = "similar"
        elif test_type == "3":
            test_type = "full"
        elif test_type == "4":
            test_type = "accuracy"
        elif test_type == "5":
            test_type = "recent"
        elif test_type == "6":
            test_type = "all"
    
    print(f"\n🎯 选择的测试类型: {test_type}")
    print("-" * 50)
    
    success = True
    
    if test_type == "quick":
        success = run_test_file("test/test_memory_quick.py", "快速记忆测试")
    elif test_type == "similar":
        success = run_test_file("test/test_similar_qa_recall.py", "相似问答召回测试")
    elif test_type == "full":
        success = run_test_file("test/test_memory_add_and_search.py", "综合记忆测试")
    elif test_type == "accuracy":
        success = run_test_file("test/test_search_accuracy.py", "搜索准确性测试")
    elif test_type == "recent":
        success = run_test_file("test/test_recent_chats_real_data.py", "最近对话测试")
    elif test_type == "all":
        print("🔄 运行所有测试...")
        success = True
        
        for test_file, test_name in tests:
            test_success = run_test_file(f"test/{test_file}", test_name)
            success = success and test_success
    else:
        print(f"❌ 未知的测试类型: {test_type}")
        print("支持的类型: quick, similar, full, accuracy, recent, all")
        return
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有测试完成！")
    else:
        print("❌ 部分测试失败，请检查错误信息")
    
    print("\n💡 使用说明:")
    print("   python test/run_memory_tests.py quick     # 快速测试")
    print("   python test/run_memory_tests.py similar   # 相似问答召回测试")
    print("   python test/run_memory_tests.py full      # 综合记忆测试")
    print("   python test/run_memory_tests.py accuracy  # 搜索准确性测试")
    print("   python test/run_memory_tests.py recent    # 最近对话测试")
    print("   python test/run_memory_tests.py all       # 所有测试")

if __name__ == "__main__":
    main()

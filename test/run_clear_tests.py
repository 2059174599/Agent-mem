#!/usr/bin/env python3
"""
ES清理API测试运行脚本
提供多种测试选项
"""

import asyncio
import sys
import os
import subprocess

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_quick_test():
    """运行快速测试"""
    print("🚀 运行快速测试...")
    try:
        result = subprocess.run([
            sys.executable, "test/quick_test_clear_api.py"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 快速测试失败: {e}")
        return False

def run_simple_test():
    """运行简单测试"""
    print("🧪 运行简单测试...")
    try:
        result = subprocess.run([
            sys.executable, "test/test_clear_es_simple.py"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 简单测试失败: {e}")
        return False

def run_full_test():
    """运行完整测试"""
    print("🔬 运行完整测试...")
    try:
        result = subprocess.run([
            sys.executable, "test/test_clear_es_api.py"
        ], capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(__file__)))
        
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 完整测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🧪 ES清理API测试运行器")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        print("请选择测试类型:")
        print("1. quick    - 快速测试（推荐）")
        print("2. simple   - 简单测试")
        print("3. full     - 完整测试")
        print("4. all      - 运行所有测试")
        print()
        test_type = input("请输入测试类型 (1-4): ").strip()
        
        if test_type == "1":
            test_type = "quick"
        elif test_type == "2":
            test_type = "simple"
        elif test_type == "3":
            test_type = "full"
        elif test_type == "4":
            test_type = "all"
    
    print(f"\n🎯 选择的测试类型: {test_type}")
    print("-" * 50)
    
    success = True
    
    if test_type == "quick":
        success = run_quick_test()
    elif test_type == "simple":
        success = run_simple_test()
    elif test_type == "full":
        success = run_full_test()
    elif test_type == "all":
        print("🔄 运行所有测试...")
        success = True
        
        print("\n1️⃣ 快速测试")
        success &= run_quick_test()
        
        print("\n2️⃣ 简单测试")
        success &= run_simple_test()
        
        print("\n3️⃣ 完整测试")
        success &= run_full_test()
    else:
        print(f"❌ 未知的测试类型: {test_type}")
        print("支持的类型: quick, simple, full, all")
        return
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 所有测试完成！")
    else:
        print("❌ 部分测试失败，请检查错误信息")
    
    print("\n💡 使用说明:")
    print("   python test/run_clear_tests.py quick    # 快速测试")
    print("   python test/run_clear_tests.py simple   # 简单测试")
    print("   python test/run_clear_tests.py full     # 完整测试")
    print("   python test/run_clear_tests.py all      # 所有测试")

if __name__ == "__main__":
    main()

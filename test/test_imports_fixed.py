#!/usr/bin/env python3
"""
验证所有测试文件的导入是否修复
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """测试所有测试文件的导入"""
    print("🧪 测试所有测试文件的导入")
    
    test_files = [
        "test_clear_es_api.py",
        "test_clear_es_simple.py", 
        "quick_test_clear_api.py",
        "test_recent_chats.py",
        "test_recent_chats_real_data.py"
    ]
    
    success_count = 0
    total_count = len(test_files)
    
    for test_file in test_files:
        try:
            print(f"\n📁 测试 {test_file}...")
            
            # 动态导入测试文件
            module_name = test_file.replace('.py', '')
            exec(f"import {module_name}")
            
            print(f"   ✅ {test_file} 导入成功")
            success_count += 1
            
        except Exception as e:
            print(f"   ❌ {test_file} 导入失败: {e}")
    
    print(f"\n📊 测试结果: {success_count}/{total_count} 个文件导入成功")
    
    if success_count == total_count:
        print("🎉 所有测试文件导入修复完成！")
    else:
        print("⚠️ 部分测试文件仍有导入问题")
    
    return success_count == total_count

if __name__ == "__main__":
    test_imports()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试运行器
集中管理所有测试的执行
"""

import asyncio
import sys
import time
from typing import List, Dict, Any

# 导入测试模块
from test_memory_api import test_basic_memory_operations, test_punctuation_handling, test_synonym_matching
from test_es_index import test_es_operations
from test_cache_operations import test_cache_operations


class TestRunner:
    """测试运行器类"""
    
    def __init__(self):
        self.results = []
        self.start_time = None
        self.end_time = None
    
    def log_test_result(self, test_name: str, success: bool, duration: float, error: str = None):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "duration": duration,
            "error": error,
            "timestamp": time.time()
        }
        self.results.append(result)
        
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} {test_name} ({duration:.2f}秒)")
        if error:
            print(f"    错误: {error}")
    
    async def run_memory_tests(self) -> bool:
        """运行记忆API测试"""
        print("\n🧪 运行记忆API测试...")
        print("-" * 30)
        
        try:
            # 基本功能测试
            start_time = time.time()
            success = await test_basic_memory_operations()
            duration = time.time() - start_time
            self.log_test_result("基本记忆操作", success, duration)
            
            # 标点符号处理测试
            start_time = time.time()
            await test_punctuation_handling()
            duration = time.time() - start_time
            self.log_test_result("标点符号处理", True, duration)
            
            # 同义词匹配测试
            start_time = time.time()
            await test_synonym_matching()
            duration = time.time() - start_time
            self.log_test_result("同义词匹配", True, duration)
            
            return True
        except Exception as e:
            self.log_test_result("记忆API测试", False, 0, str(e))
            return False
    
    def run_es_tests(self) -> bool:
        """运行ES索引测试"""
        print("\n🔍 运行ES索引测试...")
        print("-" * 30)
        
        try:
            start_time = time.time()
            success = test_es_operations()
            duration = time.time() - start_time
            self.log_test_result("ES索引操作", success, duration)
            return success
        except Exception as e:
            self.log_test_result("ES索引测试", False, 0, str(e))
            return False
    
    async def run_cache_tests(self) -> bool:
        """运行缓存操作测试"""
        print("\n🗄️ 运行缓存操作测试...")
        print("-" * 30)
        
        try:
            start_time = time.time()
            success = await test_cache_operations()
            duration = time.time() - start_time
            self.log_test_result("缓存操作", success, duration)
            return success
        except Exception as e:
            self.log_test_result("缓存操作测试", False, 0, str(e))
            return False
    
    def print_summary(self):
        """打印测试总结"""
        if not self.results:
            print("❌ 没有运行任何测试")
            return
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["success"])
        failed_tests = total_tests - passed_tests
        total_duration = sum(r["duration"] for r in self.results)
        
        print("\n" + "=" * 50)
        print("📊 测试总结")
        print("=" * 50)
        print(f"总测试数: {total_tests}")
        print(f"通过: {passed_tests} ✅")
        print(f"失败: {failed_tests} ❌")
        print(f"成功率: {passed_tests/total_tests*100:.1f}%")
        print(f"总耗时: {total_duration:.2f}秒")
        
        if self.start_time and self.end_time:
            print(f"运行时间: {self.end_time - self.start_time:.2f}秒")
        
        # 显示失败的测试
        if failed_tests > 0:
            print("\n❌ 失败的测试:")
            for result in self.results:
                if not result["success"]:
                    print(f"  - {result['test_name']}: {result['error']}")
        
        print("\n" + "=" * 50)
    
    async def run_all_tests(self, include_memory: bool = True, include_es: bool = True, include_cache: bool = True):
        """运行所有测试"""
        self.start_time = time.time()
        
        print("🚀 开始运行所有测试...")
        print("=" * 50)
        
        # 运行记忆API测试
        if include_memory:
            await self.run_memory_tests()
        
        # 运行ES索引测试
        if include_es:
            self.run_es_tests()
        
        # 运行缓存操作测试
        if include_cache:
            await self.run_cache_tests()
        
        self.end_time = time.time()
        self.print_summary()
        
        # 返回是否所有测试都通过
        return all(r["success"] for r in self.results)


async def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="运行记忆系统测试")
    parser.add_argument("--memory", action="store_true", default=True, help="运行记忆API测试")
    parser.add_argument("--es", action="store_true", default=True, help="运行ES索引测试")
    parser.add_argument("--cache", action="store_true", default=True, help="运行缓存操作测试")
    parser.add_argument("--skip-memory", action="store_true", help="跳过记忆API测试")
    parser.add_argument("--skip-es", action="store_true", help="跳过ES索引测试")
    parser.add_argument("--skip-cache", action="store_true", help="跳过缓存操作测试")
    
    args = parser.parse_args()
    
    # 确定要运行的测试
    include_memory = args.memory and not args.skip_memory
    include_es = args.es and not args.skip_es
    include_cache = args.cache and not args.skip_cache
    
    if not any([include_memory, include_es, include_cache]):
        print("❌ 没有选择要运行的测试")
        return 1
    
    # 运行测试
    runner = TestRunner()
    success = await runner.run_all_tests(
        include_memory=include_memory,
        include_es=include_es,
        include_cache=include_cache
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

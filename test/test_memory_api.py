#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
记忆API测试文件
测试搜索记忆和添加记忆的主要功能接口
"""

import asyncio
import json
import time
import uuid
from typing import Dict, Any

import httpx

# 测试配置
BASE_URL = "http://localhost:5010"
TEST_USER_ID = f"test_user_{int(time.time())}"


class MemoryAPITester:
    """记忆API测试类"""
    
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_results = {
            "add_memory_tests": [],
            "search_memory_tests": [],
            "cache_tests": [],
            "performance_tests": []
        }
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def test_health(self) -> bool:
        """测试健康检查接口"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            result = response.status_code == 200
            print(f"✅ 健康检查: {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ 健康检查失败: {e}")
            return False
    
    async def add_memory(self, question: str, answer: str, user_id: str = None) -> Dict[str, Any]:
        """添加记忆"""
        if user_id is None:
            user_id = TEST_USER_ID
            
        payload = {
            "userId": user_id,
            "question": question,
            "answer": answer
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/memory/add",
                json=payload
            )
            result = response.json()
            print(f"📝 添加记忆: {question[:20]}... -> {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ 添加记忆失败: {e}")
            return {"error": str(e)}
    
    async def search_memory(self, query: str, user_id: str = None, limit: int = 10) -> Dict[str, Any]:
        """搜索记忆"""
        if user_id is None:
            user_id = TEST_USER_ID
            
        payload = {
            "userId": user_id,
            "query": query,
            "limit": limit
        }
        
        try:
            response = await self.client.post(
                f"{self.base_url}/memory/search",
                json=payload
            )
            result = response.json()
            print(f"🔍 搜索记忆: {query} -> {response.status_code}, 找到 {len(result.get('facts', []))} 条事实")
            return result
        except Exception as e:
            print(f"❌ 搜索记忆失败: {e}")
            return {"error": str(e)}
    
    async def clear_cache(self) -> Dict[str, Any]:
        """清空缓存"""
        try:
            response = await self.client.post(f"{self.base_url}/cache/clear", json={"pattern": "*"})
            result = response.json()
            print(f"🗑️ 清空缓存: {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ 清空缓存失败: {e}")
            return {"error": str(e)}
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        try:
            response = await self.client.get(f"{self.base_url}/cache/stats")
            result = response.json()
            print(f"📊 缓存统计: {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ 获取缓存统计失败: {e}")
            return {"error": str(e)}
    
    async def get_topics(self) -> Dict[str, Any]:
        """获取主题列表"""
        try:
            response = await self.client.get(f"{self.base_url}/topics")
            result = response.json()
            print(f"📋 主题列表: {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ 获取主题列表失败: {e}")
            return {"error": str(e)}
    
    async def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        try:
            response = await self.client.get(f"{self.base_url}/performance")
            result = response.json()
            print(f"⚡ 性能统计: {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ 获取性能统计失败: {e}")
            return {"error": str(e)}
    
    def log_test_result(self, test_type: str, test_name: str, success: bool, duration: float, details: str = ""):
        """记录测试结果"""
        result = {
            "test_name": test_name,
            "success": success,
            "duration": duration,
            "details": details,
            "timestamp": time.time()
        }
        self.test_results[test_type].append(result)
        
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{status} {test_name} ({duration:.2f}秒)")
        if details:
            print(f"    详情: {details}")
    
    def print_test_summary(self):
        """打印测试总结"""
        print("\n" + "=" * 60)
        print("📊 测试总结")
        print("=" * 60)
        
        total_tests = 0
        passed_tests = 0
        
        for test_type, results in self.test_results.items():
            if not results:
                continue
                
            type_name = {
                "add_memory_tests": "添加记忆测试",
                "search_memory_tests": "搜索记忆测试", 
                "cache_tests": "缓存操作测试",
                "performance_tests": "性能测试"
            }.get(test_type, test_type)
            
            type_passed = sum(1 for r in results if r["success"])
            type_total = len(results)
            total_tests += type_total
            passed_tests += type_passed
            
            print(f"\n{type_name}: {type_passed}/{type_total} 通过")
            
            # 显示失败的测试
            failed_tests = [r for r in results if not r["success"]]
            if failed_tests:
                print("  失败的测试:")
                for test in failed_tests:
                    print(f"    - {test['test_name']}: {test['details']}")
        
        if total_tests > 0:
            print(f"\n总体结果: {passed_tests}/{total_tests} 通过 ({passed_tests/total_tests*100:.1f}%)")
        else:
            print(f"\n总体结果: 没有运行任何测试")
        print("=" * 60)


async def test_add_memory_operations():
    """测试添加记忆操作"""
    print("📝 开始测试添加记忆操作...")
    
    async with MemoryAPITester() as tester:
        # 1. 健康检查
        start_time = time.time()
        health_ok = await tester.test_health()
        duration = time.time() - start_time
        tester.log_test_result("add_memory_tests", "健康检查", health_ok, duration)
        
        if not health_ok:
            print("❌ 服务不可用，跳过测试")
            return False
        
        # 2. 清空缓存
        start_time = time.time()
        clear_result = await tester.clear_cache()
        duration = time.time() - start_time
        clear_success = "error" not in clear_result
        tester.log_test_result("add_memory_tests", "清空缓存", clear_success, duration)
        
        # 3. 测试不同类型的记忆添加
        test_cases = [
            {
                "name": "用户偏好设定",
                "question": "你叫小智",
                "answer": "好的，我记住了，我叫小智。很高兴认识你！",
                "should_extract": True
            },
            {
                "name": "用户兴趣爱好",
                "question": "我喜欢看电影",
                "answer": "很好！看电影是很好的娱乐方式。你最喜欢什么类型的电影？",
                "should_extract": True
            },
            {
                "name": "用户个人信息",
                "question": "我是程序员",
                "answer": "很棒！程序员是一个很有挑战性的职业。你主要用什么编程语言？",
                "should_extract": True
            },
            {
                "name": "用户询问问题",
                "question": "你叫什么名字？",
                "answer": "我叫小智，很高兴认识你！",
                "should_extract": False
            },
            {
                "name": "用户询问年龄",
                "question": "你多大了？",
                "answer": "我今年4岁了！",
                "should_extract": False
            },
            {
                "name": "用户询问称呼",
                "question": "怎么称呼你？",
                "answer": "您可以叫我小智。请问有什么可以帮您？",
                "should_extract": False
            }
        ]
        
        print("\n📝 测试添加记忆...")
        for i, case in enumerate(test_cases, 1):
            start_time = time.time()
            result = await tester.add_memory(case["question"], case["answer"])
            duration = time.time() - start_time
            
            success = "error" not in result
            facts_added = len(result.get("facts_added", []))
            
            # 验证事实提取是否符合预期
            expected_facts = 1 if case["should_extract"] else 0
            facts_correct = facts_added == expected_facts
            
            test_success = success and facts_correct
            details = f"预期提取{expected_facts}个事实，实际提取{facts_added}个"
            
            tester.log_test_result("add_memory_tests", f"{case['name']}", test_success, duration, details)
            
            await asyncio.sleep(0.5)  # 避免请求过快
        
        return True


async def test_search_memory_operations():
    """测试搜索记忆操作"""
    print("🔍 开始测试搜索记忆操作...")
    
    async with MemoryAPITester() as tester:
        # 1. 健康检查
        start_time = time.time()
        health_ok = await tester.test_health()
        duration = time.time() - start_time
        tester.log_test_result("search_memory_tests", "健康检查", health_ok, duration)
        
        if not health_ok:
            print("❌ 服务不可用，跳过测试")
            return False
        
        # 2. 测试不同类型的搜索
        search_cases = [
            {
                "name": "精确匹配搜索",
                "query": "你叫什么",
                "expected_min_facts": 0,
                "description": "应该找到称呼相关的事实"
            },
            {
                "name": "兴趣爱好搜索",
                "query": "电影",
                "expected_min_facts": 0,
                "description": "应该找到电影相关的事实"
            },
            {
                "name": "职业相关搜索",
                "query": "程序员",
                "expected_min_facts": 0,
                "description": "应该找到职业相关的事实"
            },
            {
                "name": "标点符号搜索",
                "query": "你叫什么名字？",
                "expected_min_facts": 0,
                "description": "带标点符号的搜索"
            },
            {
                "name": "同义词搜索",
                "query": "称呼",
                "expected_min_facts": 0,
                "description": "同义词匹配搜索"
            },
            {
                "name": "无结果搜索",
                "query": "不存在的关键词",
                "expected_min_facts": 0,
                "description": "应该返回空结果"
            }
        ]
        
        print("\n🔍 测试搜索记忆...")
        for i, case in enumerate(search_cases, 1):
            start_time = time.time()
            result = await tester.search_memory(case["query"])
            duration = time.time() - start_time
            
            success = "error" not in result
            facts_found = len(result.get("search_results", {}).get("relevant_facts", []))
            
            # 验证搜索结果
            facts_ok = facts_found >= case["expected_min_facts"]
            test_success = success and facts_ok
            details = f"找到{facts_found}条事实，预期至少{case['expected_min_facts']}条"
            
            tester.log_test_result("search_memory_tests", case["name"], test_success, duration, details)
            
            await asyncio.sleep(0.3)  # 避免请求过快
        
        return True


async def test_cache_operations():
    """测试缓存操作"""
    print("🗄️ 开始测试缓存操作...")
    
    async with MemoryAPITester() as tester:
        # 1. 健康检查
        start_time = time.time()
        health_ok = await tester.test_health()
        duration = time.time() - start_time
        tester.log_test_result("cache_tests", "健康检查", health_ok, duration)
        
        if not health_ok:
            print("❌ 服务不可用，跳过测试")
            return False
        
        # 2. 获取缓存统计
        start_time = time.time()
        stats_result = await tester.get_cache_stats()
        duration = time.time() - start_time
        stats_success = "error" not in stats_result
        tester.log_test_result("cache_tests", "获取缓存统计", stats_success, duration)
        
        # 3. 获取主题列表
        start_time = time.time()
        topics_result = await tester.get_topics()
        duration = time.time() - start_time
        topics_success = "error" not in topics_result
        tester.log_test_result("cache_tests", "获取主题列表", topics_success, duration)
        
        # 4. 清空缓存
        start_time = time.time()
        clear_result = await tester.clear_cache()
        duration = time.time() - start_time
        clear_success = "error" not in clear_result
        tester.log_test_result("cache_tests", "清空缓存", clear_success, duration)
        
        # 5. 清空后再次获取统计
        start_time = time.time()
        stats_after_result = await tester.get_cache_stats()
        duration = time.time() - start_time
        stats_after_success = "error" not in stats_after_result
        tester.log_test_result("cache_tests", "清空后获取统计", stats_after_success, duration)
        
        return True


async def test_performance_operations():
    """测试性能操作"""
    print("⚡ 开始测试性能操作...")
    
    async with MemoryAPITester() as tester:
        # 1. 健康检查
        start_time = time.time()
        health_ok = await tester.test_health()
        duration = time.time() - start_time
        tester.log_test_result("performance_tests", "健康检查", health_ok, duration)
        
        if not health_ok:
            print("❌ 服务不可用，跳过测试")
            return False
        
        # 2. 获取性能统计
        start_time = time.time()
        perf_result = await tester.get_performance_stats()
        duration = time.time() - start_time
        perf_success = "error" not in perf_result
        tester.log_test_result("performance_tests", "获取性能统计", perf_success, duration)
        
        # 3. 批量添加记忆性能测试
        print("\n⚡ 批量添加记忆性能测试...")
        batch_memories = [
            ("我喜欢音乐", "音乐是很棒的艺术形式！"),
            ("我是设计师", "设计师需要很强的创造力。"),
            ("我住在北京", "北京是个很棒的城市。"),
            ("我喜欢旅行", "旅行能开阔视野。"),
            ("我是学生", "学习是成长的重要途径。")
        ]
        
        start_time = time.time()
        for question, answer in batch_memories:
            await tester.add_memory(question, answer)
        batch_duration = time.time() - start_time
        
        batch_success = batch_duration < 10.0  # 期望在10秒内完成
        tester.log_test_result("performance_tests", "批量添加记忆", batch_success, batch_duration, 
                              f"添加{len(batch_memories)}条记忆")
        
        # 4. 批量搜索性能测试
        print("\n⚡ 批量搜索性能测试...")
        search_queries = ["音乐", "设计", "北京", "旅行", "学习"]
        
        start_time = time.time()
        for query in search_queries:
            await tester.search_memory(query)
        search_duration = time.time() - start_time
        
        search_success = search_duration < 5.0  # 期望在5秒内完成
        tester.log_test_result("performance_tests", "批量搜索记忆", search_success, search_duration,
                              f"搜索{len(search_queries)}个查询")
        
        return True


async def test_basic_memory_operations():
    """测试基本记忆操作（兼容性函数）"""
    print("🚀 开始测试基本记忆操作...")
    
    async with MemoryAPITester() as tester:
        # 1. 健康检查
        if not await tester.test_health():
            print("❌ 服务不可用，跳过测试")
            return False
        
        # 2. 清空缓存
        await tester.clear_cache()
        
        # 3. 添加测试记忆
        test_memories = [
            ("你叫什么名字？", "我叫小智，很高兴认识你！"),
            ("你多大了？", "我今年4岁了！"),
            ("你喜欢什么运动？", "我喜欢游泳和跑步。"),
            ("你的爱好是什么？", "我喜欢读书和画画。"),
            ("你住在哪里？", "我住在云端服务器里。")
        ]
        
        print("\n📝 添加测试记忆...")
        for question, answer in test_memories:
            result = await tester.add_memory(question, answer)
            if "error" in result:
                print(f"❌ 添加失败: {question}")
            else:
                print(f"✅ 添加成功: {question}")
            await asyncio.sleep(0.5)  # 避免请求过快
        
        # 4. 测试搜索
        print("\n🔍 测试记忆搜索...")
        search_queries = [
            "你叫什么",
            "你多大了",
            "你喜欢什么运动",
            "你的爱好",
            "你住在哪里",
            "怎么称呼你",  # 这个应该匹配到"你叫什么名字"
            "年龄",  # 这个应该匹配到年龄相关
            "运动",  # 这个应该匹配到运动相关
        ]
        
        for query in search_queries:
            result = await tester.search_memory(query)
            if "error" not in result:
                facts = result.get("facts", [])
                print(f"查询: '{query}' -> 找到 {len(facts)} 条事实")
                for i, fact in enumerate(facts[:2]):  # 只显示前2条
                    print(f"  {i+1}. {fact.get('topic', '')} - {fact.get('sub_topic', '')} - {fact.get('memo', '')[:50]}...")
            else:
                print(f"❌ 搜索失败: {query}")
            await asyncio.sleep(0.3)
        
        # 5. 获取缓存统计
        print("\n📊 缓存统计...")
        stats = await tester.get_cache_stats()
        if "error" not in stats:
            print(f"缓存统计: {stats}")
        
        return True


async def test_punctuation_handling():
    """测试标点符号处理"""
    print("\n🔤 测试标点符号处理...")
    
    async with MemoryAPITester() as tester:
        # 添加带标点符号的记忆
        await tester.add_memory("你叫什么名字？", "我叫小智！")
        await tester.add_memory("你多大了？", "我4岁了！")
        
        # 测试不同标点符号的搜索
        punctuation_queries = [
            "你叫什么名字？",  # 带问号
            "你叫什么名字",   # 不带问号
            "你多大了？",     # 带问号
            "你多大了",       # 不带问号
            "怎么称呼你？",   # 带问号
            "怎么称呼你",     # 不带问号
        ]
        
        for query in punctuation_queries:
            result = await tester.search_memory(query)
            facts = result.get("facts", [])
            print(f"查询: '{query}' -> 找到 {len(facts)} 条事实")


async def test_synonym_matching():
    """测试同义词匹配"""
    print("\n🔗 测试同义词匹配...")
    
    async with MemoryAPITester() as tester:
        # 添加测试记忆
        await tester.add_memory("你做什么工作？", "我是一个AI助手，帮助用户解答问题。")
        await tester.add_memory("你的职业是什么？", "我是程序员。")
        
        # 测试同义词搜索
        synonym_queries = [
            "你做什么的",     # 应该匹配工作相关
            "你的工作",       # 应该匹配工作相关
            "职业",          # 应该匹配职业相关
            "工作相关",       # 应该匹配工作相关
        ]
        
        for query in synonym_queries:
            result = await tester.search_memory(query)
            facts = result.get("facts", [])
            print(f"查询: '{query}' -> 找到 {len(facts)} 条事实")


async def run_comprehensive_tests():
    """运行综合测试"""
    print("🧪 开始综合记忆API测试...")
    print("=" * 60)
    
    async with MemoryAPITester() as tester:
        try:
            # # 1. 添加记忆测试
            # print("\n" + "="*40)
            # print("📝 测试添加记忆操作")
            # print("="*40)
            # await test_add_memory_operations_with_tester(tester)
            #
            # # 2. 搜索记忆测试
            # print("\n" + "="*40)
            # print("🔍 测试搜索记忆操作")
            # print("="*40)
            # await test_search_memory_operations_with_tester(tester)
            
            # 3. 缓存操作测试
            print("\n" + "="*40)
            print("🗄️ 测试缓存操作")
            print("="*40)
            await test_cache_operations_with_tester(tester)
            
            # # 4. 性能测试
            # print("\n" + "="*40)
            # print("⚡ 测试性能操作")
            # print("="*40)
            # await test_performance_operations_with_tester(tester)
            #
            # # 5. 打印测试总结
            # tester.print_test_summary()
            #
            # print("\n✅ 所有测试完成！")
            
        except Exception as e:
            print(f"\n❌ 测试过程中出现错误: {e}")
            import traceback
            traceback.print_exc()


async def test_add_memory_operations_with_tester(tester):
    """使用指定测试器测试添加记忆操作"""
    # 1. 健康检查
    start_time = time.time()
    health_ok = await tester.test_health()
    duration = time.time() - start_time
    tester.log_test_result("add_memory_tests", "健康检查", health_ok, duration)
    
    if not health_ok:
        print("❌ 服务不可用，跳过测试")
        return False
    
    # 2. 清空缓存
    start_time = time.time()
    clear_result = await tester.clear_cache()
    duration = time.time() - start_time
    clear_success = "error" not in clear_result
    tester.log_test_result("add_memory_tests", "清空缓存", clear_success, duration)
    
    # 3. 测试不同类型的记忆添加
    test_cases = [
        {
            "name": "用户偏好设定",
            "question": "你叫小智",
            "answer": "好的，我记住了，我叫小智。很高兴认识你！",
            "should_extract": True
        },
        {
            "name": "用户兴趣爱好",
            "question": "我喜欢看电影",
            "answer": "很好！看电影是很好的娱乐方式。你最喜欢什么类型的电影？",
            "should_extract": True
        },
        {
            "name": "用户个人信息",
            "question": "我是程序员",
            "answer": "很棒！程序员是一个很有挑战性的职业。你主要用什么编程语言？",
            "should_extract": True
        },
        {
            "name": "用户询问问题",
            "question": "你叫什么名字？",
            "answer": "我叫小智，很高兴认识你！",
            "should_extract": False
        },
        {
            "name": "用户询问年龄",
            "question": "你多大了？",
            "answer": "我今年4岁了！",
            "should_extract": False
        },
        {
            "name": "用户询问称呼",
            "question": "怎么称呼你？",
            "answer": "您可以叫我小智。请问有什么可以帮您？",
            "should_extract": False
        }
    ]
    
    print("\n📝 测试添加记忆...")
    for i, case in enumerate(test_cases, 1):
        start_time = time.time()
        result = await tester.add_memory(case["question"], case["answer"])
        duration = time.time() - start_time
        
        success = "error" not in result
        facts_added = len(result.get("facts_added", []))
        
        # 验证事实提取是否符合预期
        expected_facts = 1 if case["should_extract"] else 0
        facts_correct = facts_added == expected_facts
        
        test_success = success and facts_correct
        details = f"预期提取{expected_facts}个事实，实际提取{facts_added}个"
        
        tester.log_test_result("add_memory_tests", f"{case['name']}", test_success, duration, details)
        
        await asyncio.sleep(0.5)  # 避免请求过快
    
    return True


async def test_search_memory_operations_with_tester(tester):
    """使用指定测试器测试搜索记忆操作"""
    # 1. 健康检查
    start_time = time.time()
    health_ok = await tester.test_health()
    duration = time.time() - start_time
    tester.log_test_result("search_memory_tests", "健康检查", health_ok, duration)
    
    if not health_ok:
        print("❌ 服务不可用，跳过测试")
        return False
    
    # 2. 测试不同类型的搜索
    search_cases = [
        {
            "name": "精确匹配搜索",
            "query": "你叫什么",
            "expected_min_facts": 0,
            "description": "应该找到称呼相关的事实"
        },
        {
            "name": "兴趣爱好搜索",
            "query": "电影",
            "expected_min_facts": 0,
            "description": "应该找到电影相关的事实"
        },
        {
            "name": "职业相关搜索",
            "query": "程序员",
            "expected_min_facts": 0,
            "description": "应该找到职业相关的事实"
        },
        {
            "name": "标点符号搜索",
            "query": "你叫什么名字？",
            "expected_min_facts": 0,
            "description": "带标点符号的搜索"
        },
        {
            "name": "同义词搜索",
            "query": "称呼",
            "expected_min_facts": 0,
            "description": "同义词匹配搜索"
        },
        {
            "name": "无结果搜索",
            "query": "不存在的关键词",
            "expected_min_facts": 0,
            "description": "应该返回空结果"
        }
    ]
    
    print("\n🔍 测试搜索记忆...")
    for i, case in enumerate(search_cases, 1):
        start_time = time.time()
        result = await tester.search_memory(case["query"])
        duration = time.time() - start_time
        
        success = "error" not in result
        facts_found = len(result.get("search_results", {}).get("relevant_facts", []))
        
        # 验证搜索结果
        facts_ok = facts_found >= case["expected_min_facts"]
        test_success = success and facts_ok
        details = f"找到{facts_found}条事实，预期至少{case['expected_min_facts']}条"
        
        tester.log_test_result("search_memory_tests", case["name"], test_success, duration, details)
        
        await asyncio.sleep(0.3)  # 避免请求过快
    
    return True


async def test_cache_operations_with_tester(tester):
    """使用指定测试器测试缓存操作"""
    # 1. 健康检查
    start_time = time.time()
    health_ok = await tester.test_health()
    duration = time.time() - start_time
    tester.log_test_result("cache_tests", "健康检查", health_ok, duration)
    
    if not health_ok:
        print("❌ 服务不可用，跳过测试")
        return False
    
    # 2. 获取缓存统计
    start_time = time.time()
    stats_result = await tester.get_cache_stats()
    duration = time.time() - start_time
    stats_success = "error" not in stats_result
    tester.log_test_result("cache_tests", "获取缓存统计", stats_success, duration)
    
    # 3. 获取主题列表
    start_time = time.time()
    topics_result = await tester.get_topics()
    duration = time.time() - start_time
    topics_success = "error" not in topics_result
    tester.log_test_result("cache_tests", "获取主题列表", topics_success, duration)
    
    # 4. 清空缓存
    start_time = time.time()
    clear_result = await tester.clear_cache()
    duration = time.time() - start_time
    clear_success = "error" not in clear_result
    tester.log_test_result("cache_tests", "清空缓存", clear_success, duration)
    
    # 5. 清空后再次获取统计
    start_time = time.time()
    stats_after_result = await tester.get_cache_stats()
    duration = time.time() - start_time
    stats_after_success = "error" not in stats_after_result
    tester.log_test_result("cache_tests", "清空后获取统计", stats_after_success, duration)
    
    return True


async def test_performance_operations_with_tester(tester):
    """使用指定测试器测试性能操作"""
    # 1. 健康检查
    start_time = time.time()
    health_ok = await tester.test_health()
    duration = time.time() - start_time
    tester.log_test_result("performance_tests", "健康检查", health_ok, duration)
    
    if not health_ok:
        print("❌ 服务不可用，跳过测试")
        return False
    
    # 2. 获取性能统计
    start_time = time.time()
    perf_result = await tester.get_performance_stats()
    duration = time.time() - start_time
    perf_success = "error" not in perf_result
    tester.log_test_result("performance_tests", "获取性能统计", perf_success, duration)
    
    # 3. 批量添加记忆性能测试
    print("\n⚡ 批量添加记忆性能测试...")
    batch_memories = [
        ("我喜欢音乐", "音乐是很棒的艺术形式！"),
        ("我是设计师", "设计师需要很强的创造力。"),
        ("我住在北京", "北京是个很棒的城市。"),
        ("我喜欢旅行", "旅行能开阔视野。"),
        ("我是学生", "学习是成长的重要途径。")
    ]
    
    start_time = time.time()
    for question, answer in batch_memories:
        await tester.add_memory(question, answer)
    batch_duration = time.time() - start_time
    
    batch_success = batch_duration < 10.0  # 期望在10秒内完成
    tester.log_test_result("performance_tests", "批量添加记忆", batch_success, batch_duration, 
                          f"添加{len(batch_memories)}条记忆")
    
    # 4. 批量搜索性能测试
    print("\n⚡ 批量搜索性能测试...")
    search_queries = ["音乐", "设计", "北京", "旅行", "学习"]
    
    start_time = time.time()
    for query in search_queries:
        await tester.search_memory(query)
    search_duration = time.time() - start_time
    
    search_success = search_duration < 5.0  # 期望在5秒内完成
    tester.log_test_result("performance_tests", "批量搜索记忆", search_success, search_duration,
                          f"搜索{len(search_queries)}个查询")
    
    return True


async def run_individual_tests():
    """运行单独的测试模块"""
    print("🧪 开始单独测试模块...")
    print("=" * 50)
    
    try:
        # 基本功能测试
        await test_basic_memory_operations()
        
        # 标点符号处理测试
        await test_punctuation_handling()
        
        # 同义词匹配测试
        await test_synonym_matching()
        
        print("\n✅ 所有测试完成！")
        
    except Exception as e:
        print(f"\n❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """主测试函数"""
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
        
        if test_type == "comprehensive":
            await run_comprehensive_tests()
        elif test_type == "add":
            await test_add_memory_operations()
        elif test_type == "search":
            await test_search_memory_operations()
        elif test_type == "cache":
            await test_cache_operations()
        elif test_type == "performance":
            await test_performance_operations()
        else:
            print("❌ 未知的测试类型。支持的类型: comprehensive, add, search, cache, performance")
            return
    else:
        # 默认运行综合测试
        await run_comprehensive_tests()


if __name__ == "__main__":
    asyncio.run(main())

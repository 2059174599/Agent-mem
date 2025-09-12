#!/usr/bin/env python3
"""
Yaxin Memo 压测脚本 - 20并发测试
测试添加记忆和搜索记忆接口的性能
"""

import asyncio
import aiohttp
import json
import time
import random
import statistics
from typing import List, Dict, Any
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

from logging_config import setup_logging, get_logger

# 设置日志
setup_logging()
logger = get_logger(__name__)

class LoadTester:
    """压测类"""
    
    def __init__(self, base_url: str = "http://localhost:5010", concurrency: int = 20):
        self.base_url = base_url
        self.concurrency = concurrency
        self.test_user_id = f"load_test_user_{int(time.time())}"
        self.test_agent_id = "load_test_agent"
        self.results = {
            "add_memory": [],
            "search_memory": []
        }
    
    def generate_test_data(self, count: int) -> List[Dict[str, str]]:
        """生成测试数据"""
        test_questions = [
            "我喜欢打篮球",
            "我今年25岁",
            "我是一名程序员",
            "我喜欢听音乐",
            "我住在北京",
            "我喜欢吃火锅",
            "我养了一只猫",
            "我喜欢看电影",
            "我会说英语",
            "我喜欢旅游",
            "我每天跑步",
            "我喜欢读书",
            "我会弹吉他",
            "我喜欢画画",
            "我经常加班",
            "我喜欢喝咖啡",
            "我会做菜",
            "我喜欢玩游戏",
            "我有个弟弟",
            "我喜欢春天"
        ]
        
        test_answers = [
            "很好！篮球是很好的运动。",
            "25岁正是青春年华。",
            "程序员是很棒的职业。",
            "音乐可以调节心情。",
            "北京是中国的首都。",
            "火锅很美味。",
            "猫咪很可爱。",
            "电影很有趣。",
            "英语很有用。",
            "旅游可以开阔眼界。",
            "跑步有益健康。",
            "读书增长知识。",
            "吉他很好听。",
            "画画很有艺术感。",
            "工作很重要。",
            "咖啡提神醒脑。",
            "做菜是生活技能。",
            "游戏可以放松。",
            "兄弟情深。",
            "春天很美好。"
        ]
        
        test_data = []
        for i in range(count):
            question = random.choice(test_questions)
            answer = random.choice(test_answers)
            test_data.append({
                "question": f"{question} (测试{i+1})",
                "answer": f"{answer} (回答{i+1})"
            })
        
        return test_data
    
    async def test_add_memory(self, session: aiohttp.ClientSession, test_data: Dict[str, str], test_id: int) -> Dict[str, Any]:
        """测试添加记忆接口"""
        start_time = time.time()
        
        payload = {
            "userId": self.test_user_id,
            "question": test_data["question"],
            "answer": test_data["answer"],
            "agentId": self.test_agent_id
        }
        
        try:
            async with session.post(f"{self.base_url}/memory/add", json=payload) as response:
                end_time = time.time()
                response_time = end_time - start_time
                
                result = await response.json()
                
                return {
                    "test_id": test_id,
                    "status_code": response.status,
                    "response_time": response_time,
                    "success": result.get("success", False),
                    "request_id": result.get("request_id"),
                    "error": result.get("error") if not result.get("success") else None
                }
                
        except Exception as e:
            end_time = time.time()
            return {
                "test_id": test_id,
                "status_code": 0,
                "response_time": end_time - start_time,
                "success": False,
                "request_id": None,
                "error": str(e)
            }
    
    async def test_search_memory(self, session: aiohttp.ClientSession, query: str, test_id: int) -> Dict[str, Any]:
        """测试搜索记忆接口"""
        start_time = time.time()
        
        payload = {
            "userId": self.test_user_id,
            "query": query,
            "agentId": self.test_agent_id,
            "limit": 10
        }
        
        try:
            async with session.post(f"{self.base_url}/memory/search", json=payload) as response:
                end_time = time.time()
                response_time = end_time - start_time
                
                result = await response.json()
                
                # 统计搜索结果
                search_results = result.get("search_results", {})
                facts_count = len(search_results.get("relevant_facts", []))
                chats_count = len(search_results.get("similar_chats", []))
                
                return {
                    "test_id": test_id,
                    "status_code": response.status,
                    "response_time": response_time,
                    "success": result.get("success", False),
                    "facts_count": facts_count,
                    "chats_count": chats_count,
                    "error": result.get("error") if not result.get("success") else None
                }
                
        except Exception as e:
            end_time = time.time()
            return {
                "test_id": test_id,
                "status_code": 0,
                "response_time": end_time - start_time,
                "success": False,
                "facts_count": 0,
                "chats_count": 0,
                "error": str(e)
            }
    
    async def run_add_memory_test(self, test_data: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """运行添加记忆压测"""
        print(f"🚀 开始添加记忆压测 - {len(test_data)} 个请求，{self.concurrency} 并发")
        
        async with aiohttp.ClientSession() as session:
            # 创建信号量限制并发数
            semaphore = asyncio.Semaphore(self.concurrency)
            
            async def limited_test(test_data_item, test_id):
                async with semaphore:
                    return await self.test_add_memory(session, test_data_item, test_id)
            
            # 创建所有任务
            tasks = [
                limited_test(test_data[i], i + 1)
                for i in range(len(test_data))
            ]
            
            # 执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常结果
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "test_id": i + 1,
                        "status_code": 0,
                        "response_time": 0,
                        "success": False,
                        "request_id": None,
                        "error": str(result)
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
    
    async def run_search_memory_test(self, queries: List[str]) -> List[Dict[str, Any]]:
        """运行搜索记忆压测"""
        print(f"🔍 开始搜索记忆压测 - {len(queries)} 个请求，{self.concurrency} 并发")
        
        async with aiohttp.ClientSession() as session:
            # 创建信号量限制并发数
            semaphore = asyncio.Semaphore(self.concurrency)
            
            async def limited_test(query, test_id):
                async with semaphore:
                    return await self.test_search_memory(session, query, test_id)
            
            # 创建所有任务
            tasks = [
                limited_test(queries[i], i + 1)
                for i in range(len(queries))
            ]
            
            # 执行所有任务
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 处理异常结果
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    processed_results.append({
                        "test_id": i + 1,
                        "status_code": 0,
                        "response_time": 0,
                        "success": False,
                        "facts_count": 0,
                        "chats_count": 0,
                        "error": str(result)
                    })
                else:
                    processed_results.append(result)
            
            return processed_results
    
    def analyze_results(self, results: List[Dict[str, Any]], test_type: str) -> Dict[str, Any]:
        """分析测试结果"""
        if not results:
            return {"error": "没有测试结果"}
        
        # 基本统计
        total_requests = len(results)
        successful_requests = sum(1 for r in results if r.get("success", False))
        failed_requests = total_requests - successful_requests
        success_rate = (successful_requests / total_requests) * 100 if total_requests > 0 else 0
        
        # 响应时间统计
        response_times = [r.get("response_time", 0) for r in results if r.get("response_time", 0) > 0]
        
        if response_times:
            avg_response_time = statistics.mean(response_times)
            min_response_time = min(response_times)
            max_response_time = max(response_times)
            median_response_time = statistics.median(response_times)
            
            # 计算P95和P99
            sorted_times = sorted(response_times)
            p95_index = int(len(sorted_times) * 0.95)
            p99_index = int(len(sorted_times) * 0.99)
            p95_response_time = sorted_times[p95_index] if p95_index < len(sorted_times) else max_response_time
            p99_response_time = sorted_times[p99_index] if p99_index < len(sorted_times) else max_response_time
        else:
            avg_response_time = min_response_time = max_response_time = median_response_time = 0
            p95_response_time = p99_response_time = 0
        
        # 状态码统计
        status_codes = {}
        for result in results:
            code = result.get("status_code", 0)
            status_codes[code] = status_codes.get(code, 0) + 1
        
        # 错误统计
        errors = {}
        for result in results:
            if not result.get("success", False) and result.get("error"):
                error = str(result.get("error", "Unknown error"))
                errors[error] = errors.get(error, 0) + 1
        
        analysis = {
            "test_type": test_type,
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": round(success_rate, 2),
            "response_times": {
                "avg": round(avg_response_time, 3),
                "min": round(min_response_time, 3),
                "max": round(max_response_time, 3),
                "median": round(median_response_time, 3),
                "p95": round(p95_response_time, 3),
                "p99": round(p99_response_time, 3)
            },
            "status_codes": status_codes,
            "errors": errors
        }
        
        # 如果是搜索测试，添加搜索结果统计
        if test_type == "search_memory":
            facts_counts = [r.get("facts_count", 0) for r in results]
            chats_counts = [r.get("chats_count", 0) for r in results]
            
            analysis["search_results"] = {
                "avg_facts": round(statistics.mean(facts_counts), 2) if facts_counts else 0,
                "avg_chats": round(statistics.mean(chats_counts), 2) if chats_counts else 0,
                "total_facts": sum(facts_counts),
                "total_chats": sum(chats_counts)
            }
        
        return analysis
    
    def print_results(self, analysis: Dict[str, Any]):
        """打印测试结果"""
        print(f"\n📊 {analysis['test_type']} 测试结果:")
        print("=" * 60)
        print(f"总请求数: {analysis['total_requests']}")
        print(f"成功请求: {analysis['successful_requests']}")
        print(f"失败请求: {analysis['failed_requests']}")
        print(f"成功率: {analysis['success_rate']}%")
        
        print(f"\n⏱️ 响应时间统计:")
        rt = analysis['response_times']
        print(f"  平均响应时间: {rt['avg']}s")
        print(f"  最小响应时间: {rt['min']}s")
        print(f"  最大响应时间: {rt['max']}s")
        print(f"  中位数响应时间: {rt['median']}s")
        print(f"  P95响应时间: {rt['p95']}s")
        print(f"  P99响应时间: {rt['p99']}s")
        
        print(f"\n📈 状态码分布:")
        for code, count in analysis['status_codes'].items():
            print(f"  {code}: {count} 次")
        
        if analysis.get('errors'):
            print(f"\n❌ 错误统计:")
            for error, count in analysis['errors'].items():
                print(f"  {error}: {count} 次")
        
        if analysis.get('search_results'):
            print(f"\n🔍 搜索结果统计:")
            sr = analysis['search_results']
            print(f"  平均事实数: {sr['avg_facts']}")
            print(f"  平均对话数: {sr['avg_chats']}")
            print(f"  总事实数: {sr['total_facts']}")
            print(f"  总对话数: {sr['total_chats']}")
    
    async def run_full_test(self):
        """运行完整压测"""
        print("🎯 开始Yaxin Memo压测 - 20并发")
        print("=" * 60)
        
        # 生成测试数据
        add_test_data = self.generate_test_data(50)  # 50个添加记忆请求
        search_queries = [
            "我喜欢什么",
            "我的个人信息",
            "我的爱好",
            "我的工作",
            "我的生活",
            "我的兴趣",
            "我的技能",
            "我的经历",
            "我的想法",
            "我的计划"
        ] * 5  # 50个搜索请求
        
        # 第一阶段：添加记忆压测
        print("\n🚀 第一阶段：添加记忆压测")
        add_results = await self.run_add_memory_test(add_test_data)
        add_analysis = self.analyze_results(add_results, "add_memory")
        self.print_results(add_analysis)
        
        # 等待一段时间让后台处理完成
        print("\n⏳ 等待后台处理完成...")
        await asyncio.sleep(10)
        
        # 第二阶段：搜索记忆压测
        print("\n🔍 第二阶段：搜索记忆压测")
        search_results = await self.run_search_memory_test(search_queries)
        search_analysis = self.analyze_results(search_results, "search_memory")
        self.print_results(search_analysis)
        
        # 总结
        print("\n" + "=" * 60)
        print("🎉 压测完成！")
        print(f"📊 总体性能:")
        print(f"  添加记忆成功率: {add_analysis['success_rate']}%")
        print(f"  搜索记忆成功率: {search_analysis['success_rate']}%")
        print(f"  添加记忆平均响应时间: {add_analysis['response_times']['avg']}s")
        print(f"  搜索记忆平均响应时间: {search_analysis['response_times']['avg']}s")
        
        # 性能评估
        if add_analysis['success_rate'] >= 95 and search_analysis['success_rate'] >= 95:
            print("✅ 性能表现优秀！")
        elif add_analysis['success_rate'] >= 90 and search_analysis['success_rate'] >= 90:
            print("⚠️ 性能表现良好，但还有优化空间")
        else:
            print("❌ 性能表现需要改进")

async def main():
    """主函数"""
    tester = LoadTester(concurrency=20)
    await tester.run_full_test()

if __name__ == "__main__":
    asyncio.run(main())

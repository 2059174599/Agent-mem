#!/usr/bin/env python3
"""
记忆添加和搜索综合测试
测试同一用户/代理ID添加的事实记忆是否能准确返回，以及相似问答的召回效果
"""

import asyncio
import sys
import os
import time
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from logging_config import get_logger

logger = get_logger(__name__)

class MemoryTestSuite:
    """记忆测试套件"""
    
    def __init__(self):
        self.test_user_id = "test_memory_user_001"
        self.test_agent_id = "test_memory_agent_001"
        self.added_memories = []  # 记录添加的记忆，用于验证搜索效果
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def add_memory(self, question: str, answer: str, user_id: str = None, agent_id: str = None) -> dict:
        """添加记忆"""
        user_id = user_id or self.test_user_id
        agent_id = agent_id or self.test_agent_id
        
        logger.info(f"📝 添加记忆: {question[:50]}...")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service.add_memory_async(
                user_id=user_id,
                agent_id=agent_id,
                question=question,
                answer=answer
            )
            
            if result.get("success"):
                memory_info = {
                    "question": question,
                    "answer": answer,
                    "user_id": user_id,
                    "agent_id": agent_id,
                    "chat_id": result.get("chat_id"),
                    "facts_count": result.get("total_facts", 0)
                }
                self.added_memories.append(memory_info)
                logger.info(f"✅ 记忆添加成功: chat_id={result.get('chat_id')}, 事实数={result.get('total_facts', 0)}")
                return result
            else:
                logger.error(f"❌ 记忆添加失败: {result.get('error')}")
                return result
    
    async def search_memory(self, query: str, user_id: str = None, agent_id: str = None) -> dict:
        """搜索记忆"""
        user_id = user_id or self.test_user_id
        agent_id = agent_id or self.test_agent_id
        
        logger.info(f"🔍 搜索记忆: {query}")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service.search_memory_async(
                user_id=user_id,
                agent_id=agent_id,
                query=query,
                limit=10
            )
            
            if result.get("success"):
                facts = result.get("facts", [])
                chats = result.get("chats", [])
                recent_chats = result.get("recent_chats", [])
                
                logger.info(f"📊 搜索结果: 事实={len(facts)}, 相似对话={len(chats)}, 最近对话={len(recent_chats)}")
                return result
            else:
                logger.error(f"❌ 记忆搜索失败: {result.get('error')}")
                return result
    
    def analyze_search_results(self, query: str, search_result: dict, expected_keywords: list = None) -> dict:
        """分析搜索结果的相关性"""
        if not search_result.get("success"):
            return {"relevance_score": 0, "analysis": "搜索失败"}
        
        facts = search_result.get("facts", [])
        chats = search_result.get("chats", [])
        
        # 分析事实相关性
        fact_relevance = 0
        if facts:
            for fact in facts:
                fact_text = f"{fact.get('topic', '')} {fact.get('sub_topic', '')} {fact.get('memo', '')}"
                if expected_keywords:
                    for keyword in expected_keywords:
                        if keyword.lower() in fact_text.lower():
                            fact_relevance += 1
                            break
        
        # 分析对话相关性
        chat_relevance = 0
        if chats:
            for chat in chats:
                chat_text = f"{chat.get('question', '')} {chat.get('answer', '')}"
                if expected_keywords:
                    for keyword in expected_keywords:
                        if keyword.lower() in chat_text.lower():
                            chat_relevance += 1
                            break
        
        # 计算总体相关性分数
        total_expected = len(expected_keywords) if expected_keywords else 1
        fact_score = fact_relevance / total_expected if total_expected > 0 else 0
        chat_score = chat_relevance / len(chats) if chats else 0
        
        overall_score = (fact_score + chat_score) / 2 if (fact_score > 0 or chat_score > 0) else 0
        
        analysis = {
            "relevance_score": overall_score,
            "fact_relevance": fact_relevance,
            "chat_relevance": chat_relevance,
            "total_facts": len(facts),
            "total_chats": len(chats),
            "analysis": f"事实相关性: {fact_relevance}/{total_expected}, 对话相关性: {chat_relevance}/{len(chats)}"
        }
        
        return analysis

async def test_basic_memory_flow():
    """测试基本记忆流程"""
    logger.info("🧪 测试1: 基本记忆添加和搜索流程")
    
    async with MemoryTestSuite() as test_suite:
        # 1. 添加记忆
        add_result = await test_suite.add_memory(
            question="我喜欢吃苹果",
            answer="苹果是一种很健康的水果，富含维生素C和纤维，对身体健康很有好处。"
        )
        
        if not add_result.get("success"):
            logger.error("❌ 记忆添加失败，跳过后续测试")
            return False
        
        # 等待一下确保数据写入完成
        await asyncio.sleep(2)
        
        # 2. 搜索相关记忆
        search_result = await test_suite.search_memory("我喜欢吃什么水果")
        
        # 3. 分析结果
        analysis = test_suite.analyze_search_results(
            "我喜欢吃什么水果", 
            search_result, 
            ["苹果", "水果", "喜欢"]
        )
        
        logger.info(f"📈 相关性分析: {analysis['analysis']}")
        logger.info(f"📊 总体相关性分数: {analysis['relevance_score']:.2f}")
        
        return analysis['relevance_score'] > 0.3

async def test_specific_user_agent_memory():
    """测试特定用户和代理的记忆隔离"""
    logger.info("🧪 测试2: 特定用户和代理的记忆隔离")
    
    async with MemoryTestSuite() as test_suite:
        # 为不同用户和代理添加不同的记忆
        user1_agent1 = await test_suite.add_memory(
            question="我住在北京",
            answer="北京是中国的首都，有很多历史文化景点。",
            user_id="user_001",
            agent_id="agent_001"
        )
        
        user1_agent2 = await test_suite.add_memory(
            question="我喜欢上海",
            answer="上海是中国的经济中心，有很多现代化的建筑。",
            user_id="user_001", 
            agent_id="agent_002"
        )
        
        user2_agent1 = await test_suite.add_memory(
            question="我住在深圳",
            answer="深圳是中国的科技中心，有很多创新企业。",
            user_id="user_002",
            agent_id="agent_001"
        )
        
        await asyncio.sleep(2)
        
        # 测试用户1代理1的搜索
        result1 = await test_suite.search_memory(
            "我住在哪里",
            user_id="user_001",
            agent_id="agent_001"
        )
        
        # 测试用户1代理2的搜索
        result2 = await test_suite.search_memory(
            "我喜欢哪个城市",
            user_id="user_001",
            agent_id="agent_002"
        )
        
        # 测试用户2代理1的搜索
        result3 = await test_suite.search_memory(
            "我住在哪里",
            user_id="user_002",
            agent_id="agent_001"
        )
        
        # 分析结果
        analysis1 = test_suite.analyze_search_results("我住在哪里", result1, ["北京"])
        analysis2 = test_suite.analyze_search_results("我喜欢哪个城市", result2, ["上海"])
        analysis3 = test_suite.analyze_search_results("我住在哪里", result3, ["深圳"])
        
        logger.info(f"📊 用户1代理1搜索结果: {analysis1['analysis']}")
        logger.info(f"📊 用户1代理2搜索结果: {analysis2['analysis']}")
        logger.info(f"📊 用户2代理1搜索结果: {analysis3['analysis']}")
        
        return all([
            analysis1['relevance_score'] > 0.3,
            analysis2['relevance_score'] > 0.3,
            analysis3['relevance_score'] > 0.3
        ])

async def test_similar_question_recall():
    """测试相似问题的召回效果"""
    logger.info("🧪 测试3: 相似问题召回效果")
    
    async with MemoryTestSuite() as test_suite:
        # 添加一些关于跑步的记忆
        memories = [
            ("我喜欢跑步", "跑步是很好的有氧运动，有助于提高心肺功能。"),
            ("我每天跑步30分钟", "每天跑步30分钟可以保持身体健康，增强体质。"),
            ("我经常在公园跑步", "公园环境好，空气清新，是跑步的好地方。"),
            ("我跑步时听音乐", "听音乐可以让跑步更有趣，提高运动效果。")
        ]
        
        # 添加记忆
        for question, answer in memories:
            await test_suite.add_memory(question, answer)
            await asyncio.sleep(1)  # 避免过快添加
        
        await asyncio.sleep(3)  # 等待所有数据写入完成
        
        # 测试不同的相似问题
        test_queries = [
            ("我有什么运动爱好", ["跑步"]),
            ("我每天做什么运动", ["跑步", "30分钟"]),
            ("我在哪里运动", ["公园"]),
            ("我运动时做什么", ["音乐"]),
            ("我喜欢什么有氧运动", ["跑步"]),
            ("我如何保持健康", ["跑步", "运动"])
        ]
        
        success_count = 0
        for query, expected_keywords in test_queries:
            logger.info(f"\n🔍 测试查询: {query}")
            search_result = await test_suite.search_memory(query)
            analysis = test_suite.analyze_search_results(query, search_result, expected_keywords)
            
            logger.info(f"📊 相关性分析: {analysis['analysis']}")
            logger.info(f"📈 相关性分数: {analysis['relevance_score']:.2f}")
            
            if analysis['relevance_score'] > 0.3:
                success_count += 1
                logger.info("✅ 召回成功")
            else:
                logger.warning("⚠️ 召回效果不佳")
        
        success_rate = success_count / len(test_queries)
        logger.info(f"\n📊 相似问题召回成功率: {success_rate:.1%} ({success_count}/{len(test_queries)})")
        
        return success_rate > 0.6

async def test_fact_extraction_and_search():
    """测试事实提取和搜索效果"""
    logger.info("🧪 测试4: 事实提取和搜索效果")
    
    async with MemoryTestSuite() as test_suite:
        # 添加包含多个事实的复杂记忆
        complex_memories = [
            (
                "我是一名软件工程师，在北京工作，喜欢Python编程，业余时间喜欢打篮球",
                "软件工程师是一个很有挑战性的职业，需要不断学习新技术。Python是一门很实用的编程语言。篮球是很好的团队运动，可以锻炼身体和团队合作能力。"
            ),
            (
                "我养了一只金毛犬，名字叫小白，它很聪明，会很多技能",
                "金毛犬是很温顺的犬种，适合家庭饲养。小白已经3岁了，会握手、坐下、趴下等基本指令，还会接飞盘。"
            ),
            (
                "我最近在学习机器学习，对深度学习很感兴趣，正在看相关书籍",
                "机器学习是人工智能的重要分支，深度学习是其中的热门方向。我正在看《深度学习》这本书，内容很丰富。"
            )
        ]
        
        # 添加复杂记忆
        for question, answer in complex_memories:
            await test_suite.add_memory(question, answer)
            await asyncio.sleep(2)
        
        await asyncio.sleep(5)  # 等待事实提取完成
        
        # 测试不同维度的事实搜索
        fact_tests = [
            ("我的职业是什么", ["软件工程师", "工程师"]),
            ("我在哪里工作", ["北京"]),
            ("我喜欢什么编程语言", ["Python"]),
            ("我有什么爱好", ["篮球", "编程"]),
            ("我养了什么宠物", ["金毛犬", "小白", "狗"]),
            ("我的宠物叫什么名字", ["小白"]),
            ("我在学习什么", ["机器学习", "深度学习"]),
            ("我在看什么书", ["深度学习"])
        ]
        
        success_count = 0
        for query, expected_keywords in fact_tests:
            logger.info(f"\n🔍 测试事实查询: {query}")
            search_result = await test_suite.search_memory(query)
            
            # 重点分析事实部分
            facts = search_result.get("facts", [])
            logger.info(f"📋 提取到的事实数量: {len(facts)}")
            
            for i, fact in enumerate(facts):
                logger.info(f"  事实 {i+1}: {fact.get('topic', '')} - {fact.get('sub_topic', '')} - {fact.get('memo', '')}")
            
            analysis = test_suite.analyze_search_results(query, search_result, expected_keywords)
            logger.info(f"📊 事实相关性: {analysis['analysis']}")
            logger.info(f"📈 相关性分数: {analysis['relevance_score']:.2f}")
            
            if analysis['relevance_score'] > 0.2:  # 事实搜索可以稍微宽松一些
                success_count += 1
                logger.info("✅ 事实提取和搜索成功")
            else:
                logger.warning("⚠️ 事实提取或搜索效果不佳")
        
        success_rate = success_count / len(fact_tests)
        logger.info(f"\n📊 事实提取和搜索成功率: {success_rate:.1%} ({success_count}/{len(fact_tests)})")
        
        return success_rate > 0.5

async def test_memory_persistence():
    """测试记忆持久化"""
    logger.info("🧪 测试5: 记忆持久化测试")
    
    async with MemoryTestSuite() as test_suite:
        # 添加一些记忆
        await test_suite.add_memory(
            "我的生日是6月15日",
            "我出生于1990年6月15日，是双子座。"
        )
        
        await test_suite.add_memory(
            "我最喜欢的颜色是蓝色",
            "蓝色让我感到平静和放松，我的很多衣服都是蓝色的。"
        )
        
        await asyncio.sleep(3)
        
        # 立即搜索
        logger.info("🔍 立即搜索测试")
        immediate_result = await test_suite.search_memory("我的生日是什么时候")
        immediate_analysis = test_suite.analyze_search_results("我的生日是什么时候", immediate_result, ["6月15日", "生日"])
        
        # 等待一段时间后再次搜索
        logger.info("⏰ 等待5秒后再次搜索")
        await asyncio.sleep(5)
        
        delayed_result = await test_suite.search_memory("我最喜欢的颜色")
        delayed_analysis = test_suite.analyze_search_results("我最喜欢的颜色", delayed_result, ["蓝色", "颜色"])
        
        logger.info(f"📊 立即搜索结果: {immediate_analysis['analysis']}")
        logger.info(f"📊 延迟搜索结果: {delayed_analysis['analysis']}")
        
        return immediate_analysis['relevance_score'] > 0.3 and delayed_analysis['relevance_score'] > 0.3

async def run_all_tests():
    """运行所有测试"""
    logger.info("🚀 开始记忆添加和搜索综合测试")
    logger.info("=" * 60)
    
    test_results = []
    
    # 运行所有测试
    tests = [
        ("基本记忆流程", test_basic_memory_flow),
        ("用户代理隔离", test_specific_user_agent_memory),
        ("相似问题召回", test_similar_question_recall),
        ("事实提取搜索", test_fact_extraction_and_search),
        ("记忆持久化", test_memory_persistence)
    ]
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            test_results.append((test_name, result))
            if result:
                logger.info(f"✅ {test_name} 测试通过")
            else:
                logger.warning(f"⚠️ {test_name} 测试未通过")
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
            test_results.append((test_name, False))
    
    # 输出测试总结
    logger.info("\n" + "=" * 60)
    logger.info("📊 测试结果总结")
    logger.info("=" * 60)
    
    passed_count = 0
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        logger.info(f"{test_name}: {status}")
        if result:
            passed_count += 1
    
    success_rate = passed_count / len(test_results)
    logger.info(f"\n📈 总体成功率: {success_rate:.1%} ({passed_count}/{len(test_results)})")
    
    if success_rate >= 0.8:
        logger.info("🎉 测试整体表现优秀！")
    elif success_rate >= 0.6:
        logger.info("👍 测试整体表现良好")
    else:
        logger.warning("⚠️ 测试整体表现需要改进")
    
    return success_rate

if __name__ == "__main__":
    asyncio.run(run_all_tests())

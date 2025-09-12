#!/usr/bin/env python3
"""
相似问答召回测试
专门测试添加记忆后，相似问题能否正确召回相关问答
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from logging_config import get_logger

logger = get_logger(__name__)

class SimilarQATester:
    """相似问答测试器"""
    
    def __init__(self, user_id: str = "similar_qa_user", agent_id: str = "similar_qa_agent"):
        self.user_id = user_id
        self.agent_id = agent_id
        self.added_qa_pairs = []
    
    async def add_qa_pair(self, question: str, answer: str) -> bool:
        """添加问答对"""
        logger.info(f"📝 添加问答: {question}")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service.add_memory_async(
                user_id=self.user_id,
                agent_id=self.agent_id,
                question=question,
                answer=answer
            )
            
            if result.get("success"):
                self.added_qa_pairs.append({
                    "question": question,
                    "answer": answer,
                    "chat_id": result.get("chat_id")
                })
                logger.info(f"✅ 添加成功: chat_id={result.get('chat_id')}")
                return True
            else:
                logger.error(f"❌ 添加失败: {result.get('error')}")
                return False
    
    async def test_similar_query(self, query: str, expected_questions: list, test_name: str) -> dict:
        """测试相似查询"""
        logger.info(f"\n🔍 测试: {test_name}")
        logger.info(f"查询: {query}")
        logger.info(f"期望找到: {expected_questions}")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service.search_memory_async(
                user_id=self.user_id,
                agent_id=self.agent_id,
                query=query,
                limit=10
            )
            
            if not result.get("success"):
                logger.error(f"❌ 搜索失败: {result.get('error')}")
                return {"success": False, "found_questions": [], "recall_rate": 0}
            
            # 分析搜索结果
            chats = result.get("chats", [])
            found_questions = [chat.get("question", "") for chat in chats]
            
            # 计算召回率
            recall_count = 0
            for expected in expected_questions:
                for found in found_questions:
                    if expected.lower() in found.lower() or found.lower() in expected.lower():
                        recall_count += 1
                        break
            
            recall_rate = recall_count / len(expected_questions) if expected_questions else 0
            
            logger.info(f"📊 搜索结果: {len(chats)} 条对话")
            logger.info(f"📋 找到的问题:")
            for i, q in enumerate(found_questions):
                logger.info(f"  {i+1}. {q}")
            
            logger.info(f"📈 召回率: {recall_rate:.1%} ({recall_count}/{len(expected_questions)})")
            
            return {
                "success": True,
                "found_questions": found_questions,
                "recall_rate": recall_rate,
                "total_found": len(chats)
            }

async def test_food_preferences():
    """测试食物偏好相关问答"""
    logger.info("🍎 测试1: 食物偏好相关问答")
    
    tester = SimilarQATester("food_user", "food_agent")
    
    # 添加食物相关的问答
    food_qa_pairs = [
        ("我喜欢吃苹果", "苹果富含维生素C，对健康很有好处。"),
        ("我不喜欢吃香蕉", "香蕉的味道我不太喜欢，但我知道它很有营养。"),
        ("我最喜欢的水果是草莓", "草莓酸甜可口，是我最喜欢的水果。"),
        ("我经常吃蔬菜沙拉", "蔬菜沙拉营养丰富，我每天都会吃一些。"),
        ("我不太喜欢辣的菜", "我的口味比较清淡，不太能吃辣。")
    ]
    
    # 添加问答对
    for question, answer in food_qa_pairs:
        await tester.add_qa_pair(question, answer)
        await asyncio.sleep(1)
    
    await asyncio.sleep(3)  # 等待数据写入完成
    
    # 测试相似查询
    test_cases = [
        ("我喜欢什么水果", ["我喜欢吃苹果", "我最喜欢的水果是草莓"], "水果偏好查询"),
        ("我不喜欢吃什么", ["我不喜欢吃香蕉", "我不太喜欢辣的菜"], "不喜欢食物查询"),
        ("我经常吃什么", ["我经常吃蔬菜沙拉"], "经常吃食物查询"),
        ("我的口味怎么样", ["我不太喜欢辣的菜"], "口味偏好查询"),
        ("我喜欢吃苹果吗", ["我喜欢吃苹果"], "具体水果确认")
    ]
    
    success_count = 0
    for query, expected, name in test_cases:
        result = await tester.test_similar_query(query, expected, name)
        if result["recall_rate"] > 0.5:  # 50%以上召回率认为成功
            success_count += 1
    
    success_rate = success_count / len(test_cases)
    logger.info(f"\n📊 食物偏好测试成功率: {success_rate:.1%}")
    return success_rate > 0.6

async def test_hobby_activities():
    """测试爱好活动相关问答"""
    logger.info("🏃 测试2: 爱好活动相关问答")
    
    tester = SimilarQATester("hobby_user", "hobby_agent")
    
    # 添加爱好相关的问答
    hobby_qa_pairs = [
        ("我喜欢跑步", "跑步是很好的有氧运动，我每天都会跑30分钟。"),
        ("我经常打篮球", "篮球是团队运动，我每周都会和朋友一起打。"),
        ("我喜欢看书", "我特别喜欢科幻小说，最近在看《三体》。"),
        ("我偶尔会画画", "画画可以让我放松心情，虽然画得不太好。"),
        ("我不喜欢游泳", "我不会游泳，也不太喜欢水。")
    ]
    
    # 添加问答对
    for question, answer in hobby_qa_pairs:
        await tester.add_qa_pair(question, answer)
        await asyncio.sleep(1)
    
    await asyncio.sleep(3)
    
    # 测试相似查询
    test_cases = [
        ("我有什么运动爱好", ["我喜欢跑步", "我经常打篮球"], "运动爱好查询"),
        ("我喜欢什么运动", ["我喜欢跑步", "我经常打篮球"], "运动类型查询"),
        ("我有什么阅读习惯", ["我喜欢看书"], "阅读习惯查询"),
        ("我不喜欢什么运动", ["我不喜欢游泳"], "不喜欢运动查询"),
        ("我有什么艺术爱好", ["我偶尔会画画"], "艺术爱好查询")
    ]
    
    success_count = 0
    for query, expected, name in test_cases:
        result = await tester.test_similar_query(query, expected, name)
        if result["recall_rate"] > 0.5:
            success_count += 1
    
    success_rate = success_count / len(test_cases)
    logger.info(f"\n📊 爱好活动测试成功率: {success_rate:.1%}")
    return success_rate > 0.6

async def test_work_study():
    """测试工作学习相关问答"""
    logger.info("💼 测试3: 工作学习相关问答")
    
    tester = SimilarQATester("work_user", "work_agent")
    
    # 添加工作学习相关的问答
    work_qa_pairs = [
        ("我是一名软件工程师", "我在一家互联网公司工作，主要负责后端开发。"),
        ("我在学习Python", "Python是一门很实用的编程语言，我正在深入学习。"),
        ("我最近在学机器学习", "机器学习很有趣，我正在看相关的书籍和教程。"),
        ("我不太擅长数学", "数学对我来说比较困难，但我正在努力改善。"),
        ("我经常加班", "项目比较忙，我经常需要加班到很晚。")
    ]
    
    # 添加问答对
    for question, answer in work_qa_pairs:
        await tester.add_qa_pair(question, answer)
        await asyncio.sleep(1)
    
    await asyncio.sleep(3)
    
    # 测试相似查询
    test_cases = [
        ("我的职业是什么", ["我是一名软件工程师"], "职业查询"),
        ("我在学什么编程语言", ["我在学习Python"], "编程语言查询"),
        ("我在学什么技术", ["我最近在学机器学习"], "技术学习查询"),
        ("我有什么困难", ["我不太擅长数学"], "困难查询"),
        ("我的工作怎么样", ["我经常加班"], "工作情况查询")
    ]
    
    success_count = 0
    for query, expected, name in test_cases:
        result = await tester.test_similar_query(query, expected, name)
        if result["recall_rate"] > 0.5:
            success_count += 1
    
    success_rate = success_count / len(test_cases)
    logger.info(f"\n📊 工作学习测试成功率: {success_rate:.1%}")
    return success_rate > 0.6

async def test_semantic_similarity():
    """测试语义相似性"""
    logger.info("🧠 测试4: 语义相似性测试")
    
    tester = SimilarQATester("semantic_user", "semantic_agent")
    
    # 添加语义相关的问答
    semantic_qa_pairs = [
        ("我住在北京", "北京是中国的首都，有很多历史文化景点。"),
        ("我经常去故宫", "故宫是明清两朝的皇宫，建筑很壮观。"),
        ("我喜欢吃烤鸭", "全聚德的烤鸭很有名，我经常去吃。"),
        ("我坐地铁上班", "地铁很方便，我每天都是坐地铁通勤。"),
        ("我周末喜欢逛街", "三里屯和王府井是我常去的地方。")
    ]
    
    # 添加问答对
    for question, answer in semantic_qa_pairs:
        await tester.add_qa_pair(question, answer)
        await asyncio.sleep(1)
    
    await asyncio.sleep(3)
    
    # 测试语义相似查询
    test_cases = [
        ("我住在哪个城市", ["我住在北京"], "城市查询"),
        ("我去过什么景点", ["我经常去故宫"], "景点查询"),
        ("我喜欢什么美食", ["我喜欢吃烤鸭"], "美食查询"),
        ("我怎么上班", ["我坐地铁上班"], "通勤方式查询"),
        ("我周末做什么", ["我周末喜欢逛街"], "周末活动查询")
    ]
    
    success_count = 0
    for query, expected, name in test_cases:
        result = await tester.test_similar_query(query, expected, name)
        if result["recall_rate"] > 0.5:
            success_count += 1
    
    success_rate = success_count / len(test_cases)
    logger.info(f"\n📊 语义相似性测试成功率: {success_rate:.1%}")
    return success_rate > 0.6

async def run_all_similar_qa_tests():
    """运行所有相似问答测试"""
    logger.info("🚀 开始相似问答召回测试")
    logger.info("=" * 60)
    
    tests = [
        ("食物偏好", test_food_preferences),
        ("爱好活动", test_hobby_activities),
        ("工作学习", test_work_study),
        ("语义相似性", test_semantic_similarity)
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
            status = "✅ 通过" if result else "❌ 失败"
            logger.info(f"{test_name}: {status}")
        except Exception as e:
            logger.error(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 总结
    passed_count = sum(1 for _, result in results if result)
    total_count = len(results)
    overall_success_rate = passed_count / total_count
    
    logger.info("\n" + "=" * 60)
    logger.info("📊 相似问答召回测试总结")
    logger.info("=" * 60)
    logger.info(f"总体成功率: {overall_success_rate:.1%} ({passed_count}/{total_count})")
    
    if overall_success_rate >= 0.75:
        logger.info("🎉 相似问答召回效果优秀！")
    elif overall_success_rate >= 0.5:
        logger.info("👍 相似问答召回效果良好")
    else:
        logger.warning("⚠️ 相似问答召回效果需要改进")
    
    return overall_success_rate

if __name__ == "__main__":
    asyncio.run(run_all_similar_qa_tests())

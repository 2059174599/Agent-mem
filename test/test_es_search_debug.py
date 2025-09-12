#!/usr/bin/env python3
"""
ES搜索调试测试
专门用于调试ES搜索的召回问题
"""

import asyncio
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from models.es_models import ESService
from logging_config import get_logger

logger = get_logger(__name__)

async def test_es_search_debug():
    """调试ES搜索问题"""
    logger.info("🔍 开始ES搜索调试测试")
    
    user_id = "debug_user"
    agent_id = "debug_agent"
    
    try:
        # 1. 添加测试数据
        logger.info("📝 步骤1: 添加测试数据")
        async with AsyncMemoryServiceV2() as memory_service:
            # 添加几个测试问答
            test_qa_pairs = [
                ("我喜欢吃苹果", "苹果富含维生素C，对健康很有好处。"),
                ("我喜欢吃香蕉", "香蕉富含钾元素，有助于肌肉放松。"),
                ("我最喜欢的水果是草莓", "草莓酸甜可口，是我最喜欢的水果。"),
                ("我经常吃蔬菜沙拉", "蔬菜沙拉营养丰富，我每天都会吃一些。"),
                ("我不太喜欢辣的菜", "我的口味比较清淡，不太能吃辣。")
            ]
            
            for question, answer in test_qa_pairs:
                await memory_service.add_memory_async(
                    user_id=user_id,
                    agent_id=agent_id,
                    question=question,
                    answer=answer
                )
                await asyncio.sleep(1)
            
            await asyncio.sleep(3)  # 等待数据写入完成
            
            # 2. 测试不同的搜索查询
            test_queries = [
                "我喜欢什么水果",
                "我喜欢吃什么",
                "我不喜欢什么",
                "我经常吃什么",
                "我的口味怎么样"
            ]
            
            es_service = ESService()
            
            for query in test_queries:
                logger.info(f"\n🔍 测试查询: {query}")
                
                # 获取embedding
                query_embedding = await memory_service.async_get_embedding(query)
                logger.info(f"📊 查询embedding长度: {len(query_embedding) if query_embedding else 0}")
                
                # 测试混合搜索
                logger.info("🔍 混合搜索结果:")
                mixed_results = es_service.search_similar_chats(
                    user_id, query, query_embedding, agent_id, 10
                )
                logger.info(f"  找到 {len(mixed_results)} 条结果")
                for i, result in enumerate(mixed_results):
                    logger.info(f"    {i+1}. {result.get('question', '')}")
                
                # 测试关键词搜索
                logger.info("🔍 关键词搜索结果:")
                keyword_results = es_service.search_similar_chats_by_question_only(
                    user_id, query, 10
                )
                logger.info(f"  找到 {len(keyword_results)} 条结果")
                for i, result in enumerate(keyword_results):
                    logger.info(f"    {i+1}. {result.get('question', '')}")
                
                # 测试向量搜索
                if query_embedding:
                    logger.info("🔍 向量搜索结果:")
                    vector_results = es_service.search_similar_chats_by_embedding_only(
                        user_id, query_embedding, agent_id, 10
                    )
                    logger.info(f"  找到 {len(vector_results)} 条结果")
                    for i, result in enumerate(vector_results):
                        logger.info(f"    {i+1}. {result.get('question', '')}")
                
                logger.info("-" * 50)
                
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()

async def test_es_search_with_different_scores():
    """测试不同min_score设置的效果"""
    logger.info("\n🧪 测试不同min_score设置的效果")
    
    user_id = "score_test_user"
    agent_id = "score_test_agent"
    
    try:
        async with AsyncMemoryServiceV2() as memory_service:
            # 添加测试数据
            await memory_service.add_memory_async(
                user_id=user_id,
                agent_id=agent_id,
                question="我喜欢吃苹果",
                answer="苹果富含维生素C，对健康很有好处。"
            )
            
            await asyncio.sleep(3)
            
            query = "我喜欢什么水果"
            query_embedding = await memory_service.async_get_embedding(query)
            
            es_service = ESService()
            
            # 测试不同的min_score设置
            min_scores = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
            
            for min_score in min_scores:
                logger.info(f"\n📊 测试 min_score = {min_score}")
                
                # 临时修改min_score进行测试
                original_method = es_service.search_similar_chats
                
                def test_search_with_score(user_id, query, embedding, agent_id=None, limit=10):
                    if not es_service._ensure_chat_index_exists():
                        return []
                    
                    must_conditions = [{"term": {"user_id": user_id}}]
                    if agent_id is not None:
                        must_conditions.append({"term": {"agent_id": agent_id}})
                    
                    should_conditions = [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["question^4", "answer^1.5"],
                                "type": "best_fields",
                                "fuzziness": "0",
                                "minimum_should_match": "80%"
                            }
                        }
                    ]
                    
                    search_body = {
                        "knn": {
                            "field": "embedding",
                            "query_vector": embedding,
                            "k": limit,
                            "num_candidates": limit * 10
                        },
                        "query": {
                            "bool": {
                                "must": must_conditions,
                                "should": should_conditions,
                                "minimum_should_match": 1
                            }
                        },
                        "size": limit,
                        "min_score": min_score,
                        "sort": [
                            {"_score": {"order": "desc"}},
                            {"timestamp": {"order": "desc"}}
                        ]
                    }
                    
                    try:
                        result = es_service.es.search(index=es_service._get_chat_index(), **search_body)
                        return [hit["_source"] for hit in result["hits"]["hits"]]
                    except Exception as e:
                        logger.error(f"ES搜索失败: {e}")
                        return []
                
                results = test_search_with_score(user_id, query, query_embedding, agent_id, 10)
                logger.info(f"  找到 {len(results)} 条结果")
                for i, result in enumerate(results):
                    logger.info(f"    {i+1}. {result.get('question', '')}")
                
    except Exception as e:
        logger.error(f"❌ 测试异常: {e}")
        import traceback
        traceback.print_exc()

async def main():
    """主测试函数"""
    logger.info("🚀 开始ES搜索调试测试")
    logger.info("=" * 60)
    
    await test_es_search_debug()
    await test_es_search_with_different_scores()
    
    logger.info("\n🎉 ES搜索调试测试完成")

if __name__ == "__main__":
    asyncio.run(main())

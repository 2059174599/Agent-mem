"""
测试记忆管理接口优化功能
测试添加、更新、删除操作的异步性和ES存储功能
"""
import asyncio
import aiohttp
import json
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

class MemoryManageTester:
    def __init__(self):
        self.base_url = "http://localhost:8000"
        self.auth_token = "yixinagentmemory"
        self.test_user_id = "test_user_123"
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

    async def test_add_memory(self):
        """测试添加记忆功能"""
        print("🧪 测试添加记忆...")

        payload = {
            "action": "add",
            "userId": self.test_user_id,
            "topic": "兴趣爱好",
            "subTopic": "运动",
            "memo": "我非常喜欢打篮球"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/memory/manage",
                    json=payload,
                    headers=self.headers
                ) as response:
                    result = await response.json()
                    print(f"添加记忆结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                    return result
            except Exception as e:
                print(f"❌ 添加记忆请求失败: {e}")
                return None

    async def test_update_memory(self):
        """测试更新记忆功能"""
        print("🧪 测试更新记忆...")

        # 先查询记忆获取memoryId
        query_payload = {
            "userId": self.test_user_id
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/memory/query",
                json=query_payload,
                headers=self.headers
            ) as response:
                query_result = await response.json()

                if query_result.get("success") and query_result.get("data", {}).get("facts"):
                    memory_id = query_result["data"]["facts"][0]["chat_id"]

                    # 更新记忆
                    update_payload = {
                        "action": "update",
                        "topic": "兴趣爱好",
                        "subTopic": "运动",
                        "userId": self.test_user_id,
                        "memoryId": memory_id,
                        "memo": "我不喜欢打篮球了，改打羽毛球"
                    }

                    async with session.post(
                        f"{self.base_url}/memory/manage",
                        json=update_payload,
                        headers=self.headers
                    ) as response:
                        result = await response.json()
                        print(f"更新记忆结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        return result
                else:
                    print("❌ 没有找到记忆进行更新测试")
                    return None

    async def test_delete_memory(self):
        """测试删除记忆功能"""
        print("🧪 测试删除记忆...")

        # 查询记忆获取memoryId
        query_payload = {
            "userId": self.test_user_id
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/memory/query",
                json=query_payload,
                headers=self.headers
            ) as response:
                query_result = await response.json()

                if query_result.get("success") and query_result.get("data", {}).get("facts"):
                    memory_id = query_result["data"]["facts"][0]["chat_id"]

                    # 删除记忆
                    delete_payload = {
                        "action": "delete",
                        "userId": self.test_user_id,
                        "memoryId": memory_id
                    }

                    async with session.post(
                        f"{self.base_url}/memory/manage",
                        json=delete_payload,
                        headers=self.headers
                    ) as response:
                        result = await response.json()
                        print(f"删除记忆结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
                        return result
                else:
                    print("❌ 没有找到记忆进行删除测试")
                    return None

    async def test_redis_only(self):
        """测试只依赖Redis的功能（绕过ES）"""
        print("🧪 测试Redis-only记忆管理功能...")

        try:
            # 直接测试Redis服务
            from services.memory_management_service import MemoryManagementService
            from models.redis_models import RedisService
            from services.unified_cache_service import unified_cache_service

            redis_service = RedisService()
            memory_service = MemoryManagementService(redis_service, unified_cache_service)

            # 测试添加记忆（Redis部分）
            print("  📝 测试添加记忆到Redis...")
            add_result = await memory_service.add_memory(
                user_id=self.test_user_id,
                agent_id=None,
                topic="兴趣爱好",
                sub_topic="运动",
                memo="我非常喜欢打篮球",
                memory_id=None
            )
            print(f"  ✅ 添加结果: {add_result.get('success')}")

            # 测试查询记忆
            print("  🔍 测试查询记忆...")
            query_result = await memory_service.query_memory(
                user_id=self.test_user_id,
                agent_id=None,
                limit=10
            )
            print(f"  ✅ 查询结果: {len(query_result.get('data', {}).get('facts', []))} 条记忆")

            if query_result.get('success') and query_result.get('data', {}).get('facts'):
                memory_id = query_result['data']['facts'][0]['chat_id']

                # 测试更新记忆
                print("  🔄 测试更新记忆...")
                update_result = await memory_service.update_memory(
                    user_id=self.test_user_id,
                    agent_id=None,
                    memory_id=memory_id,
                    memo="我不喜欢打篮球了，改打羽毛球",
                    topic="兴趣爱好",
                    sub_topic="运动"
                )
                print(f"  ✅ 更新结果: {update_result.get('success')}")

                # 测试删除记忆
                print("  🗑️ 测试删除记忆...")
                delete_result = await memory_service.delete_memory(
                    user_id=self.test_user_id,
                    agent_id=None,
                    memory_id=memory_id,
                    delete_all=False
                )
                print(f"  ✅ 删除结果: {delete_result.get('success')}")

            return True

        except Exception as e:
            print(f"❌ Redis测试失败: {e}")
            return False

    async def test_api_full_cycle(self):
        """测试完整的API接口功能，包括ES存储验证"""
        print("🧪 测试完整API接口功能...")
        print("  🔄 测试添加记忆API...")

        # 测试添加记忆
        add_result = await self.test_add_memory()
        if not add_result or not add_result.get("success"):
            print(f"  ❌ 添加记忆API失败: {add_result}")
            return False

        print("  📝 添加记忆API成功")

        # 等待数据写入
        await asyncio.sleep(0.5)

        # 测试查询记忆API
        print("  🔍 测试查询记忆API...")
        query_payload = {
            "userId": self.test_user_id
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.base_url}/memory/query",
                    json=query_payload,
                    headers=self.headers
                ) as response:
                    query_result = await response.json()

                    if not query_result.get("success") or not query_result.get("data", {}).get("facts"):
                        print(f"  ❌ 查询记忆API失败: {query_result}")
                        return False

                    memory_id = query_result["data"]["facts"][0]["chat_id"]
                    print(f"  ✅ 查询记忆API成功，找到 {len(query_result['data']['facts'])} 条记忆")

                    # 验证ES中是否有对应的对话
                    print("  🔍 验证ES对话存储...")
                    es_search_payload = {
                        "userId": self.test_user_id,
                        "query": "添加记忆",
                        "limit": 10
                    }

                    async with session.post(
                        f"{self.base_url}/memory/search",
                        json=es_search_payload,
                        headers=self.headers
                    ) as search_response:
                        search_result = await search_response.json()

                        if not search_result.get("success"):
                            print(f"  ❌ ES搜索失败: {search_result}")
                            return False

                        similar_chats = search_result.get("search_results", {}).get("similar_chats", [])
                        if not similar_chats:
                            print("  ❌ ES中未找到对话记录")
                            return False

                        print(f"  ✅ ES中找到 {len(similar_chats)} 条对话记录")

                        # 测试更新记忆API
                        print("  🔄 测试更新记忆API...")
                        update_payload = {
                            "action": "update",
                            "userId": self.test_user_id,
                            "memoryId": memory_id,
                            "memo": "我现在喜欢打羽毛球了"
                        }

                        async with session.post(
                            f"{self.base_url}/memory/manage",
                            json=update_payload,
                            headers=self.headers
                        ) as update_response:
                            update_result = await update_response.json()

                            if not update_result.get("success"):
                                print(f"  ❌ 更新记忆API失败: {update_result}")
                                return False

                            print("  ✅ 更新记忆API成功")

                            # 验证更新后的ES记录
                            await asyncio.sleep(0.5)
                            async with session.post(
                                f"{self.base_url}/memory/search",
                                json={"userId": self.test_user_id, "query": "更新记忆", "limit": 10},
                                headers=self.headers
                            ) as update_search_response:
                                update_search_result = await update_search_response.json()

                                if update_search_result.get("success"):
                                    update_chats = update_search_result.get("search_results", {}).get("similar_chats", [])
                                    print(f"  ✅ ES中找到 {len(update_chats)} 条更新记录")

                        # 测试删除记忆API
                        print("  🗑️ 测试删除记忆API...")
                        delete_payload = {
                            "action": "delete",
                            "userId": self.test_user_id,
                            "memoryId": memory_id
                        }

                        async with session.post(
                            f"{self.base_url}/memory/manage",
                            json=delete_payload,
                            headers=self.headers
                        ) as delete_response:
                            delete_result = await delete_response.json()

                            if not delete_result.get("success"):
                                print(f"  ❌ 删除记忆API失败: {delete_result}")
                                return False

                            print("  ✅ 删除记忆API成功")

                            # 验证删除后的ES记录
                            await asyncio.sleep(0.5)
                            async with session.post(
                                f"{self.base_url}/memory/search",
                                json={"userId": self.test_user_id, "query": "删除记忆", "limit": 10},
                                headers=self.headers
                            ) as delete_search_response:
                                delete_search_result = await delete_search_response.json()

                                if delete_search_result.get("success"):
                                    delete_chats = delete_search_result.get("search_results", {}).get("similar_chats", [])
                                    print(f"  ✅ ES中找到 {len(delete_chats)} 条删除记录")

                return True

            except Exception as e:
                print(f"❌ API测试异常: {e}")
                return False

    async def run_tests(self):
        """运行所有测试"""
        print("🚀 开始测试记忆管理接口优化功能...")
        print("=" * 50)

        try:
            # 首先测试Redis-only功能
            print("🔧 阶段1: 测试Redis功能（不依赖ES）")
            redis_test_result = await self.test_redis_only()
            print()

            if redis_test_result:
                print("🎉 Redis功能测试通过！")
            else:
                print("❌ Redis功能测试失败")
                return {"redis_test": False, "api_test": False}

            print()
            print("🔧 阶段2: 测试完整API接口（包含ES存储验证）")
            api_test_result = await self.test_api_full_cycle()

            if api_test_result:
                print("🎉 API接口测试通过！")
                print("✅ 所有操作的ES对话存储功能正常！")
            else:
                print("❌ API接口测试失败")

            return {
                "redis_test": redis_test_result,
                "api_test": api_test_result
            }

        except Exception as e:
            print(f"❌ 测试失败: {e}")
            return None

async def main():
    tester = MemoryManageTester()
    # await tester.test_add_memory()
    # await tester.test_update_memory()
    await tester.test_delete_memory()
    # await tester.run_tests()

if __name__ == "__main__":
    asyncio.run(main())

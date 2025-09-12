#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缓存操作测试文件
测试Redis缓存的清空、统计、性能等功能
"""

import asyncio
import json
import time
from typing import Dict, Any

import httpx
import redis


class CacheTester:
    """缓存测试类"""
    
    def __init__(self, base_url: str = "http://localhost:5010", redis_host: str = "localhost", redis_port: int = 6379):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        # 使用配置中的Redis设置
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from config import Config
        self.redis_client = redis.Redis(
            host=Config.get_redis_host(),
            port=Config.get_redis_port(),
            password=Config.get_redis_password(),
            decode_responses=True
        )
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def test_redis_connection(self) -> bool:
        """测试Redis连接"""
        try:
            info = self.redis_client.info()
            print(f"✅ Redis连接成功: {info.get('redis_version', 'unknown')}")
            return True
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
            return False
    
    def get_redis_info(self) -> Dict[str, Any]:
        """获取Redis信息"""
        try:
            info = self.redis_client.info()
            print(f"📊 Redis信息:")
            print(f"  版本: {info.get('redis_version', 'unknown')}")
            print(f"  内存使用: {info.get('used_memory_human', 'unknown')}")
            print(f"  连接数: {info.get('connected_clients', 0)}")
            print(f"  键数量: {info.get('db0', {}).get('keys', 0)}")
            return info
        except Exception as e:
            print(f"❌ 获取Redis信息失败: {e}")
            return {"error": str(e)}
    
    def get_all_databases_info(self) -> Dict[str, Any]:
        """获取所有数据库信息"""
        try:
            info = self.redis_client.info("keyspace")
            print(f"🗄️ 数据库信息:")
            for db, stats in info.items():
                if db.startswith("db"):
                    print(f"  {db}: {stats.get('keys', 0)} 个键, {stats.get('expires', 0)} 个过期键")
            return info
        except Exception as e:
            print(f"❌ 获取数据库信息失败: {e}")
            return {"error": str(e)}
    
    async def clear_cache_via_api(self) -> Dict[str, Any]:
        """通过API清空缓存"""
        try:
            response = await self.client.post(f"{self.base_url}/cache/clear")
            result = response.json()
            print(f"🗑️ API清空缓存: {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ API清空缓存失败: {e}")
            return {"error": str(e)}
    
    def clear_cache_directly(self) -> Dict[str, Any]:
        """直接清空Redis缓存"""
        try:
            # 清空所有数据库
            for db_num in range(16):  # Redis默认有16个数据库
                self.redis_client.select(db_num)
                keys = self.redis_client.keys("*")
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    print(f"🗑️ 清空数据库 {db_num}: 删除了 {deleted} 个键")
            
            print("✅ 直接清空Redis缓存完成")
            return {"success": True}
        except Exception as e:
            print(f"❌ 直接清空缓存失败: {e}")
            return {"error": str(e)}
    
    async def get_cache_stats_via_api(self) -> Dict[str, Any]:
        """通过API获取缓存统计"""
        try:
            response = await self.client.get(f"{self.base_url}/cache/stats")
            result = response.json()
            print(f"📊 API缓存统计: {response.status_code}")
            return result
        except Exception as e:
            print(f"❌ 获取API缓存统计失败: {e}")
            return {"error": str(e)}
    
    def get_cache_stats_directly(self) -> Dict[str, Any]:
        """直接获取Redis缓存统计"""
        try:
            stats = {}
            total_keys = 0
            total_memory = 0
            
            for db_num in range(16):
                self.redis_client.select(db_num)
                keys = self.redis_client.keys("*")
                if keys:
                    key_count = len(keys)
                    total_keys += key_count
                    
                    # 计算内存使用（粗略估算）
                    memory_usage = 0
                    for key in keys[:10]:  # 只计算前10个键的内存使用
                        try:
                            memory_usage += self.redis_client.memory_usage(key)
                        except:
                            pass
                    
                    if key_count > 0:
                        avg_memory = memory_usage / min(key_count, 10)
                        total_memory += avg_memory * key_count
                    
                    stats[f"db{db_num}"] = {
                        "keys": key_count,
                        "memory_usage": memory_usage
                    }
            
            stats["total_keys"] = total_keys
            stats["total_memory"] = total_memory
            
            print(f"📊 直接缓存统计:")
            print(f"  总键数: {total_keys}")
            print(f"  估算内存: {total_memory / 1024 / 1024:.2f} MB")
            
            return stats
        except Exception as e:
            print(f"❌ 获取直接缓存统计失败: {e}")
            return {"error": str(e)}
    
    def test_cache_performance(self) -> Dict[str, Any]:
        """测试缓存性能"""
        try:
            # 测试写入性能
            start_time = time.time()
            for i in range(100):
                key = f"test:perf:{i}"
                value = f"test_value_{i}" * 10  # 较大的值
                self.redis_client.set(key, value, ex=60)  # 60秒过期
            write_time = time.time() - start_time
            
            # 测试读取性能
            start_time = time.time()
            for i in range(100):
                key = f"test:perf:{i}"
                self.redis_client.get(key)
            read_time = time.time() - start_time
            
            # 清理测试数据
            for i in range(100):
                key = f"test:perf:{i}"
                self.redis_client.delete(key)
            
            performance_info = {
                "write_time": write_time,
                "read_time": read_time,
                "write_ops_per_sec": 100 / write_time,
                "read_ops_per_sec": 100 / read_time
            }
            
            print(f"⚡ 缓存性能测试:")
            print(f"  写入100个键: {write_time:.3f}秒 ({performance_info['write_ops_per_sec']:.1f} ops/sec)")
            print(f"  读取100个键: {read_time:.3f}秒 ({performance_info['read_ops_per_sec']:.1f} ops/sec)")
            
            return performance_info
        except Exception as e:
            print(f"❌ 缓存性能测试失败: {e}")
            return {"error": str(e)}
    
    def analyze_cache_patterns(self) -> Dict[str, Any]:
        """分析缓存模式"""
        try:
            patterns = {}
            total_keys = 0
            
            for db_num in range(16):
                self.redis_client.select(db_num)
                keys = self.redis_client.keys("*")
                
                if keys:
                    key_count = len(keys)
                    total_keys += key_count
                    
                    # 分析键的模式
                    for key in keys:
                        if ":" in key:
                            prefix = key.split(":")[0]
                            patterns[prefix] = patterns.get(prefix, 0) + 1
                        else:
                            patterns["no_prefix"] = patterns.get("no_prefix", 0) + 1
            
            print(f"🔍 缓存模式分析:")
            print(f"  总键数: {total_keys}")
            print(f"  键模式分布:")
            for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
                print(f"    {pattern}: {count} 个键")
            
            return {
                "total_keys": total_keys,
                "patterns": patterns
            }
        except Exception as e:
            print(f"❌ 缓存模式分析失败: {e}")
            return {"error": str(e)}


async def test_cache_operations():
    """测试缓存操作"""
    print("🗄️ 开始缓存操作测试...")
    print("=" * 50)
    
    async with CacheTester() as tester:
        try:
            # 1. 测试Redis连接
            if not tester.test_redis_connection():
                print("❌ Redis服务不可用，跳过测试")
                return False
            
            # 2. 获取Redis信息
            print("\n📊 Redis信息:")
            tester.get_redis_info()
            
            # 3. 获取所有数据库信息
            print("\n🗄️ 数据库信息:")
            tester.get_all_databases_info()
            
            # 4. 分析缓存模式
            print("\n🔍 缓存模式分析:")
            tester.analyze_cache_patterns()
            
            # 5. 获取API缓存统计
            print("\n📊 API缓存统计:")
            await tester.get_cache_stats_via_api()
            
            # 6. 获取直接缓存统计
            print("\n📊 直接缓存统计:")
            tester.get_cache_stats_directly()
            
            # 7. 测试缓存性能
            print("\n⚡ 缓存性能测试:")
            tester.test_cache_performance()
            
            # 8. 清空缓存测试（可选）
            print("\n🗑️ 清空缓存测试:")
            print("注意: 这将清空所有缓存数据！")
            # await tester.clear_cache_via_api()  # 取消注释以执行清空操作
            
            print("\n✅ 缓存操作测试完成！")
            return True
            
        except Exception as e:
            print(f"\n❌ 缓存测试过程中出现错误: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    asyncio.run(test_cache_operations())

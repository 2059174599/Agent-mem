#!/usr/bin/env python3
"""
ES数据清理API简单测试文件
快速测试通过API删除ES数据的功能
"""

import asyncio
import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx

async def test_clear_api():
    """测试ES清理API"""
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("🚀 开始测试ES清理API")
        
        # 1. 测试API健康状态
        try:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("✅ API健康检查通过")
            else:
                print(f"❌ API健康检查失败: {response.status_code}")
                return
        except Exception as e:
            print(f"❌ API健康检查异常: {e}")
            return
        
        # 2. 测试清理所有数据（预览模式）
        print("\n📋 测试清理所有数据（预览模式）")
        try:
            response = await client.post(
                f"{base_url}/memory/clear",
                params={"dry_run": True}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 预览模式成功:")
                print(f"   - 找到数据: {result.get('found_count', 0)} 条")
                print(f"   - 将删除: {result.get('will_delete_count', 0)} 条")
            else:
                print(f"❌ 预览模式失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ 预览模式异常: {e}")
        
        # 3. 测试按用户ID清理（预览模式）
        print("\n👤 测试按用户ID清理（预览模式）")
        try:
            response = await client.post(
                f"{base_url}/memory/clear",
                params={
                    "user_id": "test_user",
                    "dry_run": True
                }
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 用户预览成功:")
                print(f"   - 找到数据: {result.get('found_count', 0)} 条")
                print(f"   - 将删除: {result.get('will_delete_count', 0)} 条")
            else:
                print(f"❌ 用户预览失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ 用户预览异常: {e}")
        
        # 4. 测试按代理ID清理（预览模式）
        print("\n🤖 测试按代理ID清理（预览模式）")
        try:
            response = await client.post(
                f"{base_url}/memory/clear",
                params={
                    "agent_id": "test_agent",
                    "dry_run": True
                }
            )
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 代理预览成功:")
                print(f"   - 找到数据: {result.get('found_count', 0)} 条")
                print(f"   - 将删除: {result.get('will_delete_count', 0)} 条")
            else:
                print(f"❌ 代理预览失败: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ 代理预览异常: {e}")
        
        print("\n🎉 ES清理API测试完成")
        print("\n💡 提示:")
        print("   - 预览模式 (dry_run=True) 只查看不删除")
        print("   - 实际删除 (dry_run=False) 会真正删除数据")
        print("   - 可以指定 user_id 或 agent_id 进行过滤")
        print("   - 不指定任何ID则清理所有数据")

if __name__ == "__main__":
    asyncio.run(test_clear_api())

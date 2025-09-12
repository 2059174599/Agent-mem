#!/usr/bin/env python3
"""
快速测试ES清理API的脚本
"""

import asyncio
import httpx
import json

async def quick_test():
    """快速测试API"""
    base_url = "http://localhost:8000"
    
    print("🚀 快速测试ES清理API")
    print("=" * 40)
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 测试健康检查
        try:
            print("1. 测试API健康状态...")
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                print("   ✅ API健康检查通过")
            else:
                print(f"   ❌ API健康检查失败: {response.status_code}")
                return
        except Exception as e:
            print(f"   ❌ API健康检查异常: {e}")
            return
        
        # 测试清理API（预览模式）
        try:
            print("\n2. 测试清理API（预览模式）...")
            response = await client.post(
                f"{base_url}/memory/clear",
                params={"dry_run": True}
            )
            
            if response.status_code == 200:
                result = response.json()
                print("   ✅ 清理API调用成功")
                print(f"   📊 找到数据: {result.get('found_count', 0)} 条")
                print(f"   🗑️ 将删除: {result.get('will_delete_count', 0)} 条")
                print(f"   ⏱️ 处理时间: {result.get('processing_time', 0):.3f}秒")
            else:
                print(f"   ❌ 清理API调用失败: {response.status_code}")
                print(f"   📝 错误信息: {response.text}")
        except Exception as e:
            print(f"   ❌ 清理API调用异常: {e}")
        
        print("\n🎉 快速测试完成")
        print("\n💡 提示:")
        print("   - 这是预览模式，不会真正删除数据")
        print("   - 要实际删除数据，请设置 dry_run=False")
        print("   - 可以指定 user_id 或 agent_id 进行过滤")

if __name__ == "__main__":
    asyncio.run(quick_test())

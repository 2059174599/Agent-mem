#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ES清洗接口测试
测试清洗逻辑的各种场景
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.async_memory_service_v2 import AsyncMemoryServiceV2
from logging_config import get_logger

logger = get_logger(__name__)

class CleanupAPITester:
    """ES清洗接口测试类"""
    
    def __init__(self):
        self.memory_service = None
    
    async def __aenter__(self):
        self.memory_service = AsyncMemoryServiceV2()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.memory_service:
            # AsyncMemoryServiceV2 没有 close 方法，直接设置为 None
            self.memory_service = None
    
    async def test_cleanup_all_data_preview(self):
        """测试清理全部数据（预览模式）"""
        print("\n" + "="*60)
        print("测试1: 清理全部数据（预览模式）")
        print("="*60)
        
        result = await self.memory_service.cleanup_dirty_data_async(
            test_limit=500,
            dry_run=True
        )
        
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result
    
    async def test_cleanup_by_user_id_preview(self, user_id: str):
        """测试按用户ID清理（预览模式）"""
        print("\n" + "="*60)
        print(f"测试2: 按用户ID清理（预览模式） - 用户ID: {user_id}")
        print("="*60)
        
        result = await self.memory_service.cleanup_dirty_data_async(
            user_id=user_id,
            test_limit=30,
            dry_run=True
        )
        
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result
    
    async def test_cleanup_by_agent_id_preview(self, agent_id: str):
        """测试按代理ID清理（预览模式）"""
        print("\n" + "="*60)
        print(f"测试3: 按代理ID清理（预览模式） - 代理ID: {agent_id}")
        print("="*60)
        
        result = await self.memory_service.cleanup_dirty_data_async(
            agent_id=agent_id,
            test_limit=30,
            dry_run=True
        )
        
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result
    
    async def test_cleanup_quality_check_samples(self):
        """测试质量检测样本"""
        print("\n" + "="*60)
        print("测试4: 质量检测样本测试")
        print("="*60)
        
        test_cases = [
            # 正常案例
            ("你多大了？", "我三岁了！", "简单问题简短回答"),
            ("我喜欢吃辣，推荐下北京美食", "你好呀！智语助手为你推荐北京够味的辣味美食：\n- **麻辣火锅**：小龙坎、蜀大侠的牛油红汤锅必点", "美食推荐（有格式符号）"),
            ("我每天6点起床", "早起是个好习惯！", "习惯问题简短回答"),
            
            # 脏数据案例
            ("请详细介绍人工智能的发展历史", "好", "复杂问题简短回答"),
            ("测试问题", "测试答案", "测试数据"),
            ("你叫什么", "嗯嗯嗯嗯嗯嗯嗯嗯嗯嗯", "重复语气词"),
        ]
        
        for i, (question, answer, description) in enumerate(test_cases, 1):
            print(f"\n--- 测试案例 {i}: {description} ---")
            print(f"问题: {question}")
            print(f"答案: {answer}")
            
            quality_check = await self.memory_service._check_answer_quality(question, answer)
            print(f"质量检测结果: {quality_check}")
            
            if quality_check["is_valid"]:
                print("✅ 通过质量检测")
            else:
                print(f"❌ 未通过质量检测: {quality_check['reason']}")
    
    async def test_cleanup_dry_run_vs_real_delete(self):
        """测试预览模式vs删除模式"""
        print("\n" + "="*60)
        print("测试5: 预览模式 vs 删除模式对比")
        print("="*60)
        
        # 预览模式
        print("\n--- 预览模式 ---")
        preview_result = await self.memory_service.cleanup_dirty_data_async(
            test_limit=20,
            dry_run=True
        )
        print(f"预览结果: 发现{preview_result.get('dirty_found', 0)}条脏数据")
        
        # 删除模式（只删除前2条）
        if preview_result.get('dirty_found', 0) > 0:
            print("\n--- 删除模式（只删除前2条） ---")
            # 先获取要删除的数据
            dirty_chats = preview_result.get('dirty_chats', [])
            if len(dirty_chats) >= 2:
                # 模拟删除前2条
                print(f"将删除前2条脏数据:")
                for i, chat in enumerate(dirty_chats[:2]):
                    print(f"  {i+1}. chat_id: {chat['chat_id']}, 原因: {chat['reason']}")
                
                # 这里不实际执行删除，只是演示
                print("（实际删除已跳过，仅演示）")
            else:
                print("脏数据不足2条，跳过删除测试")
        else:
            print("没有发现脏数据，跳过删除测试")
    
    async def test_cleanup_performance(self):
        """测试清洗性能"""
        print("\n" + "="*60)
        print("测试6: 清洗性能测试")
        print("="*60)
        
        test_limits = [10, 50, 100]
        
        for limit in test_limits:
            print(f"\n--- 测试限制 {limit} 条记录 ---")
            start_time = datetime.now()
            
            result = await self.memory_service.cleanup_dirty_data_async(
                test_limit=limit,
                dry_run=True
            )
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            print(f"处理时间: {duration:.2f}秒")
            print(f"处理速度: {limit/duration:.2f}条/秒")
            print(f"发现脏数据: {result.get('dirty_found', 0)}条")
    
    async def test_clear_all_data_preview(self):
        """测试清空全部数据（预览模式）"""
        print("\n" + "="*60)
        print("测试7: 清空全部数据（预览模式）")
        print("="*60)
        
        result = await self.memory_service.clear_all_data_async(dry_run=True)
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result
    
    async def test_clear_by_user_id_preview(self, user_id: str):
        """测试按用户ID清空（预览模式）"""
        print("\n" + "="*60)
        print(f"测试8: 按用户ID清空（预览模式） - 用户ID: {user_id}")
        print("="*60)
        
        result = await self.memory_service.clear_all_data_async(
            user_id=user_id,
            dry_run=True
        )
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result
    
    async def test_clear_by_agent_id_preview(self, agent_id: str):
        """测试按代理ID清空（预览模式）"""
        print("\n" + "="*60)
        print(f"测试9: 按代理ID清空（预览模式） - 代理ID: {agent_id}")
        print("="*60)
        
        result = await self.memory_service.clear_all_data_async(
            agent_id=agent_id,
            dry_run=True
        )
        print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)}")
        return result

async def main():
    """主测试函数"""
    print("🧹 ES清洗接口测试开始")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    async with CleanupAPITester() as tester:
        try:
            # 测试1: 清理全部数据（预览模式）
            await tester.test_cleanup_all_data_preview()
            
            # 测试2: 按用户ID清理（预览模式）
            # await tester.test_cleanup_by_user_id_preview("test_user_123")
            #
            # # 测试3: 按代理ID清理（预览模式）
            # await tester.test_cleanup_by_agent_id_preview("test_agent_456")
            #
            # # 测试4: 质量检测样本测试
            # await tester.test_cleanup_quality_check_samples()
            #
            # # 测试5: 预览模式vs删除模式
            # await tester.test_cleanup_dry_run_vs_real_delete()
            #
            # # 测试6: 清洗性能测试
            # await tester.test_cleanup_performance()
            
            # 测试7: 清空全部数据（预览模式）
            await tester.test_clear_all_data_preview()
            
            # 测试8: 按用户ID清空（预览模式）
            await tester.test_clear_by_user_id_preview("concurrent_user_2")
            
            # 测试9: 按代理ID清空（预览模式）
            await tester.test_clear_by_agent_id_preview("test_agent")
            
            print("\n" + "="*60)
            print("✅ 所有测试完成")
            print("="*60)
            
        except Exception as e:
            print(f"\n❌ 测试过程中出现异常: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

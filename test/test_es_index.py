#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elasticsearch索引测试文件
测试ES索引的创建、查询、删除等功能
"""

import asyncio
import json
import time
from typing import Dict, Any, List

import httpx
from elasticsearch import Elasticsearch


class ESIndexTester:
    """ES索引测试类"""
    
    def __init__(self, es_host: str = "localhost:9200"):
        self.es_host = es_host
        # 尝试连接ES，如果失败则跳过测试
        try:
            self.es_client = Elasticsearch([f"http://{es_host}"])
            # 测试连接
            self.es_client.info()
        except Exception as e:
            print(f"❌ ES连接失败: {e}")
            self.es_client = None
        self.index_name = "aigc_user_dialogs"
    
    def test_connection(self) -> bool:
        """测试ES连接"""
        if self.es_client is None:
            print("❌ ES客户端未初始化")
            return False
        try:
            info = self.es_client.info()
            print(f"✅ ES连接成功: {info['cluster_name']} - {info['version']['number']}")
            return True
        except Exception as e:
            print(f"❌ ES连接失败: {e}")
            return False
    
    def check_index_exists(self) -> bool:
        """检查索引是否存在"""
        try:
            exists = self.es_client.indices.exists(index=self.index_name)
            print(f"📋 索引 '{self.index_name}' 存在: {exists}")
            return exists
        except Exception as e:
            print(f"❌ 检查索引失败: {e}")
            return False
    
    def get_index_info(self) -> Dict[str, Any]:
        """获取索引信息"""
        try:
            if not self.check_index_exists():
                return {"error": "索引不存在"}
            
            info = self.es_client.indices.get(index=self.index_name)
            print(f"📊 索引信息: {json.dumps(info, indent=2, ensure_ascii=False)}")
            return info
        except Exception as e:
            print(f"❌ 获取索引信息失败: {e}")
            return {"error": str(e)}
    
    def get_index_stats(self) -> Dict[str, Any]:
        """获取索引统计"""
        try:
            if not self.check_index_exists():
                return {"error": "索引不存在"}
            
            stats = self.es_client.indices.stats(index=self.index_name)
            print(f"📈 索引统计: {json.dumps(stats, indent=2, ensure_ascii=False)}")
            return stats
        except Exception as e:
            print(f"❌ 获取索引统计失败: {e}")
            return {"error": str(e)}
    
    def search_documents(self, query: str = "*", size: int = 10) -> Dict[str, Any]:
        """搜索文档"""
        try:
            if not self.check_index_exists():
                return {"error": "索引不存在"}
            
            search_body = {
                "query": {
                    "match_all" if query == "*" else {
                        "multi_match": {
                            "query": query,
                            "fields": ["question", "answer", "user_id"]
                        }
                    }
                },
                "size": size,
                "sort": [{"timestamp": {"order": "desc"}}]
            }
            
            result = self.es_client.search(
                index=self.index_name,
                body=search_body
            )
            
            hits = result.get("hits", {}).get("hits", [])
            print(f"🔍 搜索 '{query}': 找到 {len(hits)} 条文档")
            
            for i, hit in enumerate(hits[:3]):  # 只显示前3条
                source = hit.get("_source", {})
                print(f"  {i+1}. {source.get('question', '')} -> {source.get('answer', '')[:50]}...")
            
            return result
        except Exception as e:
            print(f"❌ 搜索文档失败: {e}")
            return {"error": str(e)}
    
    def get_recent_documents(self, size: int = 5) -> List[Dict[str, Any]]:
        """获取最近的文档"""
        try:
            if not self.check_index_exists():
                return []
            
            search_body = {
                "query": {"match_all": {}},
                "size": size,
                "sort": [{"timestamp": {"order": "desc"}}]
            }
            
            result = self.es_client.search(
                index=self.index_name,
                body=search_body
            )
            
            hits = result.get("hits", {}).get("hits", [])
            documents = []
            
            for hit in hits:
                source = hit.get("_source", {})
                documents.append({
                    "id": hit.get("_id"),
                    "question": source.get("question", ""),
                    "answer": source.get("answer", ""),
                    "user_id": source.get("user_id", ""),
                    "timestamp": source.get("timestamp", "")
                })
            
            print(f"📄 最近 {len(documents)} 条文档:")
            for i, doc in enumerate(documents):
                print(f"  {i+1}. [{doc['user_id']}] {doc['question']} -> {doc['answer'][:30]}...")
            
            return documents
        except Exception as e:
            print(f"❌ 获取最近文档失败: {e}")
            return []
    
    def delete_old_documents(self, days: int = 7) -> Dict[str, Any]:
        """删除旧文档（超过指定天数）"""
        try:
            if not self.check_index_exists():
                return {"error": "索引不存在"}
            
            from datetime import datetime, timedelta
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%dT%H:%M:%S")
            
            delete_body = {
                "query": {
                    "range": {
                        "timestamp": {
                            "lt": cutoff_str
                        }
                    }
                }
            }
            
            result = self.es_client.delete_by_query(
                index=self.index_name,
                body=delete_body
            )
            
            deleted_count = result.get("deleted", 0)
            print(f"🗑️ 删除了 {deleted_count} 条超过 {days} 天的旧文档")
            return result
        except Exception as e:
            print(f"❌ 删除旧文档失败: {e}")
            return {"error": str(e)}
    
    def test_index_performance(self) -> Dict[str, Any]:
        """测试索引性能"""
        try:
            if not self.check_index_exists():
                return {"error": "索引不存在"}
            
            # 测试搜索性能
            start_time = time.time()
            result = self.search_documents("*", size=100)
            search_time = time.time() - start_time
            
            # 获取索引统计
            stats = self.get_index_stats()
            
            performance_info = {
                "search_time": search_time,
                "total_documents": stats.get("indices", {}).get(self.index_name, {}).get("total", {}).get("docs", {}).get("count", 0),
                "index_size": stats.get("indices", {}).get(self.index_name, {}).get("total", {}).get("store", {}).get("size_in_bytes", 0)
            }
            
            print(f"⚡ 性能测试结果:")
            print(f"  搜索时间: {search_time:.3f}秒")
            print(f"  文档总数: {performance_info['total_documents']}")
            print(f"  索引大小: {performance_info['index_size']} 字节")
            
            return performance_info
        except Exception as e:
            print(f"❌ 性能测试失败: {e}")
            return {"error": str(e)}


def test_es_operations():
    """测试ES操作"""
    print("🔍 开始ES索引测试...")
    print("=" * 50)
    
    tester = ESIndexTester()
    
    try:
        # 1. 测试连接
        if not tester.test_connection():
            print("❌ ES服务不可用，跳过测试")
            return False
        
        # 2. 检查索引
        tester.check_index_exists()
        
        # 3. 获取索引信息
        print("\n📋 索引信息:")
        tester.get_index_info()
        
        # 4. 获取索引统计
        print("\n📊 索引统计:")
        tester.get_index_stats()
        
        # 5. 搜索文档
        print("\n🔍 搜索测试:")
        tester.search_documents("*", size=5)
        tester.search_documents("小智", size=3)
        tester.search_documents("年龄", size=3)
        
        # 6. 获取最近文档
        print("\n📄 最近文档:")
        tester.get_recent_documents(5)
        
        # 7. 性能测试
        print("\n⚡ 性能测试:")
        tester.test_index_performance()
        
        # 8. 清理旧文档（可选）
        print("\n🗑️ 清理测试:")
        # tester.delete_old_documents(30)  # 删除30天前的文档
        
        print("\n✅ ES索引测试完成！")
        return True
        
    except Exception as e:
        print(f"\n❌ ES测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    test_es_operations()

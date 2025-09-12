"""
简单鉴权测试
"""

import requests
import json
from typing import Dict, Any


class AuthTester:
    """鉴权测试类"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.auth_token = "yixinagentmemory"
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_health_check(self) -> Dict[str, Any]:
        """测试健康检查（无需鉴权）"""
        try:
            response = requests.get(f"{self.base_url}/health")
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_topics_without_auth(self) -> Dict[str, Any]:
        """测试获取主题（无鉴权）"""
        try:
            response = requests.get(f"{self.base_url}/topics")
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_topics_with_auth(self) -> Dict[str, Any]:
        """测试获取主题（有鉴权）"""
        try:
            response = requests.get(f"{self.base_url}/topics", headers=self.headers)
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_memory_search_without_auth(self) -> Dict[str, Any]:
        """测试记忆搜索（无鉴权）"""
        try:
            data = {
                "userId": "test_user",
                "query": "测试查询",
                "limit": 10
            }
            response = requests.post(f"{self.base_url}/memory/search", json=data)
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_memory_search_with_auth(self) -> Dict[str, Any]:
        """测试记忆搜索（有鉴权）"""
        try:
            data = {
                "userId": "test_user",
                "query": "测试查询",
                "limit": 10
            }
            response = requests.post(f"{self.base_url}/memory/search", json=data, headers=self.headers)
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_memory_add_without_auth(self) -> Dict[str, Any]:
        """测试添加记忆（无鉴权）"""
        try:
            data = {
                "userId": "test_user",
                "question": "测试问题",
                "answer": "测试答案"
            }
            response = requests.post(f"{self.base_url}/memory/add", json=data)
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_memory_add_with_auth(self) -> Dict[str, Any]:
        """测试添加记忆（有鉴权）"""
        try:
            data = {
                "userId": "test_user",
                "question": "测试问题",
                "answer": "测试答案"
            }
            response = requests.post(f"{self.base_url}/memory/add", json=data, headers=self.headers)
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_invalid_token(self) -> Dict[str, Any]:
        """测试无效Token"""
        try:
            invalid_headers = {
                "Authorization": "Bearer invalid_token",
                "Content-Type": "application/json"
            }
            response = requests.get(f"{self.base_url}/topics", headers=invalid_headers)
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def test_missing_token(self) -> Dict[str, Any]:
        """测试缺少Token"""
        try:
            response = requests.get(f"{self.base_url}/topics")
            return {
                "success": True,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else response.text
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def run_all_tests(self) -> Dict[str, Any]:
        """运行所有测试"""
        print("🧪 开始鉴权测试...")
        
        tests = [
            ("健康检查（无需鉴权）", self.test_health_check),
            ("获取主题（无鉴权）", self.test_topics_without_auth),
            ("获取主题（有鉴权）", self.test_topics_with_auth),
            ("记忆搜索（无鉴权）", self.test_memory_search_without_auth),
            ("记忆搜索（有鉴权）", self.test_memory_search_with_auth),
            ("添加记忆（无鉴权）", self.test_memory_add_without_auth),
            ("添加记忆（有鉴权）", self.test_memory_add_with_auth),
            ("无效Token", self.test_invalid_token),
            ("缺少Token", self.test_missing_token),
        ]
        
        results = {}
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            print(f"\n🔍 测试: {test_name}")
            result = test_func()
            results[test_name] = result
            
            if result["success"]:
                status_code = result.get("status_code", 0)
                if "无鉴权" in test_name and status_code == 200:
                    print(f"✅ 通过 - 状态码: {status_code}")
                    passed += 1
                elif "有鉴权" in test_name and status_code == 200:
                    print(f"✅ 通过 - 状态码: {status_code}")
                    passed += 1
                elif "无效Token" in test_name and status_code == 401:
                    print(f"✅ 通过 - 状态码: {status_code} (正确拒绝)")
                    passed += 1
                elif "缺少Token" in test_name and status_code == 401:
                    print(f"✅ 通过 - 状态码: {status_code} (正确拒绝)")
                    passed += 1
                else:
                    print(f"❌ 失败 - 状态码: {status_code}")
                    print(f"   响应: {result.get('data', 'N/A')}")
            else:
                print(f"❌ 失败 - 错误: {result.get('error', 'Unknown error')}")
        
        print(f"\n📊 测试结果: {passed}/{total} 通过")
        return {
            "passed": passed,
            "total": total,
            "results": results
        }


def main():
    """主函数"""
    tester = AuthTester()
    results = tester.run_all_tests()
    
    if results["passed"] == results["total"]:
        print("\n🎉 所有测试通过！")
    else:
        print(f"\n⚠️  有 {results['total'] - results['passed']} 个测试失败")
    
    return results


if __name__ == "__main__":
    main()

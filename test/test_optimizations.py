"""
测试三大优化功能
1. 多场景支持
2. 内容智能压缩
3. 数据持久化
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import requests
import json
from pathlib import Path

# 测试配置
BASE_URL = "http://localhost:8000"
TOKENS = {
    "通用": "yixinagentmemory",
    "合同": "contract_review_token",
    "医疗": "medical_consult_token",
    "CRM": "crm_token"
}


def print_section(title):
    """打印分隔线"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def test_scenarios():
    """测试1: 多场景支持"""
    print_section("测试1: 多场景支持")
    
    # 1.1 获取所有场景
    print("1.1 获取所有场景...")
    response = requests.get(f"{BASE_URL}/scenarios")
    print(f"响应状态: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"✅ 发现 {data['total']} 个场景:")
        for token, info in data['scenarios'].items():
            print(f"  - {info['name']}: {token[:20]}...")
    else:
        print(f"❌ 失败: {response.text}")
    
    # 1.2 测试不同场景的主题
    print("\n1.2 测试不同场景的主题...")
    for scene_name, token in TOKENS.items():
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(f"{BASE_URL}/topics", headers=headers)
        if response.ok:
            data = response.json()
            topics = data.get('topics', {})
            print(f"✅ {scene_name}场景: {len(topics)} 个主题")
            # 打印前3个主题
            for i, (topic, subtopics) in enumerate(list(topics.items())[:3]):
                print(f"    {topic}: {len(subtopics)} 个子主题")
        else:
            print(f"❌ {scene_name}场景获取失败")
    
    # 1.3 测试当前场景信息
    print("\n1.3 测试获取当前场景信息...")
    headers = {"Authorization": f"Bearer {TOKENS['合同']}"}
    response = requests.get(f"{BASE_URL}/scenario/current", headers=headers)
    if response.ok:
        data = response.json()
        print(f"✅ 当前场景: {data['name']}")
        print(f"   描述: {data['description']}")
        print(f"   策略: {data['fact_extraction_strategy']}")
    else:
        print(f"❌ 获取失败: {response.text}")


def test_compression():
    """测试2: 内容智能压缩"""
    print_section("测试2: 内容智能压缩")
    
    # 2.1 先添加一些长文本记忆
    print("2.1 添加长文本记忆用于测试...")
    headers = {"Authorization": f"Bearer {TOKENS['通用']}"}
    
    # 添加一个技术类长文本
    long_tech_text = """
    在Go语言中实现音频文件的读取需要使用第三方库。主要有两个选择：oto和beep库。
    首先需要安装相应的库：go get github.com/hajimehoshi/oto 或 go get github.com/faiface/beep。
    使用oto库时，需要配置音频上下文，包括采样率(如44100Hz)、位深度(通常是16bit)、声道数(单声道或立体声)。
    然后可以使用io.Reader接口读取音频数据，支持WAV、MP3、OGG等格式。
    需要注意的是，不同格式需要不同的解码器，MP3需要额外的解码库支持。
    """ * 2  # 重复2次使其更长
    
    data = {
        "userId": "test_compress_user",
        "agentId": "test_agent",
        "question": "go如何读取音频文件",
        "answer": long_tech_text
    }
    
    response = requests.post(f"{BASE_URL}/memory/add", headers=headers, json=data)
    if response.ok:
        print(f"✅ 已添加测试记忆")
    else:
        print(f"⚠️ 添加记忆可能失败(如果已存在则忽略)")
    
    # 等待处理完成
    print("   等待3秒让系统处理...")
    import time
    time.sleep(3)
    
    # 2.2 测试压缩预览
    print("\n2.2 测试压缩预览(不保存)...")
    data = {
        "userId": "test_compress_user",
        "agentId": "test_agent",
        "compress_all": False
    }
    
    response = requests.post(f"{BASE_URL}/memory/compress", headers=headers, json=data)
    if response.ok:
        result = response.json()
        if result['success']:
            stats = result['compression_stats']
            print(f"✅ 压缩预览成功:")
            print(f"   事实数量: {stats['total_facts']}")
            print(f"   原始长度: {stats['original_length']} 字符")
            print(f"   压缩后长度: {stats['compressed_length']} 字符")
            print(f"   压缩比: {stats['compression_ratio']}")
            
            if 'preview' in result:
                print(f"\n   预览示例:")
                for i, fact in enumerate(result['preview'][:2], 1):
                    print(f"   {i}. 主题: {fact['topic']} - {fact['sub_topic']}")
                    print(f"      原文: {fact.get('original_memo', 'N/A')[:80]}...")
                    print(f"      压缩: {fact['memo'][:80]}...")
        else:
            print(f"⚠️ 压缩预览返回: {result.get('message', '未知')}")
    else:
        print(f"❌ 压缩预览失败: {response.text}")
    
    # 2.3 测试压缩并保存(可选)
    print("\n2.3 测试压缩并保存...")
    print("   (提示: 这将实际修改数据,本测试跳过)")
    # 取消注释以实际测试
    # data["compress_all"] = True
    # response = requests.post(f"{BASE_URL}/memory/compress", headers=headers, json=data)


def test_persistence():
    """测试3: 数据持久化"""
    print_section("测试3: 数据持久化")
    
    test_user = "test_persist_user"
    headers = {"Authorization": f"Bearer {TOKENS['通用']}"}
    
    # 3.1 添加测试数据
    print("3.1 添加测试数据...")
    data = {
        "userId": test_user,
        "agentId": "persist_agent",
        "question": "持久化测试问题",
        "answer": "这是一个用于测试持久化功能的记忆"
    }
    
    response = requests.post(f"{BASE_URL}/memory/add", headers=headers, json=data)
    if response.ok:
        print("✅ 测试数据已添加")
    else:
        print("⚠️ 添加可能失败(如已存在则忽略)")
    
    # 等待异步处理
    print("   等待2秒让系统自动持久化...")
    import time
    time.sleep(2)
    
    # 3.2 检查持久化文件
    print("\n3.2 检查持久化文件...")
    persist_dir = Path("data/persistence")
    if persist_dir.exists():
        files = list(persist_dir.glob("*.json"))
        print(f"✅ 持久化目录存在")
        print(f"   找到 {len(files)} 个持久化文件:")
        for file in files[:5]:  # 只显示前5个
            print(f"   - {file.name}")
            # 检查文件内容
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                facts_count = len(data.get('facts', []))
                print(f"     包含 {facts_count} 个事实")
    else:
        print("⚠️ 持久化目录不存在(可能还未创建)")
    
    # 3.3 测试手动保存
    print("\n3.3 测试手动保存...")
    response = requests.post(
        f"{BASE_URL}/persistence/save",
        headers=headers,
        params={"user_id": test_user, "agent_id": "persist_agent"}
    )
    if response.ok:
        result = response.json()
        print(f"✅ 手动保存成功: {result.get('message', '')}")
        print(f"   事实数量: {result.get('facts_count', 0)}")
    else:
        print(f"❌ 手动保存失败: {response.text}")
    
    # 3.4 测试手动加载
    print("\n3.4 测试手动加载...")
    response = requests.post(
        f"{BASE_URL}/persistence/load",
        headers=headers,
        params={"user_id": test_user, "agent_id": "persist_agent"}
    )
    if response.ok:
        result = response.json()
        print(f"✅ 手动加载成功: {result.get('message', '')}")
        print(f"   事实数量: {result.get('facts_count', 0)}")
    else:
        print(f"❌ 手动加载失败: {response.text}")
    
    # 3.5 测试备份
    print("\n3.5 测试备份所有数据...")
    response = requests.post(f"{BASE_URL}/persistence/backup", headers=headers)
    if response.ok:
        result = response.json()
        if result['success']:
            info = result['backup_info']
            print(f"✅ 备份成功:")
            print(f"   备份时间: {info['backup_time']}")
            print(f"   用户数量: {info['users_count']}")
        else:
            print(f"❌ 备份失败: {result.get('error', '未知')}")
    else:
        print(f"❌ 备份请求失败: {response.text}")


def test_integration():
    """测试4: 综合场景测试"""
    print_section("测试4: 综合场景测试")
    
    print("4.1 完整工作流测试...")
    
    # 使用合同场景
    token = TOKENS['合同']
    headers = {"Authorization": f"Bearer {token}"}
    test_user = "integration_test_user"
    
    # 步骤1: 添加记忆
    print("   步骤1: 添加合同记忆...")
    data = {
        "userId": test_user,
        "agentId": "contract_agent",
        "question": "审查该采购合同的付款条款和违约责任条款",
        "answer": """该采购合同的付款条款约定分三期支付：
        首期付款30%在合同签订后5个工作日内支付；
        中期付款50%在货物验收合格后10个工作日内支付；
        尾款20%在质保期满后15个工作日内支付。
        违约责任方面，如卖方延期交货，每延期一天按合同总价的0.5%支付违约金，
        累计违约金不超过合同总价的10%。买方延期付款的，每延期一天按应付款项的0.03%支付违约金。
        建议关注以下风险点：1)首期付款比例偏高；2)质保期条款不明确；3)违约金上限设置可能影响实际赔偿。"""
    }
    
    response = requests.post(f"{BASE_URL}/memory/add", headers=headers, json=data)
    if response.ok:
        print("   ✅ 记忆添加成功(系统会自动提取事实并持久化)")
    else:
        print(f"   ❌ 添加失败: {response.text}")
    
    # 等待处理
    import time
    time.sleep(3)
    
    # 步骤2: 查询记忆
    print("\n   步骤2: 查询记忆...")
    data = {
        "userId": test_user,
        "agentId": "contract_agent",
        "query": "付款条款",
        "limit": 10
    }
    
    response = requests.post(f"{BASE_URL}/memory/search", headers=headers, json=data)
    if response.ok:
        result = response.json()
        if result['success']:
            search_results = result.get('search_results', {})
            facts = search_results.get('relevant_facts', [])
            chats = search_results.get('similar_chats', [])
            print(f"   ✅ 查询成功: 找到{len(facts)}个相关事实, {len(chats)}个相关对话")
        else:
            print(f"   ❌ 查询失败: {result.get('message', '未知')}")
    else:
        print(f"   ❌ 查询请求失败: {response.text}")
    
    # 步骤3: 检查持久化
    print("\n   步骤3: 检查持久化文件...")
    persist_file = Path(f"data/persistence/{test_user}_contract_agent_facts.json")
    if persist_file.exists():
        print(f"   ✅ 持久化文件已创建: {persist_file.name}")
        with open(persist_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"   包含 {len(data.get('facts', []))} 个事实")
    else:
        print(f"   ⚠️ 持久化文件未找到(可能使用其他命名)")
    
    print("\n   综合测试完成!")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("  Agent Memo 三大优化功能测试")
    print("="*60)
    
    try:
        # 检查服务是否运行
        print("\n检查服务状态...")
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.ok:
            print("✅ 服务正常运行\n")
        else:
            print("❌ 服务异常，请先启动服务")
            return
    except Exception as e:
        print(f"❌ 无法连接到服务: {e}")
        print("   请确保服务已启动: python app.py")
        return
    
    # 运行测试
    try:
        test_scenarios()
        test_compression()
        test_persistence()
        test_integration()
        
        print_section("测试总结")
        print("✅ 所有测试已完成!")
        print("\n详细文档:")
        print("  - OPTIMIZATION_GUIDE.md - 详细使用指南")
        print("  - 优化说明.md - 快速参考")
        
    except Exception as e:
        print(f"\n❌ 测试过程出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()


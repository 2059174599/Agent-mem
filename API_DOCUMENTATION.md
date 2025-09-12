# Yaxin Memo API 文档

## 概述

Yaxin Memo 是一个智能记忆系统，支持用户事实提取、存储和搜索。系统采用异步架构，提供高性能的记忆管理服务。

## 核心特性

- **异步添加记忆**：后台异步处理，立即返回响应
- **智能事实提取**：基于LLM自动提取用户事实
- **记忆管理**：统一的查询和更新接口
- **语义搜索**：支持对话和事实的智能搜索

## API 接口

### 1. 添加记忆

**接口**: `POST /memory/add`

**描述**: 异步添加记忆，后台处理事实提取和存储

**请求参数**:
```json
{
    "userId": "string",      // 用户ID（必填）
    "question": "string",    // 用户问题（必填）
    "answer": "string",      // AI回答（必填）
    "agentId": "string"      // 代理ID（可选）
}
```

**响应示例**:
```json
{
    "success": true,
    "message": "记忆添加任务已提交到后台处理",
    "request_id": "add_1691234567890",
    "api_processing_time": 0.012,
    "status": "processing"
}
```

### 2. 记忆管理

**接口**: `POST /memory/manage`

**描述**: 查询和更新Redis中的事实数据

#### 查询事实

**请求参数**:
```json
{
    "userId": "string",      // 用户ID（必填）
    "agentId": "string",     // 代理ID（可选）
    "action": "query",       // 操作类型：query
    "limit": 50,             // 返回数量限制（可选，默认50）
    "offset": 0              // 偏移量（可选，默认0）
}
```

**响应示例**:
```json
{
    "success": true,
    "facts": [
        {
            "id": "fact_兴趣爱好_运动",
            "topic": "兴趣爱好",
            "sub_topic": "运动",
            "memo": "用户喜欢打篮球运动",
            "timestamp": "2025-09-08T10:30:00"
        }
    ],
    "summary": {
        "total_facts": 5,
        "returned_facts": 5,
        "user_id": "user123",
        "agent_id": "agent001",
        "limit": 50,
        "offset": 0
    },
    "processing_time": 0.045,
    "message": "查询成功，找到5个事实，返回5个"
}
```

#### 更新事实

**请求参数**:
```json
{
    "userId": "string",      // 用户ID（必填）
    "agentId": "string",     // 代理ID（可选）
    "action": "update",      // 操作类型：update
    "memoryId": "string",    // 事实ID（必填）
    "topic": "string",       // 主题（必填）
    "subTopic": "string",    // 子主题（必填）
    "newMemo": "string"      // 新内容（必填）
}
```

**响应示例**:
```json
{
    "success": true,
    "updated_fact": {
        "id": "fact_兴趣爱好_运动",
        "topic": "兴趣爱好",
        "sub_topic": "运动",
        "memo": "用户超级喜欢打篮球运动",
        "timestamp": "2025-09-08T10:30:00"
    },
    "processing_time": 0.023,
    "message": "事实更新成功"
}
```

### 3. 搜索记忆

**接口**: `POST /memory/search`

**描述**: 智能搜索记忆，包括对话和事实

**请求参数**:
```json
{
    "userId": "string",      // 用户ID（必填）
    "query": "string",       // 搜索查询（必填）
    "agentId": "string",     // 代理ID（可选）
    "limit": 10              // 返回数量限制（可选，默认10）
}
```

**响应示例**:
```json
{
    "success": true,
    "search_results": {
        "similar_chats": [
            {
                "question": "我喜欢打篮球",
                "answer": "很好！篮球是很好的运动",
                "timestamp": "2025-09-08T10:30:00",
                "agent_id": "agent001"
            }
        ],
        "relevant_facts": [
            {
                "topic": "兴趣爱好",
                "sub_topic": "运动",
                "memo": "用户喜欢打篮球运动",
                "timestamp": "2025-09-08T10:30:00"
            }
        ]
    },
    "summary": {
        "total_chats": 1,
        "total_facts": 1,
        "query": "我喜欢什么运动"
    },
    "processing_time": 0.156,
    "message": "搜索成功，找到1个对话和1个事实"
}
```

### 4. 获取主题列表

**接口**: `GET /topics`

**描述**: 获取预定义的主题分类

**响应示例**:
```json
{
    "success": true,
    "topics": {
        "个人信息": ["姓名", "年龄", "性别", "职业", "学历"],
        "兴趣爱好": ["运动", "音乐", "阅读", "游戏", "旅行"],
        "情感偏好": ["沟通方式", "性格特点", "价值观"],
        "学习成长": ["技能", "目标", "计划", "反思"],
        "人际关系": ["朋友", "家人", "同事", "恋人"],
        "健康医疗": ["身体状况", "医疗记录", "生活习惯"]
    }
}
```

### 5. 性能统计

**接口**: `GET /performance`

**描述**: 获取系统性能统计信息

**响应示例**:
```json
{
    "success": true,
    "performance": {
        "total_requests": 150,
        "cache_hits": 45,
        "cache_misses": 105,
        "cache_hit_rate": 0.3,
        "avg_response_time": 0.125,
        "redis_cache": {
            "cache_size": 89,
            "hit_rate": 0.35
        }
    }
}
```

### 6. 健康检查

**接口**: `GET /health`

**描述**: 检查服务健康状态

**响应示例**:
```json
{
    "status": "healthy",
    "service": "yaxin_memo_fastapi",
    "version": "2.0.0",
    "performance": {
        "cache_size": 89,
        "uptime": "2h 15m 30s"
    }
}
```

## 错误处理

所有API接口都遵循统一的错误响应格式：

```json
{
    "success": false,
    "error": "错误描述",
    "message": "用户友好的错误信息",
    "api_processing_time": 0.012
}
```

常见HTTP状态码：
- `200`: 成功
- `400`: 请求参数错误
- `500`: 服务器内部错误

## 使用示例

### Python 示例

```python
import aiohttp
import asyncio

async def test_apis():
    async with aiohttp.ClientSession() as session:
        # 1. 添加记忆
        add_payload = {
            "userId": "user123",
            "question": "我喜欢打篮球",
            "answer": "很好！篮球是很好的运动",
            "agentId": "agent001"
        }
        
        async with session.post("http://localhost:8000/memory/add", json=add_payload) as response:
            result = await response.json()
            print("添加记忆:", result)
        
        # 等待后台处理
        await asyncio.sleep(2)
        
        # 2. 查询事实
        query_payload = {
            "userId": "user123",
            "agentId": "agent001",
            "action": "query",
            "limit": 10
        }
        
        async with session.post("http://localhost:8000/memory/manage", json=query_payload) as response:
            result = await response.json()
            print("查询事实:", result)
        
        # 3. 搜索记忆
        search_payload = {
            "userId": "user123",
            "query": "我喜欢什么运动",
            "agentId": "agent001"
        }
        
        async with session.post("http://localhost:8000/memory/search", json=search_payload) as response:
            result = await response.json()
            print("搜索记忆:", result)

# 运行测试
asyncio.run(test_apis())
```

### cURL 示例

```bash
# 添加记忆
curl -X POST "http://localhost:8000/memory/add" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user123",
    "question": "我喜欢打篮球",
    "answer": "很好！篮球是很好的运动",
    "agentId": "agent001"
  }'

# 查询事实
curl -X POST "http://localhost:8000/memory/manage" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user123",
    "agentId": "agent001",
    "action": "query",
    "limit": 10
  }'

# 搜索记忆
curl -X POST "http://localhost:8000/memory/search" \
  -H "Content-Type: application/json" \
  -d '{
    "userId": "user123",
    "query": "我喜欢什么运动",
    "agentId": "agent001"
  }'

# 清理项目所有缓存
curl -X POST "http://localhost:8000/cache/clear"
```

## 缓存管理接口

### 清理缓存

**接口**: `POST /cache/clear`

**描述**: 清理当前项目的所有缓存数据，包括缓存数据和事实数据

**请求参数**: 无需参数

**清理范围**:
- **缓存数据**: `yaxin_memo:cache:*` 前缀的所有数据
- **事实数据**: `facts:*` 前缀的所有数据

**响应示例**:
```json
{
  "success": true,
  "message": "已清理项目所有缓存数据",
  "deleted_count": 25,
  "cache_count": 15,
  "facts_count": 10
}
```

**响应字段说明**:
- `deleted_count`: 总计删除的键数量
- `cache_count`: 删除的缓存数据数量
- `facts_count`: 删除的事实数据数量

### 获取缓存统计

**接口**: `GET /cache/stats`

**描述**: 获取缓存统计信息

**响应示例**:
```json
{
  "success": true,
  "cache_stats": {
    "cache_count": 150,
    "memory_used": "2.5MB",
    "memory_peak": "3.2MB"
  }
}
```

## 注意事项

1. **异步处理**: 添加记忆接口采用异步后台处理，立即返回响应
2. **数据隔离**: 所有数据按用户ID隔离，确保隐私安全
3. **缓存机制**: 系统内置缓存机制，提升查询性能
4. **缓存安全**: 支持按类型清理缓存，避免误删重要数据
5. **错误重试**: 建议在客户端实现重试机制处理网络异常
6. **限流控制**: 建议控制请求频率，避免对系统造成压力

## 版本信息

- **当前版本**: 2.0.0
- **API版本**: v1
- **最后更新**: 2025-09-08

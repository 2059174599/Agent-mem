# Agent Memo - 智能记忆系统

一个基于FastAPI的智能记忆管理系统，支持用户事实存储、语义搜索、记忆持久化和智能过滤。专为多用户、多代理场景设计，提供完整的记忆管理API。

## 🚀 功能特性

### 核心功能
- **记忆管理**: 完整的记忆增删改查功能，支持主题验证
- **智能事实提取**: 从用户对话中自动提取和存储个人事实
- **语义搜索**: 基于向量相似度的智能记忆搜索
- **记忆持久化**: 支持Redis和Elasticsearch双重存储
- **用户隔离**: 支持多用户、多代理的记忆隔离
- **主题验证**: 预定义主题和子主题的严格验证机制

### 技术特性
- **异步处理**: 基于FastAPI和asyncio的高性能异步架构
- **混合搜索**: 结合关键词和向量搜索的混合检索策略
- **智能过滤**: 当事实数量超过阈值时自动启用LLM智能过滤
- **缓存优化**: 统一的Redis缓存管理，支持预定义主题缓存
- **服务分离**: 清晰的代码架构，业务逻辑与接口分离
- **单例模式**: 避免重复初始化，提升性能

## 📁 项目结构

```
agent-mem/
├── app.py                              # FastAPI应用入口（简化版）
├── config.py                           # 配置管理
├── logging_config.py                   # 日志配置
├── requirements.txt                    # 依赖文件
├── requirements-prod.txt               # 生产环境依赖
├── env.example                         # 环境变量模板
├── Dockerfile                          # Docker镜像构建
├── docker-compose.yml                  # Docker Compose配置
├── start.sh                            # 启动脚本
├── README.md                           # 项目说明
├── models/                             # 数据模型层
│   ├── es_models.py                    # Elasticsearch模型（单例模式）
│   └── redis_models.py                 # Redis模型（单例模式）
├── services/                           # 业务服务层
│   ├── async_memory_service_v2.py      # 异步记忆服务（核心服务）
│   ├── memory_management_service.py    # 记忆管理服务（业务逻辑）
│   ├── fact_extraction_service.py      # 事实提取服务
│   ├── llm_service.py                  # LLM服务
│   ├── embedding_service.py            # 嵌入服务
│   ├── unified_cache_service.py        # 统一缓存服务
│   └── async_logging_service.py        # 异步日志服务
├── prompts/                            # 提示词模板
│   └── fact_extraction.py              # 事实提取提示词
├── middleware/                         # 中间件
│   └── simple_auth.py                  # 简单认证中间件
└── logs/                               # 日志文件
    └── app.log                         # 应用日志
```

### 架构说明

- **接口层** (`app.py`): 简洁的API接口定义，只负责路由和基本验证
- **业务层** (`services/`): 完整的业务逻辑实现，职责分离
- **数据层** (`models/`): 数据模型和存储操作，使用单例模式
- **配置层** (`config.py`): 统一的配置管理
- **中间件** (`middleware/`): 认证、日志等横切关注点

## 🛠️ 技术栈

### 后端框架
- **FastAPI**: 现代、快速的Web框架
- **Uvicorn**: ASGI服务器
- **Pydantic**: 数据验证和序列化

### 数据存储
- **Redis**: 事实缓存和快速检索
- **Elasticsearch**: 向量搜索和全文检索
- **Redisearch**: 高级搜索功能

### AI/ML
- **OpenAI API**: LLM服务
- **Embedding**: 文本向量化
- **Scikit-learn**: 机器学习工具

### 其他依赖
- **aiohttp**: 异步HTTP客户端
- **python-dotenv**: 环境变量管理
- **numpy/pandas**: 数据处理

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆项目
git clone <repository-url>
cd agent-mem

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate     # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 环境配置

复制环境变量模板并配置：

```bash
cp env.example .env
```

编辑`.env`文件，配置必要的环境变量：

```env
# 数据库配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_redis_password
REDIS_DB=0

ES_HOST=http://localhost:9200
ES_USERNAME=elastic
ES_PASSWORD=your_es_password
ES_CHAT_INDEX=aigc_user_dialogs

# LLM配置
LLM_API_KEY=your_openai_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo

# 嵌入配置
EMBEDDING_API_KEY=your_openai_api_key
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-ada-002

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
LOG_LEVEL=INFO
```

### 3. 启动服务

#### 本地开发
```bash
# 直接启动
python app.py

# 或使用uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

#### Docker部署
```bash
# 使用Docker Compose（包含Redis和ES）
./start.sh all

# 仅启动API服务（连接外部Redis和ES）
./start.sh docker

# 仅启动API服务（本地开发）
./start.sh local
```

### 4. 验证安装

访问 `http://localhost:8000/docs` 查看API文档。

## 📖 API文档

### 核心接口

#### 记忆管理
- `POST /memory/query` - 查询记忆（支持分页和主题过滤）
- `POST /memory/manage` - 记忆管理（增删改查）
  - `action: "add"` - 添加记忆（需验证主题）
  - `action: "update"` - 更新记忆（支持更新主题和内容）
  - `action: "delete"` - 删除记忆（支持删除指定或全部）
- `POST /memory/search` - 智能搜索记忆（语义+关键词）
- `POST /memory/add` - 添加记忆（兼容接口）

#### 主题管理
- `GET /topics` - 获取预定义主题列表

#### 系统管理
- `GET /health` - 健康检查
- `GET /performance` - 性能统计
- `POST /cache/clear` - 清理缓存
- `POST /memory/cleanup` - 清理脏数据

### API使用示例

#### 添加记忆
```bash
curl -X POST "http://localhost:8000/memory/manage" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yixinagentmemory" \
  -d '{
    "action": "add",
    "userId": "user123",
    "agentId": "agent456",
    "topic": "兴趣爱好",
    "subTopic": "运动",
    "memo": "我喜欢打篮球"
  }'
```

#### 查询记忆
```bash
curl -X POST "http://localhost:8000/memory/query" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yixinagentmemory" \
  -d '{
    "userId": "user123",
    "agentId": "agent456",
    "limit": 10,
    "offset": 0
  }'
```

#### 更新记忆
```bash
curl -X POST "http://localhost:8000/memory/manage" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer yixinagentmemory" \
  -d '{
    "action": "update",
    "userId": "user123",
    "memoryId": "chat_001",
    "memo": "我热爱打篮球，每周都会去球场"
  }'
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
python -m pytest test/

# 运行特定测试
python test/test_memory_add_and_search.py
python test/test_fact_extraction_question_only.py
```

### 测试说明

- **记忆测试**: 验证记忆添加、搜索和持久化功能
- **事实提取测试**: 验证只从用户问题中提取事实
- **质量检测测试**: 验证答案质量评估功能
- **清理测试**: 验证脏数据清理功能

详细测试说明请参考 [test/README_MEMORY_TESTS.md](test/README_MEMORY_TESTS.md)

## 🚀 部署

### Docker部署

#### 完整部署（包含Redis和ES）
```bash
# 启动所有服务
./start.sh all

# 或使用Docker Compose
docker-compose up -d
```

#### 仅API服务部署
```bash
# 连接外部Redis和ES
./start.sh docker

# 本地开发模式
./start.sh local
```

#### 手动Docker部署
```bash
# 构建镜像
docker build -t agent-memo .

# 运行容器
docker run -p 8000:8000 --env-file .env agent-memo
```

### Kubernetes部署

项目支持K8s部署，包含：
- Dockerfile优化（非root用户）
- 健康检查配置
- 环境变量管理
- 启动脚本支持

### 生产环境

- 使用 `requirements-prod.txt` 安装生产依赖
- 配置环境变量（参考 `env.example`）
- 启用日志轮转
- 配置监控和告警

## ⚙️ 配置说明

### 搜索策略配置

```python
# 在config.py中配置搜索策略
SEARCH_STRATEGIES = {
    "fact_count_threshold": 50,        # 事实数量阈值
    "redis_return_all_facts": False,   # 是否返回所有事实
    "enable_llm_semantic_search": False, # 是否启用LLM语义搜索
    "max_search_results": 50,          # 最大搜索结果数
    "recent_chats_limit": 20,          # 最近对话轮数
}
```

### 质量检测配置

```python
# 质量检测配置
QUALITY_CHECK = {
    "enabled": True,                   # 是否启用质量检测
    "min_answer_length": 10,           # 最小答案长度
    "max_repetition_ratio": 0.3,       # 最大重复比例
    "min_llm_score": 0.3,              # 最小LLM评分
}
```

## 🔧 开发指南

### 代码架构

- **接口层** (`app.py`): 简洁的API接口定义，只负责路由和基本验证
- **业务层** (`services/`): 完整的业务逻辑实现，职责分离
- **数据层** (`models/`): 数据模型和存储操作，使用单例模式
- **配置层** (`config.py`): 统一的配置管理
- **中间件** (`middleware/`): 认证、日志等横切关注点

### 服务说明

#### MemoryManagementService
- 处理记忆的增删改查业务逻辑
- 统一的主题验证机制
- 完整的错误处理和日志记录

#### RedisService (单例)
- Redis数据操作
- 预定义主题初始化
- 事实存储和管理

#### ESService (单例)
- Elasticsearch数据操作
- 向量搜索和混合搜索
- 对话文档管理

### 添加新功能

1. 在相应的服务类中添加方法
2. 在`app.py`中添加API路由（保持简洁）
3. 编写测试用例
4. 更新API文档

### 调试技巧

- 查看日志文件：`logs/app.log`
- 使用测试脚本验证功能
- 通过API文档测试接口
- 使用Docker进行环境隔离测试

## 📊 性能优化

### 架构优化
- **单例模式**: 避免重复初始化ES和Redis连接
- **服务分离**: 业务逻辑与接口分离，提升可维护性
- **异步处理**: 全异步架构，非阻塞I/O操作

### 缓存策略
- Redis缓存LLM调用结果
- 嵌入向量缓存
- 事实搜索结果缓存
- 预定义主题缓存

### 搜索优化
- 混合搜索策略（关键词+向量）
- 智能过滤机制（LLM过滤）
- 结果数量限制和分页
- KNN搜索优化

### 数据存储
- Redis: 快速事实存储和检索
- Elasticsearch: 向量搜索和全文检索
- 统一缓存管理

## 🤝 贡献指南

1. Fork项目
2. 创建功能分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 📄 许可证

本项目采用MIT许可证。

## 📞 联系方式

如有问题或建议，请通过以下方式联系：

- 创建Issue
- 发送邮件
- 提交Pull Request

---

**Agent Memo** - 让AI记住你的每一个重要时刻 🧠✨

## 📝 更新日志

### v2.0.0 (最新)
- ✅ 重构代码架构，业务逻辑与接口分离
- ✅ 新增记忆管理服务，支持完整的增删改查
- ✅ 实现主题验证机制，确保数据质量
- ✅ 优化Redis和ES服务，使用单例模式
- ✅ 简化app.py，提升代码可维护性
- ✅ 支持Docker和K8s部署
- ✅ 完善API文档和使用示例

### v1.0.0
- 基础记忆管理功能
- Redis和ES双重存储
- 智能搜索和过滤
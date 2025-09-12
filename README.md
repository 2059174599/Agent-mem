# Yaxin Memo - 智能记忆系统

一个基于FastAPI的智能记忆管理系统，支持用户事实存储、语义搜索、记忆持久化和智能过滤。

## 🚀 功能特性

### 核心功能
- **智能事实提取**: 从用户对话中自动提取和存储个人事实
- **语义搜索**: 基于向量相似度的智能记忆搜索
- **记忆持久化**: 支持Redis和Elasticsearch双重存储
- **用户隔离**: 支持多用户、多代理的记忆隔离
- **质量检测**: 自动过滤低质量的LLM回答

### 技术特性
- **异步处理**: 基于FastAPI和asyncio的高性能异步架构
- **混合搜索**: 结合关键词和向量搜索的混合检索策略
- **智能过滤**: 当事实数量超过阈值时自动启用LLM智能过滤
- **缓存优化**: 统一的Redis缓存管理
- **质量评估**: 多层次的答案质量检测机制

## 📁 项目结构

```
yaxin_memo/
├── app.py                      # FastAPI应用入口
├── config.py                   # 配置管理
├── logging_config.py           # 日志配置
├── requirements.txt            # 依赖文件
├── pyproject.toml             # 项目配置
├── README.md                  # 项目说明
├── API_DOCUMENTATION.md       # API文档
├── DEPLOYMENT_GUIDE.md        # 部署指南
├── models/                    # 数据模型
│   ├── es_models.py           # Elasticsearch模型
│   └── redis_models.py        # Redis模型
├── services/                  # 业务服务
│   ├── async_memory_service_v2.py  # 异步记忆服务
│   ├── fact_extraction_service.py  # 事实提取服务
│   ├── llm_service.py         # LLM服务
│   ├── embedding_service.py   # 嵌入服务
│   └── unified_cache_service.py    # 统一缓存服务
├── prompts/                   # 提示词模板
│   └── fact_extraction.py     # 事实提取提示词
├── utils/                     # 工具函数
│   └── text_utils.py          # 文本处理工具
└── test/                      # 测试文件
    ├── README.md              # 测试说明
    ├── README_MEMORY_TESTS.md # 记忆测试说明
    └── *.py                   # 各种测试脚本
```

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
cd yaxin_memo

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
REDIS_URL=redis://localhost:6379
ELASTICSEARCH_URL=http://localhost:9200

# LLM配置
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=True
```

### 3. 启动服务

```bash
# 启动应用
python app.py

# 或使用uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

### 4. 验证安装

访问 `http://localhost:8000/docs` 查看API文档。

## 📖 API文档

### 核心接口

#### 记忆管理
- `POST /memory/add` - 添加记忆
- `POST /memory/add-or-update` - 添加或更新记忆
- `GET /memory/search` - 搜索记忆
- `DELETE /memory/cleanup` - 清理脏数据
- `DELETE /memory/clear` - 清空所有数据

#### 系统管理
- `GET /health` - 健康检查
- `GET /stats` - 系统统计

详细API文档请参考 [API_DOCUMENTATION.md](API_DOCUMENTATION.md)

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

```bash
# 构建镜像
docker build -t yaxin-memo .

# 运行容器
docker run -p 8000:8000 --env-file .env yaxin-memo
```

### 生产环境

详细部署指南请参考 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)

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

### 代码结构

- **models/**: 数据模型定义
- **services/**: 业务逻辑服务
- **prompts/**: LLM提示词模板
- **utils/**: 工具函数
- **test/**: 测试文件

### 添加新功能

1. 在相应的服务类中添加方法
2. 在`app.py`中添加API路由
3. 编写测试用例
4. 更新API文档

### 调试技巧

- 查看日志文件：`logs/app.log`
- 使用测试脚本验证功能
- 通过API文档测试接口

## 📊 性能优化

### 缓存策略
- Redis缓存LLM调用结果
- 嵌入向量缓存
- 事实搜索结果缓存

### 搜索优化
- 混合搜索策略
- 智能过滤机制
- 结果数量限制

### 异步处理
- 全异步架构
- 并行处理多个请求
- 非阻塞I/O操作

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

**Yaxin Memo** - 让AI记住你的每一个重要时刻 🧠✨
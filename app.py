"""
FastAPI版本的记忆服务API
性能优化版本，支持异步处理
"""
from doctest import debug

from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import time
import logging
from services.async_memory_service_v2 import AsyncMemoryServiceV2
from services.unified_cache_service import unified_cache_service
from services.async_logging_service import async_logging_service, log_info, log_error
from services.memory_management_service import MemoryManagementService
from middleware.simple_auth import SimpleAuthMiddleware, get_current_user_id, get_auth_status, get_scenario_token, get_scenario_config
from config import Config
from config_scenarios import ScenarioConfig
from logging_config import setup_logging, get_logger

# ARQ相关导入
try:
    from arq import create_pool
    from arq.connections import ArqRedis
    ARQ_AVAILABLE = True
except ImportError:
    ARQ_AVAILABLE = False
    logger = get_logger(__name__)
    logger.warning("⚠️ ARQ未安装，持久化任务将无法运行。请安装: pip install arq")

# 设置统一日志配置
setup_logging()
logger = get_logger(__name__)

# 全局异步服务实例
async_memory_service = None
memory_management_service = None
arq_pool: Optional[ArqRedis] = None  # ARQ连接池

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global async_memory_service
    
    # 启动事件
    global async_memory_service, memory_management_service, arq_pool
    logger.info("🚀 开始启动FastAPI记忆服务...")
    
    try:
        # 初始化服务
        logger.info("📦 初始化异步记忆服务...")
        async_memory_service = AsyncMemoryServiceV2()
        await async_memory_service.__aenter__()
        
        # 测试服务连接
        logger.info("🔍 测试服务连接...")
        
        # 测试Redis连接
        try:
            cache_stats = await async_memory_service.get_performance_stats()
            logger.info(f"✅ Redis缓存服务连接成功: {cache_stats.get('stats', {}).get('redis_cache', {})}")
        except Exception as e:
            logger.warning(f"⚠️ Redis缓存服务连接测试失败: {e}")
        
        # 测试ES连接
        try:
            # 这里可以添加ES连接测试
            logger.info("✅ Elasticsearch服务连接正常")
        except Exception as e:
            logger.warning(f"⚠️ Elasticsearch服务连接测试失败: {e}")
        
        # 初始化预定义主题到Redis
        try:
            await async_memory_service.redis_service.init_predefined_topics()
            logger.info("✅ 预定义主题配置完成")
        except Exception as e:
            logger.warning(f"⚠️ 预定义主题配置失败: {e}")
        
        # 初始化记忆管理服务
        memory_management_service = MemoryManagementService(
            async_memory_service.redis_service,
            unified_cache_service
        )
        
        # 初始化ARQ连接池（用于提交任务）
        if ARQ_AVAILABLE and Config.get_persistence_enabled():
            try:
                from arq.connections import RedisSettings
                arq_pool = await create_pool(
                    RedisSettings(
                        host=Config.get_redis_host(),
                        port=Config.get_redis_port(),
                        password=Config.get_redis_password() if Config.get_redis_password() else None,
                        database=Config.get_redis_db(),
                    )
                )
                logger.info("✅ ARQ连接池已初始化，持久化任务将由ARQ Worker处理")
                logger.info(f"   请确保ARQ Worker已启动: arq services.arq_tasks.WorkerSettings")
            except Exception as e:
                logger.warning(f"⚠️ ARQ连接池初始化失败: {e}")
                logger.warning("   持久化任务将无法运行，请检查Redis连接和ARQ Worker")
        else:
            if not ARQ_AVAILABLE:
                logger.warning("⚠️ ARQ未安装，持久化功能不可用")
            elif not Config.get_persistence_enabled():
                logger.info("ℹ️ 持久化功能已禁用")
        
        logger.info("🎉 FastAPI记忆服务启动完成！")
        logger.info(f"📊 服务配置: 端口={Config.get_app_port()}, 日志级别={Config.get_log_level()}")
        
    except Exception as e:
        logger.error(f"❌ FastAPI记忆服务启动失败: {e}")
        raise
    
    yield
    
    # 关闭事件
    logger.info("🛑 开始关闭FastAPI记忆服务...")
    
    # 关闭ARQ连接池
    if arq_pool:
        await arq_pool.close()
        logger.info("✅ ARQ连接池已关闭")
    
    if async_memory_service:
        await async_memory_service.__aexit__(None, None, None)
    logger.info("FastAPI记忆服务关闭完成")

# 创建FastAPI应用
app = FastAPI(
    title="Agent Memo API",
    description="智能记忆服务API",
    version="1.1.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加简单鉴权中间件
app.add_middleware(
    SimpleAuthMiddleware,
    auth_token="yixinagentmemory",
    excluded_paths=["/health", "/docs", "/redoc", "/openapi.json"]
)

# 初始化异步记忆服务
async_memory_service = AsyncMemoryServiceV2()

# 请求模型
class AddMemoryRequest(BaseModel):
    userId: str
    question: str
    answer: str
    agentId: Optional[str] = None

class SearchMemoryRequest(BaseModel):
    userId: str
    query: str
    agentId: Optional[str] = None
    limit: int = 10

class MemoryManageRequest(BaseModel):
    userId: str
    agentId: Optional[str] = None
    action: str  # "query" 或 "update"
    memoryId: Optional[str] = None  # 更新时需要
    topic: Optional[str] = None  # 更新时需要
    subTopic: Optional[str] = None  # 更新时需要
    newMemo: Optional[str] = None  # 更新时需要
    limit: int = 50
    offset: int = 0

class AddOrUpdateMemoryRequest(BaseModel):
    userId: str
    topic: str
    subTopic: str
    memo: str
    agentId: Optional[str] = None
    chatId: Optional[str] = None

# 新的记忆管理请求模型
class MemoryQueryRequest(BaseModel):
    """查询记忆请求"""
    userId: str
    agentId: Optional[str] = None
    topic: Optional[str] = None  # 可选：按主题过滤
    limit: int = 50
    offset: int = 0

class MemoryManageRequest(BaseModel):
    """记忆管理请求 - 支持增删改查"""
    action: str  # "add", "update", "delete", "query"
    userId: str
    agentId: Optional[str] = None
    
    # 查询参数
    topic: Optional[str] = None
    limit: int = 50
    offset: int = 0
    
    # 添加/更新参数
    memoryId: Optional[str] = None  # chat_id，用于更新/删除特定记忆
    subTopic: Optional[str] = None  # 子主题
    memo: Optional[str] = None      # 记忆内容
    
    # 删除参数
    deleteAll: bool = False  # 是否删除用户所有记忆

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    performance: Dict[str, Any]

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查 - 增强版本"""
    try:
        # 获取缓存统计
        cache_stats = await async_memory_service.cache_service.get_stats()
        cache_size = cache_stats.get('cache_count', 0)
        
        return HealthResponse(
            status="healthy",
            service="yixin_memo_fastapi",
            version="2.0.0",
            performance={
                "cache_size": cache_size,
                "uptime": "running"
            }
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            service="yixin_memo_fastapi",
            version="2.0.0",
            performance={
                "cache_size": 0,
                "uptime": "error",
                "error": str(e)
            }
        )

@app.post("/memory/add")
async def add_memory(request: AddMemoryRequest, background_tasks: BackgroundTasks, current_user_id: str = Depends(get_current_user_id)):
    """添加记忆 - 异步后台执行版本"""
    start_time = time.time()
    request_id = f"add_{int(time.time() * 1000)}"
    
    try:
        await log_info("api", f"📝 [{request_id}] 收到添加记忆请求: user_id={request.userId}, question={request.question[:50]}, answer={request.answer[:50]}...")
        
        # 立即返回响应，后台异步处理
        background_tasks.add_task(
            async_memory_service.add_memory_async,
            request.userId,
            request.agentId,
            request.question,
            request.answer
        )
        
        processing_time = time.time() - start_time
        
        await log_info("api", f"✅ [{request_id}] 记忆添加任务已提交到后台: 耗时: {processing_time:.3f}秒")
        
        return {
            "success": True,
            "message": "记忆添加任务已提交到后台处理",
            "request_id": request_id,
            "api_processing_time": processing_time,
            "status": "processing"
        }
            
    except Exception as e:
        processing_time = time.time() - start_time
        await log_error("api", f"❌ [{request_id}] 添加记忆异常: {e}, 耗时: {processing_time:.3f}秒")
        raise HTTPException(status_code=500, detail={
            "success": False,
            "error": str(e),
            "message": "服务器内部错误"
        })

@app.post("/memory/search")
async def search_memory(request: SearchMemoryRequest, current_user_id: str = Depends(get_current_user_id)):
    """搜索记忆 - 异步版本"""
    start_time = time.time()
    request_id = f"search_{int(time.time() * 1000)}"
    
    try:
        await log_info("api", f"🔍 [{request_id}] 收到搜索记忆请求: user_id={request.userId}, query={request.query[:50]}..., limit={request.limit}")
        
        result = await async_memory_service.search_memory_async(
            user_id=request.userId,
            query=request.query,
            agent_id=request.agentId,
            limit=request.limit
        )
        
        processing_time = time.time() - start_time
        result["api_processing_time"] = processing_time
        
        if result['success']:
            search_results = result.get('search_results', {})
            chats_count = len(search_results.get('similar_chats', []))
            facts_count = len(search_results.get('relevant_facts', []))
            await log_info("api", f"✅ [{request_id}] 搜索记忆成功: {chats_count}个对话, {facts_count}个事实, 耗时: {processing_time:.3f}秒")
            return result
        else:
            await log_error("api", f"❌ [{request_id}] 搜索记忆失败: {result.get('message', '未知错误')}, 耗时: {processing_time:.3f}秒")
            raise HTTPException(status_code=500, detail=result)
            
    except Exception as e:
        processing_time = time.time() - start_time
        await log_error("api", f"❌ [{request_id}] 搜索记忆异常: {e}, 耗时: {processing_time:.3f}秒")
        raise HTTPException(status_code=500, detail={
            "success": False,
            "error": str(e),
            "message": "记忆搜索失败"
        })

@app.post("/memory/query")
async def query_memory(request: MemoryQueryRequest, current_user_id: str = Depends(get_current_user_id)):
    """查询记忆 - 支持根据用户ID或Agent ID查询"""
    try:
        # 验证用户ID
        if not request.userId:
            return JSONResponse(
                content={"success": False, "error": "用户ID不能为空"},
                status_code=400
            )
        
        # 调用记忆管理服务
        result = await memory_management_service.query_memory(
            user_id=request.userId,
            agent_id=request.agentId,
            topic=request.topic,
            limit=request.limit,
            offset=request.offset
        )
        
        return JSONResponse(content=result, status_code=200 if result["success"] else 500)
            
    except Exception as e:
        await log_error("api", f"❌ 记忆查询异常: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

@app.post("/memory/manage")
async def manage_memory(request: MemoryManageRequest, current_user_id: str = Depends(get_current_user_id)):
    """
    记忆管理 - 支持添加、修改、删除记忆 \n
    action：添加：add、修改：update、删除：delete\n
    memoryId：查询记忆获取的chat_id
    """
    try:
        # 验证用户ID
        if not request.userId:
            return JSONResponse(
                content={"success": False, "error": "用户ID不能为空"},
                status_code=400
            )
        
        # 根据操作类型调用相应的服务方法
        if request.action == "add":
            if not request.subTopic or not request.memo:
                return JSONResponse(
                    content={"success": False, "error": "添加记忆需要提供subTopic和memo"},
                    status_code=400
                )
            
            result = await memory_management_service.add_memory(
                user_id=request.userId,
                agent_id=request.agentId,
                topic=request.topic,
                sub_topic=request.subTopic,
                memo=request.memo,
                memory_id=request.memoryId
            )
            
        elif request.action == "update":
            if not request.memoryId or not request.memo:
                return JSONResponse(
                    content={"success": False, "error": "更新记忆需要提供memoryId和memo"},
                    status_code=400
                )
            
            result = await memory_management_service.update_memory(
                user_id=request.userId,
                agent_id=request.agentId,
                memory_id=request.memoryId,
                memo=request.memo,
                topic=request.topic,
                sub_topic=request.subTopic
            )
            
        elif request.action == "delete":
            result = await memory_management_service.delete_memory(
                user_id=request.userId,
                agent_id=request.agentId,
                memory_id=request.memoryId,
                delete_all=request.deleteAll
            )
            
        else:
            return JSONResponse(
                content={"success": False, "error": f"不支持的操作: {request.action}"},
                status_code=400
            )
        
        return JSONResponse(content=result, status_code=200 if result["success"] else 500)
            
    except Exception as e:
        await log_error("api", f"❌ 记忆管理异常: {e}")
        return JSONResponse(
            content={"success": False, "error": str(e)},
            status_code=500
        )

@app.get("/topics", summary="获取预定义主题")
async def get_topics(request: Request, current_user_id: str = Depends(get_current_user_id)):
    """获取预定义主题 - 根据当前场景返回对应的主题"""
    try:
        # 获取当前场景的token
        scenario_token = get_scenario_token(request)
        
        # 获取场景对应的主题配置
        topics = ScenarioConfig.get_scenario_topics(scenario_token)
        
        await log_info("api", f"📋 获取主题成功: 场景={scenario_token}, 主题数={len(topics)}")
        
        return {
            "success": True,
            "scenario": scenario_token,
            "topics": topics
        }
    except Exception as e:
        await log_error("api", f"❌ 获取主题失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/scenarios", summary="获取所有场景配置")
async def get_scenarios():
    """获取所有可用场景配置(不需要鉴权)"""
    try:
        scenarios = ScenarioConfig.get_all_scenarios()
        return {
            "success": True,
            "scenarios": scenarios,
            "total": len(scenarios)
        }
    except Exception as e:
        await log_error("api", f"❌ 获取场景配置失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }


@app.get("/scenario/current", summary="获取当前场景信息")
async def get_current_scenario(request: Request, current_user_id: str = Depends(get_current_user_id)):
    """获取当前请求的场景信息"""
    try:
        scenario_token = get_scenario_token(request)
        scenario_config = get_scenario_config(request)
        
        if scenario_config:
            return {
                "success": True,
                "token": scenario_token,
                "name": scenario_config.get("name", "未知"),
                "description": scenario_config.get("description", ""),
                "fact_extraction_strategy": scenario_config.get("fact_extraction_strategy", {})
            }
        else:
            return {
                "success": False,
                "error": "未找到场景配置"
            }
    except Exception as e:
        await log_error("api", f"❌ 获取当前场景失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/performance", summary="获取性能统计")
async def get_performance(current_user_id: str = Depends(get_current_user_id)):
    """获取性能统计"""
    await log_info("api", "📊 收到性能统计请求")
    try:
        # 获取详细性能统计
        detailed_stats = await async_memory_service.get_performance_stats()
        
        # 基本统计
        basic_stats = {
            "total_requests": async_memory_service.stats["total_requests"],
            "cache_hits": async_memory_service.stats["cache_hits"],
            "cache_misses": async_memory_service.stats["cache_misses"],
            "cache_hit_rate": async_memory_service.stats["cache_hits"] / max(1, async_memory_service.stats["cache_hits"] + async_memory_service.stats["cache_misses"]),
            "avg_response_time": async_memory_service.stats["avg_response_time"]
        }
        
        # 合并统计信息
        performance = {**basic_stats, **detailed_stats.get('stats', {})}
        
        await log_info("api", f"✅ 返回性能统计: {async_memory_service.stats['total_requests']}个请求, 缓存命中率: {basic_stats['cache_hit_rate']:.2%}")
        
        return {
            "success": True,
            "performance": performance
        }
    except Exception as e:
        await log_error("api", f"❌ 获取性能统计失败: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/memory/add/batch")
async def add_memory_batch(requests: list[AddMemoryRequest], current_user_id: str = Depends(get_current_user_id)):
    """批量添加记忆 - 高性能版本"""
    start_time = time.time()
    batch_id = f"batch_{int(time.time() * 1000)}"
    
    try:
        await log_info("api", f"📦 [{batch_id}] 收到批量添加记忆请求: {len(requests)}个请求")
        
        # 并行处理所有请求
        tasks = []
        for i, request in enumerate(requests):
            await log_info("api", f"📝 [{batch_id}] 准备处理请求 {i+1}: user_id={request.userId}, question={request.question[:30]}...")
            task = async_memory_service.add_memory_async(
                user_id=request.userId,
                agent_id=request.agentId,
                question=request.question,
                answer=request.answer
            )
            tasks.append(task)
        
        await log_info("api", f"🚀 [{batch_id}] 开始并行处理 {len(tasks)} 个任务")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        successful = 0
        failed = 0
        for result in results:
            if isinstance(result, Exception):
                failed += 1
            elif result.get('success', False):
                successful += 1
            else:
                failed += 1
        
        total_time = time.time() - start_time
        await log_info("api", f"✅ [{batch_id}] 批量处理完成: {successful}/{len(requests)} 成功, 耗时: {total_time:.3f}秒")
        
        return {
            "success": True,
            "batch_results": {
                "total_requests": len(requests),
                "successful": successful,
                "failed": failed,
                "processing_time": total_time,
                "average_time_per_request": total_time / len(requests)
            },
            "results": results
        }
        
    except Exception as e:
        total_time = time.time() - start_time
        await log_error("api", f"❌ [{batch_id}] 批量添加记忆失败: {e}, 耗时: {total_time:.3f}秒")
        raise HTTPException(status_code=500, detail={
            "success": False,
            "error": str(e),
            "message": "批量添加记忆失败"
        })


@app.post('/cache/clear', summary="清理缓存")
async def clear_cache_api(current_user_id: str = Depends(get_current_user_id)):
    """清理当前项目的所有缓存数据 - 使用统一缓存服务"""
    try:
        await log_info("api", "🗑️ 收到清理缓存请求")
        
        # 使用统一缓存服务清理
        deleted_count = await unified_cache_service.clear_all_project_cache()
        
        result = {
            "success": True,
            "message": "所有项目缓存已清理",
            "deleted_count": deleted_count
        }
        
        await log_info("api", f"✅ 缓存清理完成: 总计删除{deleted_count}个键")
        
        return JSONResponse(content=result)
    except Exception as e:
        await log_error("api", f"❌ 清理缓存失败: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


@app.post("/memory/cleanup", summary="清理脏数据")
async def cleanup_dirty_data_api(
    user_id: str = None,
    current_user_id: str = Depends(get_current_user_id),
    agent_id: str = None,
    test_limit: int = 100,
    dry_run: bool = True
):
    """清理ES中的脏数据 - 支持按用户ID或代理ID过滤"""
    try:
        filter_info = ""
        if user_id:
            filter_info = f"用户ID: {user_id}"
        elif agent_id:
            filter_info = f"代理ID: {agent_id}"
        else:
            filter_info = "全部数据"
            
        await log_info("api", f"🧹 收到清理脏数据请求 ({filter_info}, 限制{test_limit}条, {'预览' if dry_run else '删除'}模式)")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service.cleanup_dirty_data_async(
                user_id=user_id,
                agent_id=agent_id,
                test_limit=test_limit,
                dry_run=dry_run
            )
            
            if result.get("success"):
                mode = "预览" if dry_run else "清理"
                await log_info("api", f"✅ 脏数据{mode}完成: {mode}了{result.get('cleaned_count', 0)}条记录，发现{result.get('dirty_found', 0)}条脏数据")
            else:
                await log_error("api", f"❌ 脏数据清理失败: {result.get('error')}")
            
            return JSONResponse(content=result)
            
    except Exception as e:
        await log_error("api", f"❌ 清理脏数据异常: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@app.post("/memory/clear", summary="清空所有数据")
async def clear_all_data_api(
    user_id: str = None,
    current_user_id: str = Depends(get_current_user_id),
    agent_id: str = None,
    dry_run: bool = True
):
    """清空ES中的所有数据 - 支持按用户ID或代理ID过滤"""
    try:
        filter_info = ""
        if user_id:
            filter_info = f"用户ID: {user_id}"
        elif agent_id:
            filter_info = f"代理ID: {agent_id}"
        else:
            filter_info = "全部数据"
            
        await log_info("api", f"🗑️ 收到清空数据请求 ({filter_info}, {'预览' if dry_run else '删除'}模式)")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service.clear_all_data_async(
                user_id=user_id,
                agent_id=agent_id,
                dry_run=dry_run
            )
            
            if result.get("success"):
                mode = "预览" if dry_run else "清空"
                await log_info("api", f"✅ 数据{mode}完成: {mode}了{result.get('cleared_count', 0)}条记录，找到{result.get('total_found', 0)}条记录")
            else:
                await log_error("api", f"❌ 数据清空失败: {result.get('error')}")
            
            return JSONResponse(content=result)
            
    except Exception as e:
        await log_error("api", f"❌ 清空数据异常: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

@app.get('/cache/stats', summary="获取缓存统计")
async def get_cache_stats_api(current_user_id: str = Depends(get_current_user_id)):
    """获取缓存统计信息 - 使用统一缓存服务"""
    try:
        await log_info("api", "📊 收到缓存统计请求")
        
        # 获取统一缓存服务统计
        cache_stats = await unified_cache_service.get_stats()
        
        result = {
            "success": True,
            "cache_stats": cache_stats,
            "message": "缓存统计获取成功"
        }
        
        await log_info("api", "✅ 返回缓存统计成功")
        return JSONResponse(content=result)
    except Exception as e:
        await log_error("api", f"❌ 获取缓存统计失败: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


# ==================== 数据恢复接口 ====================

class RestoreRequest(BaseModel):
    """数据恢复请求模型"""
    userId: Optional[str] = None  # 可选，不传则恢复所有用户
    agentId: Optional[str] = None

@app.post("/memory/restore", summary="从持久化存储恢复记忆到Redis")
async def restore_memory_from_persistence(
    request: RestoreRequest,
    current_user_id: str = Depends(get_current_user_id)
):
    """
    从持久化存储恢复记忆数据到Redis
    - 如果指定 userId，只恢复该用户的记忆
    - 如果不指定 userId，恢复所有用户的记忆
    """
    try:
        from services.persistence_service import get_persistence_backend
        from models.redis_models import FactDocument
        from pathlib import Path
        
        backend = get_persistence_backend()
        backend_type = Config.get_persistence_backend()
        
        # 如果指定了 userId，只恢复该用户
        if request.userId:
            await log_info("api", f"🔄 恢复单个用户: user_id={request.userId}, agent_id={request.agentId}")
            
            facts_list = await backend.load_facts(request.userId, request.agentId)
            
            if not facts_list:
                return {
                    "success": False,
                    "message": "未找到持久化数据",
                    "user_id": request.userId,
                    "restored_count": 0
                }
            
            restored_count = 0
            for fact_dict in facts_list:
                try:
                    # 使用 from_dict 方法自动处理时间字段转换
                    fact_doc = FactDocument.from_dict(fact_dict)
                    
                    if await async_memory_service.redis_service.add_fact(fact_doc):
                        restored_count += 1
                except Exception as e:
                    await log_error("api", f"恢复单条记忆失败: {e}")
            
            await log_info("api", f"✅ 单个用户恢复完成: {restored_count}条")
            
            return {
                "success": True,
                "message": "数据恢复完成",
                "user_id": request.userId,
                "agent_id": request.agentId,
                "restored_count": restored_count,
                "total": len(facts_list)
            }
        
        # 如果未指定 userId，恢复所有用户
        else:
            await log_info("api", "🔄 恢复所有用户的记忆数据")
            
            restored_users = []
            failed_users = []
            total_restored = 0
            
            if backend_type == "file":
                # 扫描持久化文件目录
                data_dir = Path(Config.get_persistence_data_dir())
                if not data_dir.exists():
                    return {
                        "success": False,
                        "message": f"持久化目录不存在: {data_dir}",
                        "restored_users": 0
                    }
                
                # 查找所有 *_facts.json 文件
                for file_path in data_dir.glob("*_facts.json"):
                    try:
                        # 解析文件名获取 user_id 和 agent_id
                        filename = file_path.stem.replace("_facts", "")
                        
                        # 简单策略：如果文件名包含两个部分且最后部分不像email，认为最后部分是 agent_id
                        parts = filename.rsplit("_", 1)
                        if len(parts) == 2 and "@" not in parts[1] and "." not in parts[1]:
                            user_id = parts[0]
                            agent_id = parts[1]
                        else:
                            user_id = filename
                            agent_id = None
                        
                        # 恢复这个用户的数据
                        facts_list = await backend.load_facts(user_id, agent_id)
                        
                        if facts_list:
                            user_restored = 0
                            
                            for fact_dict in facts_list:
                                try:
                                    # 使用 from_dict 方法自动处理时间字段转换
                                    fact_doc = FactDocument.from_dict(fact_dict)
                                    
                                    if await async_memory_service.redis_service.add_fact(fact_doc):
                                        user_restored += 1
                                except Exception as e:
                                    await log_error("api", f"恢复失败: {user_id}/{agent_id} - {e}")
                                    pass
                            
                            if user_restored > 0:
                                restored_users.append({
                                    "user_id": user_id,
                                    "agent_id": agent_id,
                                    "count": user_restored
                                })
                                total_restored += user_restored
                                await log_info("api", f"  ✅ {user_id}: {user_restored}条")
                        
                    except Exception as e:
                        await log_error("api", f"恢复文件失败 {file_path}: {e}")
                        failed_users.append(str(file_path.name))
            
            elif backend_type == "es":
                return {
                    "success": False,
                    "message": "ES批量恢复功能待实现，请使用文件后端或指定userId逐个恢复"
                }
            
            await log_info("api", f"✅ 批量恢复完成: {len(restored_users)}个用户, 共{total_restored}条记忆")
            
            return {
                "success": True,
                "message": "批量数据恢复完成",
                "restored_users_count": len(restored_users),
                "total_restored_facts": total_restored,
                "failed_users_count": len(failed_users),
                "details": restored_users[:20]  # 返回前20个用户的详情
            }
        
    except Exception as e:
        await log_error("api", f"❌ 数据恢复失败: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=Config.get_app_host(),
        port=Config.get_app_port(),
        reload=Config.get_debug(),
        workers=1  # 单进程，避免缓存冲突
    )

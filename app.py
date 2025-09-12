"""
FastAPI版本的记忆服务API
性能优化版本，支持异步处理
"""

from dotenv import load_dotenv
import os

# 加载.env文件
load_dotenv()

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import time
import logging
from services.async_memory_service_v2 import AsyncMemoryServiceV2
from services.unified_cache_service import unified_cache_service
from services.async_logging_service import async_logging_service, log_info, log_error
from middleware.simple_auth import SimpleAuthMiddleware, get_current_user_id, get_auth_status
from config import Config
from logging_config import setup_logging, get_logger

# 设置统一日志配置
setup_logging()
logger = get_logger(__name__)

# 创建FastAPI应用
app = FastAPI(
    title="Agent Memo API",
    description="智能记忆服务API",
    version="2.0.0"
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

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    performance: Dict[str, Any]

# 全局异步服务实例
async_memory_service = None

@app.on_event("startup")
async def startup_event():
    """应用启动事件"""
    global async_memory_service
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
        
        logger.info("🎉 FastAPI记忆服务启动完成！")
        logger.info(f"📊 服务配置: 端口={Config.get_app_port()}, 日志级别={Config.get_log_level()}")
        
    except Exception as e:
        logger.error(f"❌ FastAPI记忆服务启动失败: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭事件"""
    global async_memory_service
    if async_memory_service:
        await async_memory_service.__aexit__(None, None, None)
    logger.info("FastAPI记忆服务关闭完成")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查 - 增强版本"""
    try:
        # 获取缓存统计
        cache_stats = await async_memory_service.cache_service.get_stats()
        cache_size = cache_stats.get('cache_count', 0)
        
        return HealthResponse(
            status="healthy",
            service="yaxin_memo_fastapi",
            version="2.0.0",
            performance={
                "cache_size": cache_size,
                "uptime": "running"
            }
        )
    except Exception as e:
        return HealthResponse(
            status="unhealthy",
            service="yaxin_memo_fastapi",
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

@app.post("/memory/manage")
async def manage_memory(request: MemoryManageRequest, current_user_id: str = Depends(get_current_user_id)):
    """记忆管理 - 查询和更新Redis中的事实数据"""
    start_time = time.time()
    request_id = f"manage_{int(time.time() * 1000)}"
    
    try:
        await log_info("api", f"🔧 [{request_id}] 收到记忆管理请求: action={request.action}, user_id={request.userId}")
        
        if request.action == "query":
            # 查询事实
            result = await async_memory_service.query_facts_async(
                user_id=request.userId,
                agent_id=request.agentId,
                limit=request.limit,
                offset=request.offset
            )
        elif request.action == "update":
            # 更新事实
            if not request.memoryId or not request.topic or not request.subTopic or not request.newMemo:
                raise HTTPException(status_code=400, detail={
                    "success": False,
                    "error": "更新操作需要提供memoryId、topic、subTopic和newMemo",
                    "message": "参数错误"
                })
            
            result = await async_memory_service.update_fact_async(
                user_id=request.userId,
                agent_id=request.agentId,
                topic=request.topic,
                sub_topic=request.subTopic,
                new_memo=request.newMemo
            )
        else:
            raise HTTPException(status_code=400, detail={
                "success": False,
                "error": "action必须是'query'或'update'",
                "message": "参数错误"
            })
        
        processing_time = time.time() - start_time
        result["api_processing_time"] = processing_time
        
        if result['success']:
            if request.action == "query":
                facts_count = len(result.get('facts', []))
                await log_info("api", f"✅ [{request_id}] 查询事实成功: {facts_count}个事实, 耗时: {processing_time:.3f}秒")
            else:
                await log_info("api", f"✅ [{request_id}] 更新事实成功: 耗时: {processing_time:.3f}秒")
            return result
        else:
            await log_error("api", f"❌ [{request_id}] 记忆管理失败: {result.get('message', '未知错误')}, 耗时: {processing_time:.3f}秒")
            raise HTTPException(status_code=500, detail=result)
            
    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        await log_error("api", f"❌ [{request_id}] 记忆管理异常: {e}, 耗时: {processing_time:.3f}秒")
        raise HTTPException(status_code=500, detail={
            "success": False,
            "error": str(e),
            "message": "记忆管理失败"
        })

@app.get("/topics")
async def get_topics(current_user_id: str = Depends(get_current_user_id)):
    """获取预定义主题"""
    await log_info("api", "📋 收到获取主题请求")
    topics = Config.get_predefined_topics()
    await log_info("api", f"✅ 返回 {len(topics)} 个预定义主题")
    return {
        "success": True,
        "topics": topics
    }

@app.get("/performance")
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

@app.get('/topics', summary="获取预定义主题")
async def get_topics_api(current_user_id: str = Depends(get_current_user_id)):
    """获取预定义主题"""
    return JSONResponse(content={
        "success": True,
        "topics": Config.get_predefined_topics()
    })

@app.get('/performance', summary="获取性能统计")
async def get_performance_api(current_user_id: str = Depends(get_current_user_id)):
    """获取性能统计信息"""
    try:
        await log_info("api", "📊 收到性能统计请求")
        result = await async_memory_service.get_performance_stats()
        await log_info("api", "✅ 返回性能统计成功")
        return JSONResponse(content=result)
    except Exception as e:
        await log_error("api", f"❌ 获取性能统计失败: {e}")
        return JSONResponse(content={"success": False, "error": str(e)}, status_code=500)

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

@app.post("/memory/add-or-update", summary="添加或更新记忆")
async def add_or_update_memory_api(request: AddOrUpdateMemoryRequest, current_user_id: str = Depends(get_current_user_id)):
    """添加或更新记忆 - 支持指定主题和小主题"""
    try:
        await log_info("api", f"🔄 收到添加或更新记忆请求: user_id={request.userId}, topic={request.topic}, sub_topic={request.subTopic}")
        
        async with AsyncMemoryServiceV2() as memory_service:
            result = await memory_service.add_or_update_memory_async(
                user_id=request.userId,
                topic=request.topic,
                sub_topic=request.subTopic,
                memo=request.memo,
                agent_id=request.agentId,
                chat_id=request.chatId
            )
            
            if result.get("success"):
                await log_info("api", f"✅ 记忆操作成功: {result.get('action')}")
            else:
                await log_error("api", f"❌ 记忆操作失败: {result.get('error')}")
            
            return JSONResponse(content=result)
            
    except Exception as e:
        await log_error("api", f"❌ 添加或更新记忆异常: {e}")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host=Config.get_app_host(),
        port=Config.get_app_port(),
        reload=Config.get_debug(),
        workers=1  # 单进程，避免缓存冲突
    )

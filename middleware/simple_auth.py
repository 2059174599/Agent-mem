"""
简单鉴权中间件 - 基于Header验证，支持多场景
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import List, Callable
from logging_config import get_logger

logger = get_logger(__name__)


class SimpleAuthMiddleware(BaseHTTPMiddleware):
    """简单鉴权中间件 - 基于Header验证，支持多场景token"""
    
    def __init__(self, app, auth_token: str = "yixinagentmemory", excluded_paths: List[str] = None):
        super().__init__(app)
        self.auth_token = auth_token  # 保留用于向后兼容
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register",
            "/scenarios"  # 新增: 场景列表接口
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求 - 支持多场景token验证"""
        try:
            # 检查是否在排除路径中
            if self._is_excluded_path(request.url.path):
                return await call_next(request)
            
            # 获取认证Token
            auth_header = request.headers.get("Authorization")
            if not auth_header:
                return self._create_auth_error_response("缺少Authorization头")
            
            # 验证Token格式
            if not auth_header.startswith("Bearer "):
                return self._create_auth_error_response("Authorization头格式错误，应为 'Bearer <token>'")
            
            token = auth_header[7:]  # 移除 "Bearer " 前缀
            
            # 验证Token - 支持多场景
            from config_scenarios import ScenarioConfig
            
            # 检查是否为有效的场景token
            if not ScenarioConfig.is_valid_token(token):
                # 向后兼容: 检查是否为旧的默认token
                if token != self.auth_token:
                    return self._create_auth_error_response("无效的认证Token")
            
            # 将场景信息添加到请求状态
            request.state.user_id = "authenticated_user"
            request.state.is_authenticated = True
            request.state.scenario_token = token  # 存储场景token
            request.state.scenario_config = ScenarioConfig.get_scenario_config(token)
            
            # 记录场景信息
            scenario_name = request.state.scenario_config.get("name", "未知场景") if request.state.scenario_config else "通用场景"
            logger.info(f"请求场景: {scenario_name} (token: {token[:10]}...)")
            
            # 继续处理请求
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"鉴权中间件错误: {e}")
            return self._create_auth_error_response("认证处理失败")
    
    def _is_excluded_path(self, path: str) -> bool:
        """检查路径是否在排除列表中"""
        for excluded_path in self.excluded_paths:
            if path == excluded_path or path.startswith(excluded_path):
                return True
        return False
    
    def _create_auth_error_response(self, message: str) -> JSONResponse:
        """创建认证错误响应"""
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "unauthorized",
                "error_description": message,
                "error_code": "invalid_token"
            }
        )


def get_current_user_id(request: Request) -> str:
    """获取当前用户ID（简化版）"""
    user_id = getattr(request.state, 'user_id', None)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户未认证"
        )
    return user_id


def get_auth_status(request: Request) -> bool:
    """获取认证状态"""
    return getattr(request.state, 'is_authenticated', False)


def get_scenario_token(request: Request) -> str:
    """获取当前请求的场景token"""
    return getattr(request.state, 'scenario_token', 'yixinagentmemory')


def get_scenario_config(request: Request) -> dict:
    """获取当前请求的场景配置"""
    return getattr(request.state, 'scenario_config', None)

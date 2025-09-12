"""
简单鉴权中间件 - 基于Header验证
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import List, Callable
from logging_config import get_logger

logger = get_logger(__name__)


class SimpleAuthMiddleware(BaseHTTPMiddleware):
    """简单鉴权中间件 - 基于Header验证"""
    
    def __init__(self, app, auth_token: str = "yixinagentmemory", excluded_paths: List[str] = None):
        super().__init__(app)
        self.auth_token = auth_token
        self.excluded_paths = excluded_paths or [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/auth/login",
            "/auth/register"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求"""
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
            
            # 验证Token
            if token != self.auth_token:
                return self._create_auth_error_response("无效的认证Token")
            
            # 将用户信息添加到请求状态（简化版）
            request.state.user_id = "authenticated_user"
            request.state.is_authenticated = True
            
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

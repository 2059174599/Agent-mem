#!/bin/bash

# yaxin_memo Docker构建脚本 - 支持国内网络环境

set -e

echo "🐳 开始构建 yaxin_memo Docker镜像..."

# 检查Docker是否运行
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker 未运行，请先启动 Docker"
    exit 1
fi

# 检查当前架构
ARCH=$(uname -m)
echo "🔍 检测到系统架构: $ARCH"

# 设置构建参数
IMAGE_NAME="yaxin-memo"
TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

# 清理旧镜像
echo "🧹 清理旧镜像..."
docker rmi $FULL_IMAGE_NAME 2>/dev/null || true

# 构建镜像 - 按优先级尝试不同版本
echo "🔨 构建Docker镜像..."

# 首先尝试超简单版本（避免网络问题）
if [ -f "Dockerfile.minimal" ]; then
    echo "🔨 使用超简单版本Dockerfile构建..."
    if docker build -f Dockerfile.minimal -t $FULL_IMAGE_NAME .; then
        echo "✅ 使用超简单版本Dockerfile构建成功！"
    else
        echo "⚠️  超简单版本构建失败，尝试其他版本..."
        
        # 如果超简单版本失败，尝试简单版本
        if [ -f "Dockerfile.simple" ]; then
            echo "🔨 使用简单版本Dockerfile构建..."
            if docker build -f Dockerfile.simple -t $FULL_IMAGE_NAME .; then
                echo "✅ 使用简单版本Dockerfile构建成功！"
            else
                echo "⚠️  简单版本也失败，尝试兼容版本..."
                
                # 如果简单版本失败，尝试兼容版本
                if [ -f "Dockerfile.compat" ]; then
                    echo "🔨 使用兼容版本Dockerfile构建..."
                    if docker build -f Dockerfile.compat -t $FULL_IMAGE_NAME .; then
                        echo "✅ 使用兼容版本Dockerfile构建成功！"
                    else
                        echo "⚠️  兼容版本也失败，尝试主版本..."
                        
                        # 如果兼容版本失败，尝试主版本
                        if docker build -t $FULL_IMAGE_NAME .; then
                            echo "✅ 使用主Dockerfile构建成功！"
                        else
                            echo "❌ 所有Dockerfile版本都构建失败！"
                            echo "🔧 建议检查网络连接或手动构建"
                            exit 1
                        fi
                    fi
                else
                    echo "❌ 未找到兼容版本Dockerfile，构建失败！"
                    exit 1
                fi
            fi
        else
            echo "❌ 未找到简单版本Dockerfile，构建失败！"
            exit 1
        fi
    fi
else
    echo "⚠️  未找到超简单版本Dockerfile，尝试其他版本..."
    
    # 如果没有超简单版本，尝试简单版本
    if [ -f "Dockerfile.simple" ]; then
        echo "🔨 使用简单版本Dockerfile构建..."
        if docker build -f Dockerfile.simple -t $FULL_IMAGE_NAME .; then
            echo "✅ 使用简单版本Dockerfile构建成功！"
        else
            echo "⚠️  简单版本构建失败，尝试兼容版本..."
            
            # 如果简单版本失败，尝试兼容版本
            if [ -f "Dockerfile.compat" ]; then
                echo "🔨 使用兼容版本Dockerfile构建..."
                if docker build -f Dockerfile.compat -t $FULL_IMAGE_NAME .; then
                    echo "✅ 使用兼容版本Dockerfile构建成功！"
                else
                    echo "⚠️  兼容版本也失败，尝试主版本..."
                    
                    # 如果兼容版本失败，尝试主版本
                    if docker build -t $FULL_IMAGE_NAME .; then
                        echo "✅ 使用主Dockerfile构建成功！"
                    else
                        echo "❌ 所有Dockerfile版本都构建失败！"
                        echo "🔧 建议检查网络连接或手动构建"
                        exit 1
                    fi
                fi
            else
                echo "❌ 未找到兼容版本Dockerfile，构建失败！"
                exit 1
            fi
        fi
    else
        echo "⚠️  未找到简单版本Dockerfile，尝试其他版本..."
        
        # 如果没有简单版本，尝试兼容版本
        if [ -f "Dockerfile.compat" ]; then
            echo "🔨 使用兼容版本Dockerfile构建..."
            if docker build -f Dockerfile.compat -t $FULL_IMAGE_NAME .; then
                echo "✅ 使用兼容版本Dockerfile构建成功！"
            else
                echo "⚠️  兼容版本构建失败，尝试主版本..."
                
                # 如果兼容版本失败，尝试主版本
                if docker build -t $FULL_IMAGE_NAME .; then
                    echo "✅ 使用主Dockerfile构建成功！"
                else
                    echo "❌ 所有Dockerfile版本都构建失败！"
                    echo "🔧 建议检查网络连接或手动构建"
                    exit 1
                fi
            fi
        else
            echo "⚠️  未找到兼容版本Dockerfile，尝试主版本..."
            
            # 如果没有兼容版本，尝试主版本
            if docker build -t $FULL_IMAGE_NAME .; then
                echo "✅ 使用主Dockerfile构建成功！"
            else
                echo "❌ 主Dockerfile构建失败！"
                echo "🔧 建议检查网络连接或手动构建"
                exit 1
            fi
        fi
    fi
fi

# 验证镜像构建成功
if docker images | grep -q "$IMAGE_NAME.*$TAG"; then
    echo "✅ Docker镜像构建成功！"
    echo "📦 镜像信息:"
    docker images | grep "$IMAGE_NAME"
    
    # 显示镜像详情
    echo ""
    echo "🔍 镜像详情:"
    docker inspect $FULL_IMAGE_NAME | grep -E '"Architecture"|"Os"|"Size"'
    
    echo ""
    echo "🎉 构建完成！现在可以使用以下命令启动应用："
    echo "   ./start.sh app-only    # 只启动后台服务"
    echo "   ./start.sh source      # 源码启动"
    echo "   ./start.sh full        # 完整部署"
    
else
    echo "❌ Docker镜像构建失败！"
    exit 1
fi

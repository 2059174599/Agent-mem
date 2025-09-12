.PHONY: help install install-dev install-prod run test clean lint format check

# 默认目标
help:
	@echo "Yaxin Memo - 智能记忆管理系统"
	@echo ""
	@echo "可用命令:"
	@echo "  install      安装生产环境依赖"
	@echo "  install-dev  安装开发环境依赖"
	@echo "  install-prod 安装生产环境依赖"
	@echo "  run          启动开发服务器"
	@echo "  run-prod     启动生产服务器"
	@echo "  test         运行测试"
	@echo "  test-cov     运行测试并生成覆盖率报告"
	@echo "  lint         代码检查"
	@echo "  format       代码格式化"
	@echo "  check        运行所有检查"
	@echo "  clean        清理临时文件"
	@echo "  logs         查看日志"
	@echo "  docker-build 构建Docker镜像"
	@echo "  docker-run   运行Docker容器"

# 安装依赖
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

install-prod:
	pip install -r requirements-prod.txt

# 启动服务
run:
	python app.py

run-prod:
	gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# 测试
test:
	python -m pytest test/ -v

test-cov:
	python -m pytest test/ --cov=. --cov-report=html --cov-report=term-missing

# 代码质量
lint:
	flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 . --count --exit-zero --max-complexity=10 --max-line-length=88 --statistics
	mypy .

format:
	black .
	isort .

check: format lint test

# 清理
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/
	rm -rf dist/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/

# 日志
logs:
	tail -f logs/app.log

# Docker
docker-build:
	docker build -t yaxin-memo .

docker-run:
	docker run -p 8000:8000 --env-file .env yaxin-memo

# 数据库初始化
init-db:
	@echo "初始化数据库..."
	@echo "请确保Redis和Elasticsearch服务正在运行"
	@echo "然后运行: python -c 'from models.redis_models import RedisService; from models.es_models import ESService; print(\"数据库初始化完成\")'"

# 健康检查
health:
	curl -f http://localhost:8000/health || echo "服务未运行"

# 部署检查
deploy-check: clean check test
	@echo "部署检查完成"

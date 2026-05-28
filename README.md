# Python 股票分析项目

基于 FastAPI 的 股票分析项目。

## 技术栈

- **Python 3.10+** - 核心语言
- **FastAPI** - 高性能异步 Web 框架
- **SQLModel** - ORM 层（结合 SQLAlchemy + Pydantic）
- **Redis** - 任务状态存储 + SSE 事件广播
- **MySQL** - 主数据库（支持同步/异步访问）
- **Poetry** - 依赖管理
- **Loguru** - 日志系统（支持多通道过滤）
- **Docker** - 容器化部署

## 快速开始

### 1. 安装依赖

```bash
poetry install
```

### 2. 配置环境变量

复制 `.env` 文件并配置必要参数：

```bash
# 数据库配置
DB_HOST=your_db_host
DB_PORT=3306
DB_USER=your_user
DB_PASSWORD=your_password
DB_NAME=your_database

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your_password
REDIS_DB=0

# 日志级别
LOG_LEVEL=INFO

# 运行模式
RUN_MODE=local  # 启用调试端点
```

### 3. 启动服务

```bash
# 开发模式（自动重载）
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8168

# 生产模式
poetry run uvicorn app.main:app --host 0.0.0.0 --port 8168 --workers 4
```

## 项目结构

```
app/
├── main.py              # FastAPI 应用入口
├── api/
│   └── v1/
│       ├── router.py    # API 路由聚合
│       └── endpoints/   # 各业务端点
├── core/
│   ├── config.py        # 配置管理（pydantic-settings）
│   ├── db.py            # 数据库连接（同步/异步）
│   ├── task_store.py    # Redis 任务存储 + SSE
│   ├── logger.py        # 日志配置（双通道）
│   ├── middleware.py    # ASGI 日志中间件
│   ├── exceptions.py    # 全局异常处理
│   └── retry.py         # 网络重试配置
├── models/              # SQLModel ORM 模型
├── schemas/             # Pydantic 请求/响应结构
├── services/            # 业务逻辑层
├── utils/               # 工具函数
└── static/              # 静态文件
```

## 核心功能

### 1. 异步数据库访问

- 同步引擎：简单查询场景
- 异步引擎：高并发场景，自动提交/回滚

```python
from app.core.db import get_async_db

@app.post("/items")
async def create_item(item: ItemCreate, db: AsyncSession = Depends(get_async_db)):
    # 自动提交成功，异常自动回滚
    ...
```

### 2. Redis 任务管理 + SSE 流式推送

支持异步任务状态追踪和实时事件推送：

```python
from app.core.task_store import create_task_async, update_task_async

# 创建任务
await create_task_async(task_id)

# 更新状态并广播
await update_task_async(task_id, status="completed", data=result)
```

### 3. 双通道日志系统

- **app.log**: 常规应用日志
- **ai_trace.log**: AI 相关日志（避免刷屏）

```python
from loguru import logger

# 普通日志
logger.info("常规日志")

# AI 追踪日志（仅写入 ai_trace.log）
logger.bind(channel="ai").info("AI 处理过程...")
```

### 4. 全局异常处理

统一 JSON 响应格式：

```json
{
  "errCode": 422,
  "errMsg": "参数校验失败: field - message",
  "data": null
}
```

### 5. 代码生成器

从 MySQL 表结构自动生成 SQLModel 模型 + Service 服务类：

```bash
# 查看数据库所有表
poetry run python app/services/code_generator.py --db-name <database> --list-tables

# 生成单表代码
poetry run python app/services/code_generator.py --db-name <database> --table <table_name> --output ./output

# 生成多表代码
poetry run python app/services/code_generator.py --db-name <database> --tables table1 table2 --output ./output
```

生成的 Service 类包含：`fetch`, `list`, `query_list`, `query_one`, `create`, `update`, `delete` 方法。

## Docker 部署

### 构建镜像

```bash
docker build -t registry.cn-shenzhen.aliyuncs.com/speechx/llm-gateway:<tag> .
```

### 运行容器

```bash
docker run -d \
  -p 8008:8008 \
  --env-file .env \
  registry.cn-shenzhen.aliyuncs.com/speechx/llm-gateway:<tag>
```

### 推送镜像

```bash
docker push registry.cn-shenzhen.aliyuncs.com/speechx/llm-gateway:<tag>
```

## 开发工具

### Lint & 格式化

```bash
poetry run ruff check app/
poetry run ruff format app/
```

### 类型检查

```bash
poetry run mypy app/
```

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `API_V1_STR` | API 路径前缀 | `/api/v1` |
| `RUN_MODE` | 运行模式 | `prod` |
| `PROMPT_DIR` | Prompt 模板目录 | `./prompts` |
| `PDF_CONVERT_MAX_WORKERS` | 最大并发任务数 | 2 |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `ENABLE_NACOS` | 启用 Nacos 注册 | `True` |

## 许可证

MIT License
# 1. 基础镜像
FROM python:3.10-slim

# 2. 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 3. 设置工作目录
WORKDIR /app


# 4. 安装 Poetry (作为一个单独的层，利用缓存)
# 这里的 pip install poetry 也会产生体积，但比 apt-get build-essential 小得多
RUN pip install --no-cache-dir poetry

# 5. 复制依赖文件
COPY pyproject.toml poetry.lock* /app/

# 6. 安装依赖 (核心优化)
# config virtualenvs.create false: 让 poetry 直接装到系统 Python，不创建 venv
# --no-root: 暂时不安装当前项目本身 (因为代码还没拷进来)
# --only main: 只安装生产环境依赖 (不装 dev 依赖，如 pytest)
RUN poetry config virtualenvs.create false \
    && poetry install --no-root --only main --no-interaction --no-ansi

# 7. 复制项目代码
COPY . /app

# 8. 暴露端口
EXPOSE 8168

# 9. 启动命令
CMD ["gunicorn", "app.main:app", \
     "-w", "4", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8168", \
     "--timeout", "180", \
     "--access-logfile", "-", \
     "--error-logfile", "-"]
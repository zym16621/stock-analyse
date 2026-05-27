import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.config import settings

# 引入您已经写好的工具类和方法
from app.services.code_generator import DatabaseReader, ModelGenerator, ServiceGenerator, to_snake_case

router = APIRouter()

# =========================
# 1. 定义请求数据验证 Schema
# =========================
class GenerateCodeRequest(BaseModel):
    tables: List[str]                     # 需要生成的表名列表
    db_name: Optional[str] = None         # 数据库名 (可选，优先使用)
    db_host: Optional[str] = None         # 数据库主机 (可选)
    db_port: Optional[int] = None         # 数据库端口 (可选)
    db_user: Optional[str] = None         # 数据库用户 (可选)
    db_password: Optional[str] = None     # 数据库密码 (可选)
    model_path: str = "app.models"        # 默认的模型导入路径

# =========================
# 2. 辅助方法：自动追加 import 到 __init__.py
# =========================
def append_to_init(dir_path: str, import_statement: str):
    """检查并向指定目录的 __init__.py 追加 import 语句"""
    init_file = os.path.join(dir_path, "__init__.py")
    
    # 如果文件不存在则创建
    if not os.path.exists(init_file):
        with open(init_file, "w", encoding="utf-8") as f:
            pass
            
    with open(init_file, "r", encoding="utf-8") as f:
        content = f.read()
        
    # 避免重复 import
    if import_statement not in content:
        prefix = "\n" if content and not content.endswith("\n") else ""
        with open(init_file, "a", encoding="utf-8") as f:
            f.write(f"{prefix}{import_statement}\n")

# =========================
# 3. 核心接口逻辑
# =========================
@router.post("/generate", summary="批量生成表对应的代码到本地(防覆盖并自动Import)")
def generate_tables_code(
    req: GenerateCodeRequest,
    db: Session = Depends(get_db)
):
    """
    传入数据库表名列表，生成对应的 SQLModel 和 Service 文件直接保存到项目目录。
    遇到同名文件将自动跳过，新生成的文件会自动追加 import 到 __init__.py。

    ⚠️ 安全警告：此接口仅在开发环境启用，生产环境禁止访问
    """
    # 环境安全检查
    if settings.RUN_MODE not in ("local", "dev"):
        logger.error(f"生产环境禁止访问代码生成接口 | RUN_MODE={settings.RUN_MODE}")
        raise HTTPException(
            status_code=403,
            detail="此接口仅在开发环境启用，生产环境禁止访问"
        )

    if not req.tables:
        raise HTTPException(status_code=400, detail="未提供需要生成的表名列表 (tables 不能为空)")

    # 1. 解析数据库连接信息（优先取请求参数，其次取依赖注入的 db 连接）
    bind = db.get_bind()
    url = bind.url

    db_name = req.db_name or url.database
    if not db_name:
        raise HTTPException(status_code=400, detail="未指定数据库名称，且无法从系统配置中获取")
        
    db_host = req.db_host or url.host or "127.0.0.1"
    db_port = req.db_port or url.port or 3306
    db_user = req.db_user or url.username or "root"
    db_password = req.db_password if req.db_password is not None else (url.password or "")

    # 2. 建立数据库读取器
    try:
        reader = DatabaseReader(db_host, db_port, db_user, db_password, db_name)
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        raise HTTPException(status_code=500, detail=f"数据库连接失败: {str(e)}")

    # 3. 定义保存文件的目标目录
    base_dir = os.getcwd()
    model_dir = os.path.join(base_dir, "app", "models")
    service_dir = os.path.join(base_dir, "app", "services", "db")
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(service_dir, exist_ok=True)

    generated_files = []
    skipped_files = []
    

    for table_name in req.tables:
        try:
            config = reader.get_table_structure(table_name)
            snake_name = to_snake_case(config.class_name)
            class_name = config.class_name

            # === 处理 Model ===
            model_file_path = os.path.join(model_dir, f"{snake_name}.py")
            if os.path.exists(model_file_path):
                skipped_files.append(model_file_path)
            else:
                model_code = ModelGenerator(config).generate()
                with open(model_file_path, "w", encoding="utf-8") as f:
                    f.write(model_code)
                generated_files.append(model_file_path)
                append_to_init(model_dir, f"from .{snake_name} import {class_name}")

            # === 处理 Service ===
            service_file_path = os.path.join(service_dir, f"{snake_name}_service.py")
            if os.path.exists(service_file_path):
                skipped_files.append(service_file_path)
            else:
                service_code = ServiceGenerator(config, req.model_path).generate()
                with open(service_file_path, "w", encoding="utf-8") as f:
                    f.write(service_code)
                generated_files.append(service_file_path)
                append_to_init(service_dir, f"from .{snake_name}_service import {snake_name}_service")
            
        except Exception as e:
            logger.error(f"表 '{table_name}' 生成失败: {e}")
            raise HTTPException(status_code=500, detail=f"生成表 '{table_name}' 失败: {str(e)}")
        
    # 5. 返回处理结果状态
    return {
        "errCode": 200,
        "errMsg": "代码处理完成",
        "data": {
            "tables": req.tables,
            "generated_files": generated_files,
            "skipped_files": skipped_files
        }
    }
     
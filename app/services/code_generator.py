#!/usr/bin/env python3
"""
代码生成器 - 根据数据库表结构生成 SQLModel 模型文件和 Service 文件

使用方法:
    # 从数据库直接读取表结构
    python code_generator.py --db-host 127.0.0.1 --db-user root --db-password xxx --db-name stock --table index_daily --output ./output
    
    # 从配置文件读取
    python code_generator.py --config table_config.json --output ./output
    
    # 使用环境变量中的数据库配置
    python code_generator.py --db-name stock --table index_daily --output ./output
"""

import argparse
import os
import re
from pathlib import Path
from typing import Dict, List, Optional

# 数据库连接
try:
    import pymysql
    HAS_PYMYSQL = True
except ImportError:
    HAS_PYMYSQL = False


# ============== 类型映射 ==============
TYPE_MAPPING = {
    # MySQL 类型 -> (Python类型, SQLAlchemy类型, 是否需要长度)
    "int": ("int", "Integer", False),
    "integer": ("int", "Integer", False),
    "tinyint": ("int", "Integer", False),
    "smallint": ("int", "Integer", False),
    "mediumint": ("int", "Integer", False),
    "bigint": ("int", "Integer", False),
    
    "varchar": ("str", "String", True),
    "char": ("str", "String", True),
    "text": ("str", "Text", False),
    "longtext": ("str", "Text", False),
    "mediumtext": ("str", "Text", False),
    
    "datetime": ("datetime", "DateTime", False),
    "timestamp": ("datetime", "DateTime", False),
    "date": ("date", "Date", False),
    "time": ("time", "Time", False),
    
    "float": ("float", "Float", False),
    "double": ("float", "Float", False),
    "decimal": ("Decimal", "Numeric", False),
    "numeric": ("Decimal", "Numeric", False),
    
    "boolean": ("bool", "Boolean", False),
    "bool": ("bool", "Boolean", False),
    
    "json": ("dict", "JSON", False),
}


def parse_db_type(db_type: str) -> tuple:
    """
    解析数据库类型，返回 (基础类型名, 长度, 精度, 是否无符号)
    例如: "VARCHAR(255)" -> ("varchar", 255, None, False)
         "DECIMAL(12,4)" -> ("decimal", 12, 4, False)
    """
    db_type = db_type.strip().lower()
    
    # 提取长度参数
    length = None
    precision = None
    if "(" in db_type:
        base = db_type.split("(")[0].strip()
        params = db_type.split("(")[1].split(")")[0]
        try:
            if "," in params:
                # decimal(10,2) 的情况
                parts = params.split(",")
                length = int(parts[0].strip())
                precision = int(parts[1].strip())
            else:
                length = int(params.strip())
        except:
            pass
    else:
        base = db_type
    
    # 检查是否无符号
    unsigned = "unsigned" in db_type
    
    return base, length, precision, unsigned


def get_python_type(db_type: str) -> tuple:
    """
    根据数据库类型获取 Python 类型和 SQLAlchemy 类型
    返回: (python_type, sa_type, length, precision)
    """
    base_type, length, precision, unsigned = parse_db_type(db_type)
    
    if base_type in TYPE_MAPPING:
        py_type, sa_type, needs_length = TYPE_MAPPING[base_type]
        return py_type, sa_type, length if needs_length else None, precision
    
    # 未知类型默认为 str
    return "str", "String", length, None


def to_snake_case(name: str) -> str:
    """转换为下划线命名"""
    name = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name).lower()


def to_pascal_case(name: str) -> str:
    """转换为帕斯卡命名"""
    # 处理下划线命名
    parts = name.lower().replace("-", "_").split("_")
    return "".join(part.capitalize() for part in parts if part)


def to_camel_case(name: str) -> str:
    """转换为驼峰命名"""
    pascal = to_pascal_case(name)
    return pascal[0].lower() + pascal[1:] if pascal else pascal


class TableConfig:
    """表配置类"""
    
    def __init__(self, table_name: str, class_name: Optional[str] = None, 
                 comment: str = "", fields: List[Dict] = None):
        self.table_name = table_name
        self.class_name = class_name or to_pascal_case(table_name)
        self.comment = comment
        self.fields = fields or []
    
    @classmethod
    def from_dict(cls, data: Dict) -> "TableConfig":
        return cls(
            table_name=data["table_name"],
            class_name=data.get("class_name"),
            comment=data.get("comment", ""),
            fields=data.get("fields", [])
        )


class DatabaseReader:
    """数据库表结构读取器"""
    
    def __init__(self, host: str, port: int, user: str, password: str, database: str):
        if not HAS_PYMYSQL:
            raise ImportError("需要安装 pymysql: pip install pymysql")
        
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
    
    def get_table_structure(self, table_name: str) -> TableConfig:
        """读取表结构并返回 TableConfig"""
        conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4'
        )
        
        try:
            cursor = conn.cursor()
            
            # 获取表注释
            cursor.execute("""
                SELECT TABLE_COMMENT 
                FROM information_schema.TABLES 
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """, (self.database, table_name))
            table_comment_row = cursor.fetchone()
            table_comment = table_comment_row[0] if table_comment_row else ""
            
            # 获取列信息
            cursor.execute("""
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    COLUMN_TYPE,
                    IS_NULLABLE,
                    COLUMN_KEY,
                    COLUMN_DEFAULT,
                    EXTRA,
                    COLUMN_COMMENT
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                ORDER BY ORDINAL_POSITION
            """, (self.database, table_name))
            
            columns = cursor.fetchall()
            
            fields = []
            for col in columns:
                col_name, data_type, col_type, is_nullable, col_key, col_default, extra, col_comment = col
                
                # 解析类型
                py_type, sa_type, length, precision = get_python_type(col_type)
                
                # 判断是否为主键
                is_pk = col_key == "PRI"
                
                # 判断是否自增
                auto_increment = "auto_increment" in extra.lower() if extra else False
                
                # 处理默认值
                default_value = None
                if col_default:
                    if col_default.upper() == "CURRENT_TIMESTAMP":
                        default_value = None  # SQLModel 会处理
                    elif col_default.upper() == "NULL":
                        default_value = None
                    else:
                        try:
                            if py_type == "int":
                                default_value = int(col_default)
                            elif py_type == "float":
                                default_value = float(col_default)
                            elif py_type == "bool":
                                default_value = col_default.lower() in ("1", "true", "yes")
                            else:
                                # 字符串类型去掉引号
                                default_value = col_default.strip("'\"")
                        except:
                            default_value = col_default
                
                field = {
                    "name": to_snake_case(col_name),
                    "db_name": col_name,
                    "type": col_type,
                    "python_type": py_type,
                    "sa_type": sa_type,
                    "length": length,
                    "precision": precision,
                    "primary_key": is_pk,
                    "auto_increment": auto_increment,
                    "nullable": is_nullable == "YES",
                    "default": default_value,
                    "comment": col_comment or ""
                }
                fields.append(field)
            
            return TableConfig(
                table_name=table_name,
                class_name=to_pascal_case(table_name),
                comment=table_comment,
                fields=fields
            )
        finally:
            conn.close()
    
    def list_tables(self) -> List[str]:
        """列出数据库中的所有表"""
        conn = pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset='utf8mb4'
        )
        
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            return tables
        finally:
            conn.close()


class ModelGenerator:
    """模型文件生成器"""
    
    def __init__(self, config: TableConfig):
        self.config = config
    
    def generate_imports(self) -> str:
        """生成导入语句"""
        imports = set()
        imports.add("from typing import Optional")
        
        # 检查需要的类型
        has_datetime = False
        has_date = False
        has_time = False
        has_decimal = False
        
        for field in self.config.fields:
            py_type = field.get("python_type", "str")
            if py_type == "datetime":
                has_datetime = True
            elif py_type == "date":
                has_date = True
            elif py_type == "time":
                has_time = True
            elif py_type == "Decimal":
                has_decimal = True
        
        # 时间类型导入
        time_imports = []
        if has_datetime:
            time_imports.append("datetime")
        if has_date:
            time_imports.append("date")
        if has_time and not has_datetime:
            time_imports.append("time")
        if time_imports:
            imports.add(f"from datetime import {', '.join(sorted(set(time_imports)))}")
        
        # Decimal 导入
        if has_decimal:
            imports.add("from decimal import Decimal")
        
        imports.add("from sqlmodel import SQLModel, Field")
        imports.add("from sqlalchemy import Column")
        
        # 收集需要的 SQLAlchemy 类型
        sa_types = set()
        for field in self.config.fields:
            sa_type = field.get("sa_type", "String")
            sa_types.add(sa_type)
        
        # 生成 SQLAlchemy 导入
        if sa_types:
            imports.add(f"from sqlalchemy import {', '.join(sorted(sa_types))}")
        
        # 排序并格式化导入
        import_lines = sorted(imports)
        return "\n".join(import_lines) + "\n\n"
    
    def generate_field(self, field: Dict) -> str:
        """生成单个字段的代码"""
        field_name = field["name"]
        db_name = field["db_name"]
        sa_type = field.get("sa_type", "String")
        length = field.get("length")
        precision = field.get("precision")
        py_type = field.get("python_type", "str")
        is_pk = field.get("primary_key", False)
        auto_increment = field.get("auto_increment", False)
        default_value = field.get("default")
        comment = field.get("comment", "")
        nullable_db = field.get("nullable", False) # 从数据库 schema 获取的 nullable 属性
        
        lines = []
        
        # 添加注释
        if comment:
            lines.append(f"    # {comment}")
        
        # 确定 Python 类型注解
        # 如果数据库中是可空的，使用 Optional。否则使用基础类型。
        # SQLModel 会从 Optional[Type] 推断 Field(nullable=True)
        # 从 Type 推断 Field(nullable=False)。
        type_annotation = f"Optional[{py_type}]" if nullable_db else py_type

        # 构建 Field 参数
        field_args = []

        # 处理默认值
        if default_value is not None:
            if py_type == "int":
                field_args.append(f"default={default_value}")
            elif py_type == "float":
                field_args.append(f"default={default_value}")
            elif py_type == "bool":
                field_args.append(f"default={'True' if default_value else 'False'}")
            elif py_type == "Decimal":
                field_args.append(f"default=Decimal('{default_value}')")
            else:
                field_args.append(f'default="{default_value}"')
        elif nullable_db: # 如果可空且没有默认值，明确指定 default=None 以提高可读性
            field_args.append("default=None")

        # 构建 sa_column，主要用于类型和名称，以及非主键的非空约束
        sa_column_base = f'Column("{db_name}", {sa_type}'

        # 为 SQLAlchemy 类型添加长度/精度
        if sa_type == "String" and length:
            sa_column_base = f'Column("{db_name}", {sa_type}({length})'
        elif sa_type == "Numeric":
            if precision:
                sa_column_base = f'Column("{db_name}", {sa_type}({length}, {precision})'
            elif length:
                sa_column_base = f'Column("{db_name}", {sa_type}({length})'
            else:
                sa_column_base = f'Column("{db_name}", {sa_type}(20, 4)' # 如果未指定，为 Numeric 提供默认精度

        # 如果数据库中是非空且不是主键，则在 sa_column 中明确指定 nullable=False
        # 这对于 SQLAlchemy 的 DDL 生成非常重要。
        if not nullable_db and not is_pk:
            sa_column_base += ", nullable=False"

        # SQLModel 当提供 sa_column 时，primary_key 必须放在 sa_column 内部
        if is_pk:
            sa_column_base += ", primary_key=True"

        # SQLModel 的 Field 不接受 autoincrement，将其放入 sa_column 中
        if auto_increment:
            sa_column_base += ", autoincrement=True"

        sa_column_str = sa_column_base + ")"

        if field_args:
            field_def = f"{field_name}: {type_annotation} = Field({', '.join(field_args)}, sa_column={sa_column_str})"
        else:
            field_def = f"{field_name}: {type_annotation} = Field(sa_column={sa_column_str})"
        lines.append(f"    {field_def}")
        
        return "\n".join(lines)
    
    def generate(self) -> str:
        """生成完整的模型文件"""
        output = []
        
        # 导入语句
        output.append(self.generate_imports())
        
        # 类定义
        class_doc = f'"""{self.config.comment}"""' if self.config.comment else ""
        output.append(f"class {self.config.class_name}(SQLModel, table=True):")
        if class_doc:
            output.append(f"    {class_doc}")
        output.append(f'    __tablename__ = "{self.config.table_name}"')
        output.append("")
        
        # 字段
        for field in self.config.fields:
            output.append(self.generate_field(field))
        
        return "\n".join(output)


class ServiceGenerator:
    """服务文件生成器"""
    
    def __init__(self, config: TableConfig, model_import_path: str = "app.models"):
        self.config = config
        self.model_import_path = model_import_path
    
    def generate_imports(self) -> str:
        """生成导入语句"""
        model_name_lower = to_snake_case(self.config.class_name)
        return f"""from typing import Optional, List, Dict, Any
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from {self.model_import_path}.{model_name_lower} import {self.config.class_name}
"""
    
    def _get_pk_field(self) -> tuple:
        """获取主键字段名和类型"""
        for field in self.config.fields:
            if field.get("primary_key"):
                return field["name"], field.get("python_type", "int")
        # 如果没有找到主键，则默认使用 'id'，并发出警告
        print(f"⚠️ 警告: 表 '{self.config.table_name}' 未找到明确的主键。服务方法将默认使用 'id' 作为主键。请检查数据库设计或手动调整生成代码。")
        return "id", "int"
    
    def generate_fetch_method(self) -> str:
        """生成 fetch 方法"""
        class_name = self.config.class_name
        pk_field, pk_type = self._get_pk_field()
        var_name = to_snake_case(class_name)
        
        return f'''    async def fetch(self, db: AsyncSession, {pk_field}: {pk_type}) -> Optional[{class_name}]:
        """
        根据 ID 查询记录
        :param db: 异步数据库会话
        :param {pk_field}: 记录ID
        :return: {class_name} 对象或 None
        """
        statement = select({class_name}).where({class_name}.{pk_field} == {pk_field})
        result = await db.exec(statement)
        return result.first()'''
    
    def generate_list_method(self) -> str:
        """生成 list 方法"""
        class_name = self.config.class_name
        return f'''    async def list(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> List[{class_name}]:
        """
        分页查询记录列表
        :param db: 异步数据库会话
        :param skip: 跳过记录数
        :param limit: 返回记录数
        :return: {class_name} 列表
        """
        statement = select({class_name}).offset(skip).limit(limit)
        result = await db.exec(statement)
        return result.all()'''
    
    def generate_query_list_method(self) -> str:
        """生成 query_list 方法"""
        class_name = self.config.class_name
        return f'''    async def query_list(
        self, 
        db: AsyncSession, 
        condition: Dict[str, Any], 
        order_by: Optional[str] = None, 
        sort_by: Optional[str] = "asc"
    ) -> List[{class_name}]:
        """
        根据条件查询记录列表
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :param order_by: 排序字段
        :param sort_by: 排序方式 ('asc' or 'desc')
        :return: {class_name} 列表
        """
        statement = select({class_name})
        for key, value in condition.items():
            if hasattr({class_name}, key):
                statement = statement.where(getattr({class_name}, key) == value)
        
        if order_by and hasattr({class_name}, order_by):
            order_col = getattr({class_name}, order_by)
            if sort_by and sort_by.lower() == 'desc':
                statement = statement.order_by(order_col.desc())
            else:
                statement = statement.order_by(order_col.asc())
        
        result = await db.exec(statement)
        return result.all()'''

    def generate_query_one_method(self) -> str:
        """生成 query_one 方法"""
        class_name = self.config.class_name
        return f'''    async def query_one(self, db: AsyncSession, condition: Dict[str, Any]) -> Optional[{class_name}]:
        """
        根据条件查询单条记录
        :param db: 异步数据库会话
        :param condition: 查询条件字典
        :return: {class_name} 对象或 None
        """
        statement = select({class_name})
        for key, value in condition.items():
            if hasattr({class_name}, key):
                statement = statement.where(getattr({class_name}, key) == value)
        
        result = await db.exec(statement)
        return result.first()'''
    
    def generate_create_method(self) -> str:
        """生成 create 方法"""
        class_name = self.config.class_name
        var_name = to_snake_case(class_name)
        return f'''    async def create(self, db: AsyncSession, {var_name}: {class_name}) -> {class_name}:
        """
        创建新记录
        :param db: 异步数据库会话
        :param {var_name}: 要创建的记录对象
        :return: 创建后的记录对象
        """
        db.add({var_name})
        await db.flush()
        return {var_name}'''
    
    def generate_update_method(self) -> str:
        """生成 update 方法"""
        class_name = self.config.class_name
        var_name = to_snake_case(class_name)
        return f'''    async def update(self, db: AsyncSession, {var_name}: {class_name}) -> {class_name}:
        """
        更新记录
        :param db: 异步数据库会话
        :param {var_name}: 要更新的记录对象
        :return: 更新后的记录对象
        """
        db.add({var_name})
        await db.flush()
        return {var_name}'''
    
    def generate_delete_method(self) -> str:
        """生成 delete 方法"""
        class_name = self.config.class_name
        var_name = to_snake_case(class_name)
        pk_field, pk_type = self._get_pk_field()
        
        return f'''    async def delete(self, db: AsyncSession, {pk_field}: {pk_type}) -> bool:
        """
        删除记录
        :param db: 异步数据库会话
        :param {pk_field}: 记录ID
        :return: 是否删除成功
        """
        {var_name} = await self.fetch(db, {pk_field})
        if {var_name}:
            await db.delete({var_name})
            await db.flush()
            return True
        return False'''
    
    def generate(self) -> str:
        """生成完整的服务文件"""
        output = []
        
        # 导入语句
        output.append(self.generate_imports())
        output.append("")
        
        # 类定义
        output.append(f"class {self.config.class_name}Service:")
        output.append('    """')
        output.append(f'    处理 {self.config.class_name} 相关的业务逻辑')
        if self.config.comment:
            output.append(f'    表: {self.config.table_name} - {self.config.comment}')
        output.append('    """')
        output.append("")
        
        # 生成各个方法
        output.append(self.generate_fetch_method())
        output.append("")
        output.append(self.generate_list_method())
        output.append("")
        output.append(self.generate_query_list_method())
        output.append("")
        output.append(self.generate_query_one_method())
        output.append("")
        output.append(self.generate_create_method())
        output.append("")
        output.append(self.generate_update_method())
        output.append("")
        output.append(self.generate_delete_method())
        
        # 单例实例
        var_name = to_snake_case(self.config.class_name) + "_service"
        output.append("")
        output.append("# 创建单例实例 (Singleton)")
        output.append(f'{var_name} = {self.config.class_name}Service()')
        
        return "\n".join(output)


def generate_code(config: TableConfig, output_dir: str, model_import_path: str = "app.models"):
    """
    生成代码文件
    
    :param config: 表配置
    :param output_dir: 输出目录
    :param model_import_path: 模型导入路径
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # 生成模型文件
    model_gen = ModelGenerator(config)
    model_code = model_gen.generate()
    model_file = output_path / f"{to_snake_case(config.class_name)}.py"
    model_file.write_text(model_code, encoding="utf-8")
    print(f"✅ 模型文件已生成: {model_file}")
    
    # 生成服务文件
    service_gen = ServiceGenerator(config, model_import_path)
    service_code = service_gen.generate()
    service_file = output_path / f"{to_snake_case(config.class_name)}_service.py"
    service_file.write_text(service_code, encoding="utf-8")
    print(f"✅ 服务文件已生成: {service_file}")


def main():
    parser = argparse.ArgumentParser(description="根据数据库表结构生成 SQLModel 模型和服务代码")
    
    # 数据库连接参数
    parser.add_argument("--db-host", default=os.getenv("DB_HOST", "127.0.0.1"), help="数据库主机")
    parser.add_argument("--db-port", type=int, default=int(os.getenv("DB_PORT", 3306)), help="数据库端口")
    parser.add_argument("--db-user", default=os.getenv("DB_USER", "root"), help="数据库用户名")
    parser.add_argument("--db-password", default=os.getenv("DB_PASSWORD", ""), help="数据库密码")
    parser.add_argument("--db-name", default=os.getenv("DB_NAME", ""), help="数据库名称")
    
    # 表选择
    parser.add_argument("--table", "-t", help="要生成代码的表名")
    parser.add_argument("--tables", nargs="+", help="多个表名（空格分隔）")
    parser.add_argument("--list-tables", action="store_true", help="列出数据库中的所有表")
    
    
    # 输出设置
    parser.add_argument("--output", "-o", default="./output", help="输出目录")
    parser.add_argument("--model-path", "-m", default="app.models", help="模型导入路径")
    
    args = parser.parse_args()
    
    # 列出所有表
    if args.list_tables:
        if not args.db_name:
            print("❌ 请指定数据库名称: --db-name <database>")
            return
        reader = DatabaseReader(args.db_host, args.db_port, args.db_user, args.db_password, args.db_name)
        tables = reader.list_tables()
        print(f"\n📋 数据库 '{args.db_name}' 中的表:")
        for t in tables:
            print(f"  - {t}")
        return
    
    # 从数据库读取
    if args.table or args.tables:
        if not args.db_name:
            print("❌ 请指定数据库名称: --db-name <database>")
            return
        
        reader = DatabaseReader(args.db_host, args.db_port, args.db_user, args.db_password, args.db_name)
        
        # 获取要处理的表列表
        table_list = []
        if args.tables:
            table_list = args.tables
        elif args.table:
            table_list = [args.table]
        
        for table_name in table_list:
            print(f"\n📖 读取表结构: {table_name}")
            config = reader.get_table_structure(table_name)
            print(f"   字段数量: {len(config.fields)}")
            generate_code(config, args.output, args.model_path)
        
        print(f"\n🎉 完成! 文件已输出到: {args.output}")
        return
    
    # 无参数时显示帮助
    parser.print_help()
    print("\n\n📖 示例用法:")
    print("  # 从数据库读取单个表")
    print("  python code_generator.py --db-name stock --table index_daily --output ./models")
    print("\n  # 从数据库读取多个表")
    print("  python code_generator.py --db-name stock --tables index_daily index_weekly --output ./models")
    print("\n  # 列出数据库中的所有表")
    print("  python code_generator.py --db-name stock --list-tables")
    print("\n  # 使用环境变量中的数据库配置")
    print("  python code_generator.py --db-name stock --table index_daily")


if __name__ == "__main__":
    main()
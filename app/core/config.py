from typing import Optional
from urllib.parse import quote_plus

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # --- 基础配置 ---
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "stock-analyse"
    
    # --- 1. 数据库配置 (极简模式默认禁用，开启时必填) ---
    ENABLE_DB: bool = False
    ENABLE_REDIS: bool = False
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = None
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None

    # --- 2. Nacos 配置 (支持 .env 覆盖，提供默认值方便本地开发) ---

    ENABLE_NACOS: bool = True
    
    NACOS_SERVER_ADDR: str = "127.0.0.1:8848"
    NACOS_NAMESPACE: Optional[str] = ""       # public 命名空间通常为空字符串
    NACOS_USERNAME: str = "nacos"
    NACOS_PASSWORD: str = "nacos"
    NACOS_CLIENT_IP: Optional[str] = None     # 优先用于服务注册的本机 IP
    
    # --- 3. 本服务注册信息 ---
    # 这个名字要和 Gateway 配置的 lb://service-name 一致
    SERVICE_NAME: str = "stock-analyse"      
    SERVICE_PORT: int = 8008
    SERVICE_GROUP: str = "DEFAULT_GROUP"

    ALIYUN_OSS_ENDPOINT: str = "oss-cn-shenzhen.aliyuncs.com"
    ALIYUN_OSS_BUCKET_NAME: str = "my-company"
    ALIYUN_OSS_ACCESS_KEY_ID: str = ""      # OSS 访问密钥 ID
    ALIYUN_OSS_ACCESS_KEY_SECRET: str = ""  # OSS 访问密钥 Secret

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""  # 生产环境必须配置密码，移除Optional强制验证
    REDIS_DB: int = 0

    PDF_CONVERT_MAX_WORKERS: Optional[int] = 2

    LOG_LEVEL: str = "INFO"

    REGION: str = "hongkong"

    RUN_MODE: str = "prod"

    PROMPT_DIR: str = "./prompts"

    GEMINI_API_WHITELIST: Optional[str] = ""

    GATEWAY_AUTH_TOKEN: Optional[str] = None

    PRODUCT_IP: Optional[str] = None

    LIXINGER_TOKEN: Optional[str] = None

    # --- 微信 dispatch 鉴权 (Node bot 与 Python 共享) ---
    WECHAT_DISPATCH_TOKEN: Optional[str] = None

    # --- 4. 组装 DATABASE_URL ---
    @property
    def DATABASE_URL(self) -> str:
        """
        自动组装 SQLAlchemy 连接字符串
        格式: mysql+pymysql://user:password@host:port/dbname
        仅在 ENABLE_DB=True 时调用方有意义
        """
        user = quote_plus(self.DB_USER or "")
        password = quote_plus(self.DB_PASSWORD or "")

        return (
            f"mysql+pymysql://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        异步连接字符串 (用于 aiomysql)
        """
        user = quote_plus(self.DB_USER or "")
        password = quote_plus(self.DB_PASSWORD or "")
        return (
            f"mysql+aiomysql://{user}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    class Config:
        case_sensitive = True
        # 指定读取 .env 文件
        env_file = ".env"
        # 忽略 .env 中多余的字段 (防止 .env 有注释或其他无关变量导致报错)
        extra = "ignore"

settings = Settings()
import oss2
import requests
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

# 1. 定义需要重试的异常集合
# 这些是所有网络 IO 操作可能遇到的通用错误
NETWORK_EXCEPTIONS = (
    requests.exceptions.RequestException,  # 常规 HTTP 请求错误
    oss2.exceptions.OssError,              # 阿里云 OSS 错误
    ConnectionError,                       # 底层连接错误
    TimeoutError,                          # 底层超时
    # 如果有其他库的特定异常（比如 pymysql.Error），也可以加在这里
)

# 2. 定义通用的重试配置字典
# 这样你在 Service 里只需要 @retry(**COMMON_RETRY_CONFIG) 即可
COMMON_RETRY_CONFIG = {
    "stop": stop_after_attempt(3), 
    "wait": wait_exponential(multiplier=1, min=1, max=10),
    "retry": retry_if_exception_type(NETWORK_EXCEPTIONS),
    "reraise": True  #以此抛出最终的异常，而不是 RetryError
}
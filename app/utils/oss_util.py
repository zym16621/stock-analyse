import concurrent
import os
import time
import urllib.parse
from io import BytesIO
from typing import List, Union
from urllib.parse import urlparse

import oss2
from loguru import logger
from requests.adapters import HTTPAdapter  # 必须导入
from tenacity import retry

from app.core.config import settings
from app.core.retry import COMMON_RETRY_CONFIG


class OssUtil:

    _bucket_cache = {}

    @staticmethod
    def _validate_config():
        """验证OSS配置完整性"""
        key_id = settings.ALIYUN_OSS_ACCESS_KEY_ID
        secret = settings.ALIYUN_OSS_ACCESS_KEY_SECRET

        if settings.RUN_MODE == "prod":
            if not key_id:
                raise ValueError("❌ 生产环境必须配置 ALIYUN_OSS_ACCESS_KEY_ID，请检查 .env 文件")
            if not secret:
                raise ValueError("❌ 生产环境必须配置 ALIYUN_OSS_ACCESS_KEY_SECRET，请检查 .env 文件")
        elif not key_id or not secret:
            logger.warning("⚠️ OSS密钥未配置，OSS相关功能将无法使用")
            raise ValueError("OSS配置缺失: AccessKey 或 Secret 为空，请检查 .env 文件")

    @staticmethod
    def _get_bucket(endpoint: str, bucket_name: str) -> oss2.Bucket:
        """
        获取 Bucket 对象 (带缓存复用 + 强制 HTTPS + 50并发连接池)
        """
        # 0. 验证配置完整性
        OssUtil._validate_config()

        # 1. 构造缓存 Key
        cache_key = f"{endpoint}_{bucket_name}"
        
        # 2. 缓存复用
        if cache_key in OssUtil._bucket_cache:
            return OssUtil._bucket_cache[cache_key]

        # 3. 强制 HTTPS
        if not endpoint:
            raise ValueError("❌ OSS配置缺失: Endpoint 为空")

        if endpoint.startswith("http://"):
            endpoint = endpoint.replace("http://", "https://")
        elif not endpoint.startswith("https://"):
            endpoint = f"https://{endpoint}"

        # =========================================================
        # 4. 配置高并发连接池（移除 max_retries，依赖 tenacity）
        # =========================================================
        adapter = HTTPAdapter(pool_connections=50, pool_maxsize=50)
        session = oss2.Session(adapter=adapter)
        session.session.trust_env = False

        # 配置已在 _validate_config() 中验证
        key_id = settings.ALIYUN_OSS_ACCESS_KEY_ID
        secret = settings.ALIYUN_OSS_ACCESS_KEY_SECRET

        auth = oss2.Auth(key_id, secret)

        # 5. 创建 Bucket (必须传入 session)
        bucket = oss2.Bucket(auth, endpoint, bucket_name, connect_timeout=30, enable_crc=True, session=session)
        
        # 存入缓存
        OssUtil._bucket_cache[cache_key] = bucket
        return bucket

    @staticmethod
    def get_default_oss_key(key: str) -> str:
        """从完整 URL 中提取 OSS Key"""
        if not key:
            return ""
        
        key = urllib.parse.unquote(key)
        
        for domain_suffix in [".com", ".cn"]:
            idx = key.rfind(domain_suffix)
            if idx > 0:
                key = key[idx + len(domain_suffix):]
                break
        
        q_idx = key.rfind("?")
        if q_idx > 0:
            key = key[:q_idx]
            
        key = key.lstrip("/")
        return key

    @staticmethod
    def get_signed_url(endpoint: str, bucket_name: str, key: str, style: str = None) -> str:
        """生成签名 URL"""
        if not key or key.startswith("https://") or key.startswith("http://"):
            return key

        # 服务器上配置的 endpoint 通常是以 -internal.aliyuncs.com 结尾
        #    这里需要把这个后缀替换成 .aliyuncs.com
        endpoint = endpoint.replace("-internal.aliyuncs.com", ".aliyuncs.com")
        try:
            bucket = OssUtil._get_bucket(endpoint, bucket_name)
            expires = 30 * 24 * 3600 # 30天
            params = {'x-oss-process': style} if style else {}
            
            url = bucket.sign_url('GET', key, expires, params=params, slash_safe=True)
            url = url.replace("http://", "https://")              
            return url
        except Exception as e:
            logger.error(f"Error generating signed URL: {e}")
            return key

    @staticmethod
    def regenerate_presigned_url(endpoint: str, bucket_name: str, url: str) -> str:
        """重新生成签名 URL"""
        if not url:
            return url
            
        try:
            parsed = urlparse(url)
            path = parsed.path
            
            if path.startswith("/"):
                oss_key = path[1:] # 去掉开头的 /
                return OssUtil.get_signed_url(endpoint, bucket_name, oss_key)
                
        except Exception as e:
            logger.error(f"Regenerate URL failed: {e}")
            pass 
            
        return url

    @staticmethod
    def put_file(endpoint: str, bucket_name: str, data: Union[str, bytes, BytesIO], key: str):
        """上传文件"""
        bucket = OssUtil._get_bucket(endpoint, bucket_name)
        try:
            if isinstance(data, str) and os.path.exists(data):
                oss2.resumable_upload(bucket, key, data)
            else:
                bucket.put_object(key, data)
        except Exception as e:
            raise Exception(f"上传OSS失败: {str(e)}") from e

    @staticmethod
    def put_file_with_public(endpoint: str, bucket_name: str, data, key: str):
        """上传并设为公共读"""
        bucket = OssUtil._get_bucket(endpoint, bucket_name)
        try:
            headers = {'x-oss-object-acl': oss2.OBJECT_ACL_PUBLIC_READ}
            bucket.put_object(key, data, headers=headers)
        except Exception as e:
            raise Exception(f"上传OSS失败: {str(e)}") from e

    @staticmethod
    def copy_file(endpoint: str, source_bucket: str, source_key: str, dest_bucket: str, dest_key: str):
        """复制文件"""
        bucket = OssUtil._get_bucket(endpoint, dest_bucket)
        try:
            bucket.copy_object(source_bucket, source_key, dest_key)
        except Exception as e:
            raise Exception(f"复制OSS失败: {str(e)}") from e

    @staticmethod
    def is_file_exist(endpoint: str, bucket_name: str, key: str) -> bool:
        """判断文件是否存在"""
        try:
            bucket = OssUtil._get_bucket(endpoint, bucket_name)
            return bucket.object_exists(key)
        except Exception:
            return False

    @staticmethod
    def download_file(endpoint: str, bucket_name: str, key: str, local_path: str):
        """
        [新增] 下载文件到本地 (用于 Stage 2 跨服务器恢复原始 PDF)
        """
        bucket = OssUtil._get_bucket(endpoint, bucket_name)
        try:
            # 确保父目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            # 下载
            bucket.get_object_to_file(key, local_path)
        except Exception as e:
            logger.error(f"OSS下载失败 [{key}]: {e}")
            raise Exception(f"下载OSS失败: {str(e)}") from e

    @staticmethod
    def delete_file(endpoint: str, bucket_name: str, key: str) -> bool:
        """删除文件"""
        try:
            bucket = OssUtil._get_bucket(endpoint, bucket_name)
            bucket.delete_object(key)
            return True
        except Exception as e:
            logger.error(f"删除文件失败: {e}")
            return False

    @staticmethod
    def get_video_snapshot_url(endpoint: str, bucket_name: str, key: str) -> str:
        """视频截图签名URL"""
        style = "video/snapshot,t_1000,f_jpg,w_800,h_600"
        return OssUtil.get_signed_url(endpoint, bucket_name, key, style=style)

    @staticmethod
    def concurrent_upload_images(local_img_paths: List[str],dir:str, task_id: str) -> List[dict]:
        """
        [原子方法] 并发上传图片到 OSS
        Args:
            local_img_paths: 本地图片路径列表
            task_id: 任务ID (用于日志)
        Returns:
            List[dict]: 按原始顺序排列的对象列表，包含 page_index, url, oss_key
        """
        t_start = time.time()
        logger.info(f"[{task_id}]正在并发上传图片到 OSS...")
        
        page_result_map = {} 
        
        # 使用 Context Manager 自动管理线程池资源
        with concurrent.futures.ThreadPoolExecutor(max_workers=settings.PDF_CONVERT_MAX_WORKERS) as executor:
            # 建立 future 到 index 的映射
            future_to_idx = {
                executor.submit(OssUtil.upload_single_image, path,dir,task_id): i 
                for i, path in enumerate(local_img_paths)
            }
            
            # 处理结果
            for future in concurrent.futures.as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    url, oss_key = future.result()
                    
                    # 组装完整的对象
                    page_result_map[idx] = {
                        "page_index": idx,
                        "url": url,
                        "oss_key": oss_key
                    }
                except Exception as e:
                    logger.error(f"第 {idx} 页上传失败: {e}")
                    raise e

        # 校验完整性
        if len(page_result_map) != len(local_img_paths):
             raise Exception("部分图片上传失败，无法继续拆分作业")
        
        # 关键：按原始索引顺序还原列表
        sorted_results = [page_result_map[i] for i in range(len(local_img_paths))]

        logger.info(f"[{task_id}] 图片上传完成 | 上传数量: {len(sorted_results)} | 耗时: {time.time() - t_start:.2f}s")
        return sorted_results

    @staticmethod
    @retry(**COMMON_RETRY_CONFIG)
    def upload_single_image(img_path: str, dir:str,task_id: str):
        """单个图片上传逻辑 (线程内执行)"""
        file_name = os.path.basename(img_path)
        oss_key = f"{dir}/{task_id}/{file_name}"

        OssUtil.put_file(settings.ALIYUN_OSS_ENDPOINT, settings.ALIYUN_OSS_BUCKET_NAME, img_path, oss_key)
        url = OssUtil.get_signed_url(settings.ALIYUN_OSS_ENDPOINT, settings.ALIYUN_OSS_BUCKET_NAME,oss_key)
        return url, oss_key
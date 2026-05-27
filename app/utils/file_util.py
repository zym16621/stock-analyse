import os
from datetime import datetime


class FileUtil:
    @staticmethod
    def get_ocr_dir() -> str:
        """生成上传目录 ocr/2023/5/20"""
        now = datetime.now()
        return f"ocr/{now.year}/{now.month}/{now.day}"
    
    @staticmethod
    def get_split_dir() -> str:
        """生成上传目录 ocr/2023/5/20"""
        now = datetime.now()
        return f"split/{now.year}/{now.month}/{now.day}"
    
    @staticmethod
    def get_group_report_dir() -> str:
        """生成上传目录 group_report/2023/5/20"""
        now = datetime.now()
        return f"group_report/{now.year}/{now.month}/{now.day}"

    @staticmethod
    def get_temp_dir() -> str:
        """
        获取项目目录下的临时文件夹。
        路径通常为: {项目根目录}/temp_workspace/{task_id}
        """
        # 1. 获取当前项目的工作目录 (运行 python main.py 或 uvicorn 的那个目录)
        project_root = os.getcwd()
        
        # 2. 指定一个子文件夹名字，建议起个明显的名字，防止和代码文件夹混淆
        target_dir = os.path.join(project_root, "temp_workspace")
        
        # 3. 确保目录存在
        os.makedirs(target_dir, exist_ok=True)
        
        return target_dir
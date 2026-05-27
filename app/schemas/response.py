from typing import Any, Optional

from pydantic import BaseModel


# ==========================================
# 1. 新增：通用响应结构 (解决 ImportError)
# ==========================================
class SingleResponse(BaseModel):
    data: Optional[Any] = None
    errCode: int = 200
    errMsg: Optional[str] = None

    def is_success(self) -> bool:
        # 兼容 200 或 0 作为成功码
        return self.errCode == 200 or self.errCode == 0
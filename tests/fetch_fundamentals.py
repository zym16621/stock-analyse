import requests
from datetime import datetime, timedelta

def fetch_fundamentals(index_codes, start_date, end_date):
    """从理杏仁获取基本面数据（支持日期范围）"""
    url = "https://open.lixinger.com/api/hk/index/fundamental"
    payload = {
        "token": LIXINGER_TOKEN,
        "startDate": start_date,
        "endDate": end_date,
        "stockCodes": index_codes,
        "metricsList": [
            "pe_ttm.mcw", "pe_ttm.y10.mcw.cvpos",
            "pb.mcw", "pb.y10.mcw.cvpos",
            "ps_ttm.mcw", "ps_ttm.y10.mcw.cvpos",
            "dyr.mcw",
            "cp", "cpc", "ta", "mc",
            "ah_shm", "mm_nba", "fet_snif_ma"
        ]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        data = response.json()
        if data.get("code") == 1 and data.get("data"):
            return data["data"]
        else:
            print(f"   ⚠️ API 返回: code={data.get('code')}, message={data.get('message', 'N/A')}")
    except Exception as e:
        print(f"   ❌ 请求失败: {e}")
    return []

start_date = "2026-05-17"
end_date = "2026-05-27"

indices = {'HSTECH': '恒生科技指数'}
index_codes = list(indices.keys())
        
print(f"\n📈 [1/2] 获取指数基本面数据: {', '.join(index_codes)}")
results = fetch_fundamentals(index_codes, start_date, end_date)

print(f"\n📈 [2/2] 指数基本面数据获取完成，共计 {len(results)} 条数据。")
import requests
import json
from datetime import datetime, timedelta
import os

def fetch_sp500_fundamental_history(token, days=10):
    """
    获取美国标普500指数(.INX)最近一段时间的基本面估值数据
    """
    url = "https://open.lixinger.com/api/us/index/fundamental"
    
    # 自动计算 startDate 和 endDate
    end_date_obj = datetime.now()
    start_date_obj = end_date_obj - timedelta(days=days)
    
    end_date_str = end_date_obj.strftime("%Y-%m-%d")
    start_date_str = start_date_obj.strftime("%Y-%m-%d")
    
    print(f"正在获取标普500 (.INX) 从 {start_date_str} 到 {end_date_str} 的估值数据...\n")
    
    # 构造请求参数 (注意去掉了 'date' 参数，换成了 startDate 和 endDate)
    payload = {
        "token": token,
        "stockCodes": [".INX"], 
        "startDate": start_date_str,
        "endDate": end_date_str,
        "metricsList": [
            "cp",                       # 收盘点位
            "pe_ttm.mcw",               # 市盈率(TTM) - 市值加权当前值
            "pe_ttm.y10.mcw.cvpos",     # 核心红线：PE 10年分位点
        ]
    }

    headers = {
        'Content-Type': 'application/json'
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status() 
        data = response.json()
        
        if data.get('code') == 1 and data.get('data'):
            results = data['data']
            
            print(f"{'日期':<12} | {'收盘点位':<10} | {'PE-TTM':<8} | {'PE 10年分位点'}")
            print("-" * 55)
            
            # API返回的数据通常是按日期倒序或正序的，我们循环打印出来
            for item in results:
                date_str = item.get('date')[:10]
                cp = item.get('cp', 0)
                pe = item.get('pe_ttm.mcw', 0)
                pe_pos = item.get('pe_ttm.y10.mcw.cvpos', 0) * 100 # 转成百分比
                
                print(f"{date_str:<12} | {cp:<10.2f} | {pe:<8.2f} | {pe_pos:.2f}%")
            
            # 提取最新一天的分位点进行智能判定
            latest_data = results[0] # 假设第一个是最新的，根据实际API返回顺序可能需调整
            latest_pe_pos = latest_data.get('pe_ttm.y10.mcw.cvpos', 0)
            
            print("\n>>> 最新系统判决：")
            if latest_pe_pos > 0.90:
                print("🚨 警告：标普500当前估值已突破90%危险区，建议本月资金转入货币基金(3096.HK)避险！")
            else:
                print("✅ 估值未触碰90%红线，请继续执行纪律：本月发薪后买入 3195.HK。")
                
        else:
            print("未能获取到有效数据，返回信息:", data)
            
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")

if __name__ == "__main__":
    LIXINGER_TOKEN = os.getenv('LIXINGER_TOKEN', '')
    fetch_sp500_fundamental_history(LIXINGER_TOKEN, days=10)
import requests
from datetime import datetime

def fetch_fear_and_greed_history(days=5):
    """
    抓取 CNN 恐惧与贪婪指数的近期历史趋势
    :param days: 需要获取的最近天数，默认 5 天
    """
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://edition.cnn.com/markets/fear-and-greed"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # 提取包含历史数据的列表
        historical_data = data.get('fear_and_greed_historical', {}).get('data', [])
        
        if not historical_data:
            print("未能解析到历史数据。")
            return
        
        # 截取列表的最后 N 个元素（即最近 N 天）
        recent_data = historical_data[-days:]
        
        print(f"=== CNN 恐惧与贪婪指数 (近 {days} 天趋势) ===")
        print(f"{'日期':<12} | {'得分':<6} | {'情绪状态'}")
        print("-" * 35)
        
        # 状态翻译映射字典
        rating_cn_map = {
            'extreme greed': '极度贪婪',
            'greed': '贪婪',
            'neutral': '中性',
            'fear': '恐惧',
            'extreme fear': '极度恐惧'
        }
        
        for item in recent_data:
            # CNN返回的时间戳(x)是毫秒级，需要除以1000转成秒
            timestamp = item.get('x', 0) / 1000.0
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
            
            score = item.get('y', 0)
            rating = item.get('rating', 'unknown')
            rating_cn = rating_cn_map.get(rating.lower(), rating)
            
            print(f"{date_str:<12} | {score:<6.1f} | {rating_cn}")
            
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {e}")
    except Exception as e:
        print(f"数据解析出错: {e}")

if __name__ == "__main__":
    # 这里可以自由修改你想看的最近天数，比如 7 天、10 天
    fetch_fear_and_greed_history(days=7)
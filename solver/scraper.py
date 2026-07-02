import os
import time
import random
from typing import Dict, List
from datetime import datetime

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

class CSPlayerScraper:
    def __init__(self):
        self.base_url = "https://api.blast.tv"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Origin": "https://blast.tv",
            "Pragma": "no-cache",
            "Priority": "u=1, i",
            "Referer": "https://blast.tv/",
            "Sec-Ch-Ua": '"Chromium";v="134", "Not:A-Brand";v="24", "Google Chrome";v="134"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site"
        }
        
        # 设置重试机制
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,  # 最大重试次数
            backoff_factor=1,  # 重试间隔
            status_forcelist=[429, 500, 502, 503, 504]  # 需要重试的HTTP状态码
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
    def get_all_players(self, difficulty: str = "pro") -> List[Dict]:
        """获取所有可选择的选手列表"""
        url = f"{self.base_url}/v1/counterstrikle/multiplayer/players"
        params = {
            "difficulty": difficulty
        }
        # 移除分页参数，直接获取所有数据
        
        try:
            response = self.session.get(url, params=params, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            if not data or len(data) == 0:
                print("未获取到任何数据")
                return []
            
            print(f"获取到 {len(data)} 名选手")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"获取选手列表失败: {e}")
            return []

    def get_player_details(self, player_id: str) -> Dict:
        """获取选手详细信息"""
        url = f"{self.base_url}/v1/counterstrikle/guesses"
        payload = {
            "playerId": player_id,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
        
        try:
            response = self.session.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"获取选手详情失败 (ID: {player_id}): {e}")
            return None

    def scrape_and_save(self):
        """爬取所有选手信息并保存为Excel"""
        print("开始获取选手列表...")
        players = self.get_all_players()
        
        if not players:
            print("未获取到任何选手信息！")
            return
            
        # 根据ID去重
        unique_players = {player['id']: player for player in players}
        players = list(unique_players.values())
        print(f"去重后共获取到 {len(players)} 名选手")
        
        # 用于存储所有选手详细信息
        player_details = []
        
        # 遍历每个选手
        for i, player in enumerate(players, 1):
            print(f"正在获取第 {i}/{len(players)} 名选手信息: {player.get('nickname', 'Unknown')}")
            
            details = self.get_player_details(player['id'])
            if details:
                try:
                    # 提取需要的信息，处理team字段
                    team_data = details.get('team', {}).get('data', {})
                    team_name = team_data.get('name') if team_data else None
                    
                    player_info = {
                        'id': details.get('id'),
                        'nickname': details.get('nickname'),
                        'firstName': details.get('firstName'),
                        'lastName': details.get('lastName'),
                        'isRetired': details.get('isRetired'),
                        'nationality': details.get('nationality', {}).get('value'),
                        'team': team_name,  # 只保存队伍名称
                        'age': details.get('age', {}).get('value'),
                        'majorAppearances': details.get('majorAppearances', {}).get('value'),
                        'role': details.get('role', {}).get('value')
                    }
                    player_details.append(player_info)
                except Exception as e:
                    print(f"处理选手信息时出错 (ID: {player['id']}): {e}")
            
            # 添加随机延时，避免请求过快
            time.sleep(random.uniform(1, 3))
        
        if not player_details:
            print("未获取到任何选手详细信息！")
            return
            
        # 转换为DataFrame并保存到 solver/data/players_pro.xlsx（求解器默认读取路径）
        df = pd.DataFrame(player_details)
        out_dir = os.path.join(os.path.dirname(__file__), "data")
        os.makedirs(out_dir, exist_ok=True)
        excel_path = os.path.join(out_dir, "players_pro.xlsx")
        df.to_excel(excel_path, index=False)
        print(f"数据已保存到: {excel_path}")
        print(f"共保存 {len(player_details)} 名选手的详细信息")

if __name__ == "__main__":
    scraper = CSPlayerScraper()
    scraper.scrape_and_save()
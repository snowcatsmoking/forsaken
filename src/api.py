"""
CS:GO选手猜测助手 - API服务
提供RESTful API接口，处理前端请求并返回猜测结果
作者: [SnowCat]
版本: 1.0.0
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import json
import os

# 初始化Flask应用
app = Flask(__name__)
CORS(app)  # 启用跨域支持
class CSPlayerAnalyzer:
    """
    CS:GO选手分析器
    负责处理选手数据分析和猜测逻辑
    """
    def __init__(self, excel_path: str):
        """
        初始化分析器
        
        Args:
            excel_path: 选手数据Excel文件路径
        """
        # 确保文件存在
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"找不到数据文件: {excel_path}")
            
        # 读取Excel数据
        self.df = pd.read_excel(excel_path)
        self.possible_players = self.df.copy()
        self.guess_history = []  # 只存储nickname字符串
        self.attributes = ['nationality', 'team', 'age', 'majorAppearances', 'role']
        self.total_players = len(self.df)  # 添加总选手数量属性
        
    def update_possibilities(self, feedback: Dict) -> pd.DataFrame:
        """
        根据反馈更新可能的选手列表
        
        Args:
            feedback: 包含各个属性反馈的字典
            
        Returns:
            更新后的可能选手DataFrame
        """
        # 创建全True掩码
        mask = pd.Series(True, index=self.possible_players.index)
        
        # 处理每个属性的反馈
        for key, value in feedback.items():
            if isinstance(value, dict) and 'result' in value:
                if key == 'team':
                    # 特殊处理team属性（可能为free agent）
                    if value['result'] == 'CORRECT':
                        if value['data'] is None:
                            mask &= self.possible_players['team'].isna()
                        else:
                            mask &= (self.possible_players['team'] == value['data']['name'])
                    elif value['result'] == 'INCORRECT':
                        if value['data'] is None:
                            mask &= ~self.possible_players['team'].isna()
                        else:
                            mask &= (self.possible_players['team'] != value['data']['name'])
                else:
                    # 处理其他属性
                    if value['result'] == 'CORRECT':
                        mask &= (self.possible_players[key] == value['value'])
                    elif value['result'] == 'INCORRECT':
                        mask &= (self.possible_players[key] != value['value'])
                    elif value['result'] == 'HIGH_NOT_CLOSE':
                        mask &= (self.possible_players[key] < value['value'])
                    elif value['result'] == 'LOW_NOT_CLOSE':
                        mask &= (self.possible_players[key] > value['value'])
                    elif value['result'] == 'HIGH_CLOSE':
                        # 高但是接近，使用更精确的范围
                        if key == 'age':
                            # 年龄接近通常在1-3年范围内
                            mask &= (self.possible_players[key] < value['value']) & (self.possible_players[key] > value['value'] - 4)
                        elif key == 'majorAppearances':
                            # Major出场次数接近通常在1-2次范围内
                            mask &= (self.possible_players[key] < value['value']) & (self.possible_players[key] > value['value'] - 3)
                    elif value['result'] == 'LOW_CLOSE':
                        # 低但是接近，使用更精确的范围
                        if key == 'age':
                            mask &= (self.possible_players[key] > value['value']) & (self.possible_players[key] < value['value'] + 4)
                        elif key == 'majorAppearances':
                            mask &= (self.possible_players[key] > value['value']) & (self.possible_players[key] < value['value'] + 3)
        
        # 应用掩码更新可能选手列表
        self.possible_players = self.possible_players[mask]
        return self.possible_players
    
    def calculate_entropy(self, column: str) -> float:
        """
        计算某个属性的信息熵
        
        Args:
            column: 属性名称
            
        Returns:
            信息熵值
        """
        value_counts = self.possible_players[column].value_counts(normalize=True)
        return -np.sum(value_counts * np.log2(value_counts))
    
    def calculate_expected_information_gain(self, player_data: Dict) -> float:
        """
        计算选择某个选手猜测可能带来的预期信息增益
        
        Args:
            player_data: 选手数据字典
            
        Returns:
            预期信息增益值
        """
        if len(self.possible_players) <= 1:
            return 0
            
        total_gain = 0
        total_weight = 0
        
        # 为每个属性计算可能的反馈和相应的概率
        for attr in self.attributes:
            # 跳过没有值的属性
            if pd.isna(player_data.get(attr)):
                continue
                
            attr_value = player_data[attr]
            
            # 计算数值型属性的可能反馈
            if attr in ['age', 'majorAppearances']:
                # 统计可能的反馈分布
                correct_prob = np.mean(self.possible_players[attr] == attr_value)
                high_not_close_prob = np.mean((self.possible_players[attr] < attr_value) & 
                                              (self.possible_players[attr] < attr_value - (3 if attr == 'age' else 2)))
                low_not_close_prob = np.mean((self.possible_players[attr] > attr_value) & 
                                              (self.possible_players[attr] > attr_value + (3 if attr == 'age' else 2)))
                high_close_prob = np.mean((self.possible_players[attr] < attr_value) & 
                                          (self.possible_players[attr] >= attr_value - (3 if attr == 'age' else 2)))
                low_close_prob = np.mean((self.possible_players[attr] > attr_value) & 
                                          (self.possible_players[attr] <= attr_value + (3 if attr == 'age' else 2)))
                
                # 计算每种反馈的可能信息增益
                total_prob = correct_prob + high_not_close_prob + low_not_close_prob + high_close_prob + low_close_prob
                if total_prob > 0:
                    # 根据每种可能反馈计算条件熵
                    feedback_entropies = []
                    feedback_probs = [correct_prob, high_not_close_prob, low_not_close_prob, high_close_prob, low_close_prob]
                    
                    for i, prob in enumerate(feedback_probs):
                        if prob > 0:
                            # 模拟该反馈下的结果集
                            if i == 0:  # CORRECT
                                subset = self.possible_players[self.possible_players[attr] == attr_value]
                            elif i == 1:  # HIGH_NOT_CLOSE
                                subset = self.possible_players[(self.possible_players[attr] < attr_value) & 
                                                              (self.possible_players[attr] < attr_value - (3 if attr == 'age' else 2))]
                            elif i == 2:  # LOW_NOT_CLOSE
                                subset = self.possible_players[(self.possible_players[attr] > attr_value) & 
                                                              (self.possible_players[attr] > attr_value + (3 if attr == 'age' else 2))]
                            elif i == 3:  # HIGH_CLOSE
                                subset = self.possible_players[(self.possible_players[attr] < attr_value) & 
                                                              (self.possible_players[attr] >= attr_value - (3 if attr == 'age' else 2))]
                            else:  # LOW_CLOSE
                                subset = self.possible_players[(self.possible_players[attr] > attr_value) & 
                                                              (self.possible_players[attr] <= attr_value + (3 if attr == 'age' else 2))]
                                
                            if len(subset) > 0:
                                # 计算反馈后的熵
                                feedback_entropies.append(prob * np.log2(len(subset)))
                    
                    # 计算该属性的信息增益
                    attr_weight = 1.0  # 可以根据属性重要性调整权重
                    if attr == 'age':
                        attr_weight = 0.8  # 年龄可能不那么具有区分性
                    
                    attr_gain = attr_weight * (np.log2(len(self.possible_players)) - sum(feedback_entropies))
                    total_gain += attr_gain
                    total_weight += attr_weight
            
            # 计算分类属性的可能反馈
            else:
                # 对于team特殊处理
                if attr == 'team':
                    # 如果是free agent，特殊处理
                    if pd.isna(attr_value):
                        correct_prob = np.mean(self.possible_players[attr].isna())
                        incorrect_prob = 1 - correct_prob
                    else:
                        correct_prob = np.mean(self.possible_players[attr] == attr_value)
                        incorrect_prob = 1 - correct_prob
                else:
                    correct_prob = np.mean(self.possible_players[attr] == attr_value)
                    incorrect_prob = 1 - correct_prob
                
                # 计算信息增益
                if correct_prob > 0 and correct_prob < 1:
                    # 模拟反馈后的结果集
                    correct_subset = self.possible_players[self.possible_players[attr] == attr_value]
                    incorrect_subset = self.possible_players[self.possible_players[attr] != attr_value]
                    
                    # 计算条件熵
                    attr_weight = 1.0  # 可以根据属性重要性调整权重
                    if attr == 'role':
                        attr_weight = 1.2  # role通常较为重要
                    
                    # 计算信息增益: 原熵 - 条件熵
                    attr_gain = attr_weight * (np.log2(len(self.possible_players)) - 
                                             (correct_prob * np.log2(len(correct_subset)) + 
                                              incorrect_prob * np.log2(len(incorrect_subset))))
                    
                    total_gain += attr_gain
                    total_weight += attr_weight
        
        # 返回平均信息增益
        return total_gain / total_weight if total_weight > 0 else 0
        
    def submit_feedback(self, feedback: Dict) -> pd.DataFrame:
        """
        提交反馈并更新可能的选手列表
        """
        self.update_possibilities(feedback)
        # 只保存nickname
        self.guess_history.append(feedback.get('nickname'))
        return self.possible_players
        
    def choose_next_guess(self) -> Optional[Dict]:
        if len(self.possible_players) == 0:
            return None
        elif len(self.possible_players) == 1:
            return self.possible_players.iloc[0].to_dict()
        
        # 第一次猜测固定为friberg
        if not self.guess_history:
            friberg = self.possible_players[self.possible_players['nickname'] == 'friberg']
            if not friberg.empty:
                return friberg.iloc[0].to_dict()
        
        # 对每个可能的选手计算预期信息增益
        info_gains = []
        for idx, player in self.possible_players.iterrows():
            # 跳过已经猜过的选手
            if player['nickname'] in self.guess_history:  # 直接比较字符串
                continue
                
            player_dict = player.to_dict()
            info_gain = self.calculate_expected_information_gain(player_dict)
            info_gains.append((idx, info_gain))
        
        if not info_gains:
            # 如果所有选手都已猜过，则选择第一个未猜过的
            for idx, player in self.possible_players.iterrows():
                if player['nickname'] not in self.guess_history:
                    return player.to_dict()
            return None
        
        # 选择信息增益最高的选手
        best_idx = max(info_gains, key=lambda x: x[1])[0]
        return self.possible_players.loc[best_idx].to_dict()

# 创建全局分析器实例
analyzer = CSPlayerAnalyzer("../Data/cs_player_Pro.xlsx")

@app.route('/api/next-guess', methods=['GET'])
def get_next_guess():
    """
    获取下一个猜测的API端点
    
    Returns:
        JSON响应，包含下一个猜测和统计信息
    """
    next_guess = analyzer.choose_next_guess()
    if not next_guess:
        return jsonify({"error": "无法继续猜测"}), 404
    
    # 获取更详细的统计信息
    stats = {}
    for attr in analyzer.attributes:
        if attr in ['nationality', 'team', 'role']:
            value_counts = analyzer.possible_players[attr].value_counts()
            stats[attr] = {
                'values': value_counts.index.tolist(),
                'counts': value_counts.values.tolist(),
                'entropy': analyzer.calculate_entropy(attr)
            }
    
    return jsonify({
        "guess": next_guess,
        "remaining_count": len(analyzer.possible_players),
        "total_players": analyzer.total_players,  # 添加总选手数
        "stats": stats
    })

@app.route('/api/submit-feedback', methods=['POST'])
def submit_feedback():
    try:
        feedback = request.json
        previous_count = len(analyzer.possible_players)
        analyzer.submit_feedback(feedback)
        current_count = len(analyzer.possible_players)
        
        # 获取下一个猜测
        next_guess = analyzer.choose_next_guess()
        next_nickname = next_guess['nickname'] if next_guess else None
        
        # 获取当前统计信息
        stats = {}
        for attr in analyzer.attributes:
            if attr in ['nationality', 'team', 'role']:
                value_counts = analyzer.possible_players[attr].value_counts()
                stats[attr] = {
                    'values': value_counts.index.tolist(),
                    'counts': value_counts.values.tolist(),
                    'entropy': analyzer.calculate_entropy(attr)
                }
        
        return jsonify({
            "success": True,
            "previous_count": previous_count,
            "current_count": current_count,
            "total_players": analyzer.total_players,  # 添加总选手数
            "next_guess": next_nickname,
            "guess_history": analyzer.guess_history,
            "stats": stats
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/api/reset', methods=['POST'])
def reset_game():
    """
    重置游戏的API端点
    
    Returns:
        JSON响应，表示重置成功
    """
    analyzer.possible_players = analyzer.df.copy()
    analyzer.guess_history = []
    return jsonify({"success": True})

if __name__ == '__main__':
    # 启动Flask服务器
    app.run(debug=True, port=5000) 
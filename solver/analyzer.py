import os
from typing import Dict, Optional

import pandas as pd
import numpy as np

# 默认选手数据库：solver/data/players_pro.xlsx（pro 难度，每日挑战用）
DEFAULT_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "players_pro.xlsx")


class CSPlayerAnalyzer:
    """
    CS:GO 选手分析器

    核心算法：基于信息熵，每一步选出期望信息增益最大的选手作为下一次猜测，
    并根据官方逐属性反馈持续收敛候选集合。
    """
    def __init__(self, excel_path: str = DEFAULT_DATA_PATH):
        """
        初始化分析器

        Args:
            excel_path: 选手数据 Excel 文件路径，默认使用内置 pro 数据库
        """
        self.df = pd.read_excel(excel_path)
        self.possible_players = self.df.copy()
        self.guess_history = []  # 存储已猜过的nickname字符串
        self.attributes = ['nationality', 'team', 'age', 'majorAppearances', 'role']
        self.total_players = len(self.df)

    def update_possibilities(self, feedback: Dict) -> pd.DataFrame:
        """
        根据反馈更新可能的选手列表

        Args:
            feedback: 包含各个属性反馈的字典

        Returns:
            更新后的可能选手DataFrame
        """
        mask = pd.Series(True, index=self.possible_players.index)

        for key, value in feedback.items():
            if isinstance(value, dict) and 'result' in value:
                if key == 'team':
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
                    if value['result'] == 'CORRECT':
                        mask &= (self.possible_players[key] == value['value'])
                    elif value['result'] in ('INCORRECT', 'INCORRECT_CLOSE'):
                        # 官方对 nationality 常返回 INCORRECT_CLOSE（同大洲/邻国），
                        # 语义等同于「不是这个值」，同样要过滤，否则会白白丢掉这条信息。
                        mask &= (self.possible_players[key] != value['value'])
                    elif value['result'] == 'HIGH_NOT_CLOSE':
                        mask &= (self.possible_players[key] < value['value'])
                    elif value['result'] == 'LOW_NOT_CLOSE':
                        mask &= (self.possible_players[key] > value['value'])
                    elif value['result'] == 'HIGH_CLOSE':
                        if key == 'age':
                            mask &= (self.possible_players[key] < value['value']) & (self.possible_players[key] > value['value'] - 4)
                        elif key == 'majorAppearances':
                            mask &= (self.possible_players[key] < value['value']) & (self.possible_players[key] > value['value'] - 3)
                    elif value['result'] == 'LOW_CLOSE':
                        if key == 'age':
                            mask &= (self.possible_players[key] > value['value']) & (self.possible_players[key] < value['value'] + 4)
                        elif key == 'majorAppearances':
                            mask &= (self.possible_players[key] > value['value']) & (self.possible_players[key] < value['value'] + 3)

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

        for attr in self.attributes:
            if pd.isna(player_data.get(attr)):
                continue

            attr_value = player_data[attr]

            if attr in ['age', 'majorAppearances']:
                correct_prob = np.mean(self.possible_players[attr] == attr_value)
                high_not_close_prob = np.mean((self.possible_players[attr] < attr_value) &
                                          (self.possible_players[attr] < attr_value - (3 if attr == 'age' else 2)))
                low_not_close_prob = np.mean((self.possible_players[attr] > attr_value) &
                                          (self.possible_players[attr] > attr_value + (3 if attr == 'age' else 2)))
                high_close_prob = np.mean((self.possible_players[attr] < attr_value) &
                                      (self.possible_players[attr] >= attr_value - (3 if attr == 'age' else 2)))
                low_close_prob = np.mean((self.possible_players[attr] > attr_value) &
                                      (self.possible_players[attr] <= attr_value + (3 if attr == 'age' else 2)))

                total_prob = correct_prob + high_not_close_prob + low_not_close_prob + high_close_prob + low_close_prob
                if total_prob > 0:
                    feedback_entropies = []
                    feedback_probs = [correct_prob, high_not_close_prob, low_not_close_prob, high_close_prob, low_close_prob]

                    for i, prob in enumerate(feedback_probs):
                        if prob > 0:
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
                                feedback_entropies.append(prob * np.log2(len(subset)))

                    attr_weight = 0.8 if attr == 'age' else 1.0
                    attr_gain = attr_weight * (np.log2(len(self.possible_players)) - sum(feedback_entropies))
                    total_gain += attr_gain
                    total_weight += attr_weight

            else:
                if attr == 'team':
                    if pd.isna(attr_value):
                        correct_prob = np.mean(self.possible_players[attr].isna())
                    else:
                        correct_prob = np.mean(self.possible_players[attr] == attr_value)
                else:
                    correct_prob = np.mean(self.possible_players[attr] == attr_value)

                incorrect_prob = 1 - correct_prob

                if 0 < correct_prob < 1:
                    correct_subset = self.possible_players[self.possible_players[attr] == attr_value]
                    incorrect_subset = self.possible_players[self.possible_players[attr] != attr_value]

                    attr_weight = 1.2 if attr == 'role' else 1.0

                    attr_gain = attr_weight * (np.log2(len(self.possible_players)) -
                                           (correct_prob * np.log2(len(correct_subset)) +
                                            incorrect_prob * np.log2(len(incorrect_subset))))

                    total_gain += attr_gain
                    total_weight += attr_weight

        return total_gain / total_weight if total_weight > 0 else 0

    def submit_feedback(self, feedback: Dict) -> pd.DataFrame:
        """
        提交反馈并更新可能的选手列表，同时记录猜测历史

        Args:
            feedback: 包含各个属性反馈的字典，需带nickname字段

        Returns:
            更新后的可能选手DataFrame
        """
        self.update_possibilities(feedback)
        self.guess_history.append(feedback.get('nickname'))
        return self.possible_players

    def choose_next_guess(self) -> Optional[Dict]:
        """
        选择下一个要猜的选手

        Returns:
            下一个要猜的选手信息字典，如果没有符合条件的选手则返回None
        """
        if len(self.possible_players) == 0:
            return None
        elif len(self.possible_players) == 1:
            return self.possible_players.iloc[0].to_dict()

        if not self.guess_history:
            friberg = self.possible_players[self.possible_players['nickname'] == 'friberg']
            if not friberg.empty:
                return friberg.iloc[0].to_dict()

        info_gains = []
        for idx, player in self.possible_players.iterrows():
            if player['nickname'] in self.guess_history:
                continue

            player_dict = player.to_dict()
            info_gain = self.calculate_expected_information_gain(player_dict)
            info_gains.append((idx, info_gain))

        if not info_gains:
            for idx, player in self.possible_players.iterrows():
                if player['nickname'] not in self.guess_history:
                    return player.to_dict()
            return None

        best_idx = max(info_gains, key=lambda x: x[1])[0]
        return self.possible_players.loc[best_idx].to_dict()

    def reset(self) -> None:
        """重置为初始状态，清空猜测历史"""
        self.possible_players = self.df.copy()
        self.guess_history = []

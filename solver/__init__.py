"""Counter-Strikle 每日挑战终端求解器。

基于信息熵的智能猜测：每一步选择期望信息增益最大的选手，
通常 2-3 次即可命中当日目标。
"""

from .analyzer import CSPlayerAnalyzer

__all__ = ["CSPlayerAnalyzer"]
__version__ = "3.0.0"

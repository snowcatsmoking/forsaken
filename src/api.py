"""
CS:GO选手猜测助手 - API服务
提供RESTful API接口，处理前端请求并返回猜测结果
作者: [SnowCat]
版本: 1.0.0
"""

from flask import Flask, request, jsonify
from flask_cors import CORS

from caice import CSPlayerAnalyzer

# 初始化Flask应用
app = Flask(__name__)
CORS(app)  # 启用跨域支持

# 创建全局分析器实例
analyzer = CSPlayerAnalyzer("../Data/cs_player_pro.xlsx")


def _build_stats() -> dict:
    stats = {}
    for attr in analyzer.attributes:
        if attr in ['nationality', 'team', 'role']:
            value_counts = analyzer.possible_players[attr].value_counts()
            stats[attr] = {
                'values': value_counts.index.tolist(),
                'counts': value_counts.values.tolist(),
                'entropy': analyzer.calculate_entropy(attr)
            }
    return stats


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

    return jsonify({
        "guess": next_guess,
        "remaining_count": len(analyzer.possible_players),
        "total_players": analyzer.total_players,
        "stats": _build_stats()
    })


@app.route('/api/submit-feedback', methods=['POST'])
def submit_feedback():
    try:
        feedback = request.json
        previous_count = len(analyzer.possible_players)
        analyzer.submit_feedback(feedback)
        current_count = len(analyzer.possible_players)

        next_guess = analyzer.choose_next_guess()
        next_nickname = next_guess['nickname'] if next_guess else None

        return jsonify({
            "success": True,
            "previous_count": previous_count,
            "current_count": current_count,
            "total_players": analyzer.total_players,
            "next_guess": next_nickname,
            "guess_history": analyzer.guess_history,
            "stats": _build_stats()
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
    analyzer.reset()
    return jsonify({"success": True})


if __name__ == '__main__':
    # 启动Flask服务器
    app.run(debug=True, port=5000)

"""
全自动猜测脚本：直接调用BLAST官方guesses接口提交猜测，
用算法拿到的真实反馈自动计算下一个猜测，直到命中为止。
无需用户手动复制JSON。
"""

import os
import time
import random
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from caice import CSPlayerAnalyzer

GUESS_URL = "https://api.blast.tv/v1/counterstrikle/guesses"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://blast.tv",
    "Referer": "https://blast.tv/",
}


def build_session() -> requests.Session:
    session = requests.Session()
    retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def submit_guess(session: requests.Session, player_id: str) -> dict:
    payload = {
        "playerId": player_id,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    response = session.post(GUESS_URL, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()


def auto_solve(excel_path: str, max_guesses: int = 20, delay_range=(1, 2)) -> None:
    analyzer = CSPlayerAnalyzer(excel_path)
    session = build_session()

    for step in range(1, max_guesses + 1):
        guess = analyzer.choose_next_guess()
        if guess is None:
            print("没有更多候选选手，猜测失败")
            return

        print(f"第{step}次猜测: {guess['nickname']}")
        feedback = submit_guess(session, guess["id"])
        analyzer.guess_history.append(guess["nickname"])

        if feedback.get("isSuccess"):
            print(f"命中！目标选手是: {feedback['nickname']}（共猜{step}次）")
            return

        analyzer.update_possibilities(feedback)
        remaining = len(analyzer.possible_players)
        print(f"  反馈: {feedback}")
        print(f"  剩余候选: {remaining}")

        time.sleep(random.uniform(*delay_range))

    print("已达到最大猜测次数，仍未命中")


if __name__ == "__main__":
    data_path = os.path.join(os.path.dirname(__file__), "..", "Data", "cs_player_pro.xlsx")
    auto_solve(data_path)

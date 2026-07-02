"""每日挑战终端求解器。

直接调用 BLAST 官方 guesses 接口提交猜测，用真实反馈驱动信息熵算法自动迭代，
直到命中当日目标。无需任何前端或手动复制 JSON——一条命令跑到底。

用法：
    python -m solver.daily_solve                # 默认自动求解
    python -m solver.daily_solve --no-color     # 关闭彩色（重定向/CI 友好）
    python -m solver.daily_solve --delay 0.5    # 每步间隔（秒），追求速度可调小
    python -m solver.daily_solve --max-guesses 8
"""

import argparse
import sys
import time
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

from .analyzer import CSPlayerAnalyzer, DEFAULT_DATA_PATH

GUESS_URL = "https://api.blast.tv/v1/counterstrikle/guesses"
# sb6657.cn 玩机器直播间烂梗接口（第三方调用不带 dpahjdoiaw 统计头）
MEME_URL = "https://hguofichp.cn:10086/machine/getRandOne"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": "https://blast.tv",
    "Referer": "https://blast.tv/",
}

# 逐属性反馈 → 展示格子（emoji + 文案），对齐官方 result 枚举
FEEDBACK_TILES = {
    "CORRECT":        ("🟩", "命中"),
    "INCORRECT":      ("🟥", "错误"),
    "INCORRECT_CLOSE": ("🟨", "接近"),
    "HIGH_NOT_CLOSE": ("🔽", "偏高"),
    "LOW_NOT_CLOSE":  ("🔼", "偏低"),
    "HIGH_CLOSE":     ("🔻", "略高"),
    "LOW_CLOSE":      ("🔺", "略低"),
}
ATTR_LABELS = {
    "nationality": "国籍",
    "team": "战队",
    "age": "年龄",
    "majorAppearances": "Major",
    "role": "定位",
}


# --------------------------------------------------------------------------- #
# 终端样式：纯标准库 ANSI，非 TTY 自动降级为无色，零额外依赖
# --------------------------------------------------------------------------- #
class Style:
    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def dim(self, t):     return self._wrap("2", t)
    def bold(self, t):    return self._wrap("1", t)
    def cyan(self, t):    return self._wrap("96", t)
    def green(self, t):   return self._wrap("92", t)
    def yellow(self, t):  return self._wrap("93", t)
    def red(self, t):     return self._wrap("91", t)
    def magenta(self, t): return self._wrap("95", t)


def print_banner(style: Style) -> None:
    art = r"""
   ______                 __             _____ __       _ __   __
  / ____/___  __  ______  / /____  _____/ ___// /______(_) /__/ /__
 / /   / __ \/ / / / __ \/ __/ _ \/ ___/\__ \/ __/ ___/ / //_/ / _ \
/ /___/ /_/ / /_/ / / / / /_/  __/ /   ___/ / /_/ /  / / ,< / /  __/
\____/\____/\__,_/_/ /_/\__/\___/_/   /____/\__/_/  /_/_/|_/_/\___/
"""
    print(style.cyan(art))
    print("  " + style.bold("弗一把小助手 · 每日挑战自动求解器") +
          style.dim("  —  信息熵驱动，2-3 步锁定目标"))
    print(style.dim("  " + "─" * 62))


def render_feedback(feedback: dict, style: Style) -> str:
    """把一条猜测的逐属性反馈渲染成一行紧凑的格子。"""
    cells = []
    for attr, label in ATTR_LABELS.items():
        info = feedback.get(attr)
        result = info.get("result") if isinstance(info, dict) else None
        icon, _ = FEEDBACK_TILES.get(result, ("⬜", ""))
        cells.append(f"{icon} {style.dim(label)}")
    return "  ".join(cells)


def build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
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


def fetch_meme(session: requests.Session) -> str:
    """从 sb6657.cn 抽一条玩机器直播间烂梗；任何异常都静默返回空串（纯彩蛋，不影响主流程）。"""
    try:
        res = session.get(MEME_URL, timeout=5)
        res.raise_for_status()
        return (res.json().get("data") or {}).get("barrage", "") or ""
    except Exception:
        return ""


def auto_solve(excel_path: str = DEFAULT_DATA_PATH, max_guesses: int = 20,
               delay: float = 1.0, style: Style = None) -> bool:
    """自动求解当日挑战，返回是否命中。"""
    style = style or Style(enabled=False)
    analyzer = CSPlayerAnalyzer(excel_path)
    session = build_session()

    print(style.dim(f"  选手库共 {analyzer.total_players} 人，开始求解…\n"))

    for step in range(1, max_guesses + 1):
        guess = analyzer.choose_next_guess()
        if guess is None:
            print(style.red("  ✗ 没有更多候选选手，求解失败（选手库可能已过期，请更新数据）"))
            return False

        prefix = style.magenta(f"  [{step}]")
        print(f"{prefix} 猜测 {style.bold(guess['nickname'])} …", flush=True)

        feedback = submit_guess(session, guess["id"])
        analyzer.guess_history.append(guess["nickname"])

        if feedback.get("isSuccess"):
            print(f"      {render_feedback(feedback, style)}")
            print()
            print(style.green(f"  ★ 命中！目标是 {style.bold(feedback['nickname'])}"
                              f"  ·  共 {step} 步  ·  弗一把赢麻了 🎉"))
            meme = fetch_meme(session)
            if meme:
                print(style.dim("  ── 今日烂梗 ──"))
                print("  " + style.magenta(meme) + style.dim("   —— 6657 直播间"))
            return True

        analyzer.update_possibilities(feedback)
        remaining = len(analyzer.possible_players)
        print(f"      {render_feedback(feedback, style)}")
        print(f"      {style.dim('剩余候选')} {style.yellow(str(remaining))}\n")

        if delay > 0:
            time.sleep(delay)

    print(style.red(f"  ✗ 已达最大猜测次数（{max_guesses}），仍未命中"))
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="solver.daily_solve",
        description="Counter-Strikle 每日挑战自动求解器（信息熵）",
    )
    parser.add_argument("--data", default=DEFAULT_DATA_PATH, help="选手数据 Excel 路径")
    parser.add_argument("--max-guesses", type=int, default=20, help="最大猜测次数")
    parser.add_argument("--delay", type=float, default=1.0, help="每步间隔秒数（追求速度可设 0）")
    parser.add_argument("--no-color", action="store_true", help="关闭彩色输出")
    args = parser.parse_args(argv)

    use_color = not args.no_color and sys.stdout.isatty()
    style = Style(enabled=use_color)

    print_banner(style)
    try:
        hit = auto_solve(args.data, args.max_guesses, args.delay, style)
    except requests.HTTPError as exc:
        print(style.red(f"\n  网络/接口错误：{exc}"))
        print(style.dim("  提示：每日挑战需在浏览器登录 blast.tv 后当天有效，接口可能带 session。"))
        return 2
    except KeyboardInterrupt:
        print(style.dim("\n  已中断"))
        return 130
    return 0 if hit else 1


if __name__ == "__main__":
    raise SystemExit(main())

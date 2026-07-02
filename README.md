<div align="center">

<img src="extension/icon.png" width="96" alt="玩机器 machine" />

# Counter-Strikle 弗一把小助手

基于信息熵的 [BLAST Counter-Strikle](https://blast.tv/counter-strikle) 智能猜测工具。

分析选手的多维属性（国籍、战队、年龄、Major 出场次数、角色），
每一步选出**期望信息增益最大**的猜测，通常 2–3 次即命中目标。

</div>

---

## 两大功能

| 功能 | 场景 | 目录 | 形态 |
| --- | --- | --- | --- |
| 🧩 **每日挑战求解** | 单人每日挑战 | [`solver/`](solver/) | 单条命令的终端脚本，直连官方接口，自动猜到命中 |
| 🤖 **浏览器插件** | 对战模式（multiplayer） | [`extension/`](extension/) | 即插即用扩展，实时浮层建议 + 一键更新数据库 |

> 每日挑战为单人玩法，本地自娱自乐无妨；对战 PVP 请理性使用，尊重对手。

---

## 功能一：每日挑战终端求解器

一条命令跑到底——脚本直连官方 `guesses` 接口提交猜测、用真实反馈驱动信息熵算法自动迭代，
终端里带彩色反馈格子实时展示收敛过程，无需任何前端或手动复制 JSON。

### 环境

- Python 3.9+

```bash
pip install -r requirements.txt
```

### 运行

```bash
# 在仓库根目录执行
python -m solver.daily_solve
```

常用参数：

| 参数 | 说明 |
| --- | --- |
| `--delay 0.5` | 每步间隔秒数，追求速度可设 `0` |
| `--max-guesses 8` | 最大猜测次数 |
| `--no-color` | 关闭彩色输出（重定向 / CI 友好） |
| `--data <path>` | 指定选手数据 Excel（默认 `solver/data/players_pro.xlsx`） |

反馈格子含义：🟩 命中 · 🟥 错误 · 🟨 接近 · 🔻略高 / 🔺略低 · 🔽偏高 / 🔼偏低。

### 更新选手数据

选手库随赛事更新。重新抓取覆盖默认数据文件：

```bash
python -m solver.scraper
```

---

## 功能二：浏览器插件

Chrome 扩展（Manifest V3），在对战房间页面右上角浮层实时显示轮次、下一步建议、剩余候选数，
支持「自动弗」自动提交，并内置**一键手动更新选手数据库**。

### 安装（即插即用）

1. 打开 `chrome://extensions`，开启右上角「开发者模式」
2. 点击「加载已解压的扩展程序」，选择 [`extension/`](extension/) 目录
3. 进入对战房间 `https://blast.tv/counter-strikle/multiplayer/*`，右上角出现浮层即生效

### 手动更新数据库

当遇到**猜不到的新选手**（数据库过期）时，点面板底部的 **⟳ 更新选手库** 按钮：
插件会直连官方 API 重新抓取全部选手，带实时进度，结果存入 `chrome.storage.local`。
更新一次长期生效，下次进房自动加载新库，无需重装扩展。

### 原理

- 以 MV3 原生 `world: "MAIN"` 在 `document_start` 注入 [`ws_hook.js`](extension/ws_hook.js)，
  劫持 `window.WebSocket`（绕开页面 CSP，且保证在页面创建连接前生效，消除注入时机竞态）
- [`content_script.js`](extension/content_script.js) 解析对局状态，用
  [`analyzer.js`](extension/analyzer.js)（与 `solver/analyzer.py` 等价的 JS 版信息熵算法）
  计算最优猜测，Shadow DOM 浮层展示
- 「自动弗」模式下反向通过 `postMessage` 让被劫持的 WebSocket 直接 `send()` 提交猜测

---

## 项目结构

```
forsaken/
├── solver/                     # 功能一：每日挑战终端求解器
│   ├── analyzer.py             # 核心信息熵算法（CSPlayerAnalyzer）
│   ├── daily_solve.py          # 终端主入口（彩色 TUI，直连官方接口自动迭代）
│   ├── scraper.py              # 选手数据抓取
│   └── data/players_pro.xlsx   # 选手数据库（pro 难度）
├── extension/                  # 功能二：对战模式插件（MV3）
│   ├── manifest.json
│   ├── ws_hook.js              # MAIN world WebSocket 劫持
│   ├── content_script.js       # 状态解析 + UI 面板 + 手动更新数据库
│   ├── analyzer.js             # 信息熵算法（JS 版）
│   ├── panel.css
│   ├── players_data.json       # 内置默认选手库
│   └── icon.png                # 玩机器 machine 头像
├── requirements.txt
├── LICENSE
├── README.md
└── BLOG.md                     # 算法原理详解
```

## 算法原理

核心思想：每一步选择**期望信息增益最大**的猜测，最快缩小候选范围。详见 [BLOG.md](BLOG.md)。

Python 版（`solver/analyzer.py`）与 JS 版（`extension/analyzer.js`）逻辑一致，共用同一套反馈语义。

## 彩蛋：玩机器烂梗联动

终端命中时、以及插件面板底部，会展示一条来自 [sb6657.cn](https://sb6657.cn)
（斗鱼 6657 玩机器直播间弹幕收集站）的随机烂梗，点击可复制、可换一条。
纯彩蛋，接口不可用时静默降级，不影响主流程。数据来源 [SEhzm/sb6657](https://github.com/SEhzm/sb6657)。

## 致谢

- 感谢 BLAST.tv 提供的游戏
- 特别感谢玩机器 machine 的弗开策略
- 烂梗联动数据来自 [sb6657.cn](https://sb6657.cn) / [SEhzm/sb6657](https://github.com/SEhzm/sb6657)

## License

[MIT](LICENSE) © 2026 SnowCat

问题或建议欢迎提交 Issue，或邮件 panmingh@outlook.com

# Counter-Strikle 弗一把助手

基于信息熵的 [BLAST Counter-Strikle](https://blast.tv/counter-strikle) 智能猜测工具，帮你快速锁定目标 CS 职业选手。

通过分析选手的多维属性（国籍、队伍、年龄、Major 出场次数、角色），用信息熵算法在每一步选出**期望信息增益最大**的猜测，通常 2–3 次即可命中。

## 两大功能

| 功能 | 场景 | 目录 |
| --- | --- | --- |
| 🧩 **本地拆每日挑战** | 单人每日挑战。本地 Web 界面粘贴反馈，算法给出下一步最优猜测 | [`src/`](src/) |
| 🤖 **浏览器插件自动完成** | 对战模式（multiplayer）。插件劫持 WebSocket 实时解析对局，自动提交猜测 | [`browser_extension/`](browser_extension/) |

> 每日挑战为单人玩法，本地辅助自娱自乐无妨；对战 PVP 请理性使用，尊重对手。

## 功能一：本地拆每日挑战

基于 Flask 后端 + 纯前端页面，粘贴游戏反馈即可得到下一步建议。

### 环境要求

- Python 3.9+
- 现代浏览器（Chrome / Firefox / Safari）

### 使用步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动后端服务
cd src
python api.py            # 监听 http://localhost:5000
```

然后用浏览器打开 [`src/static/index.html`](src/static/index.html)。

界面操作：

1. 程序默认第一个猜测为 `friberg`（致敬玩机器 machine）
2. 在游戏页面按 `F12` → `Network` 面板 → 找到 `guesses` 请求 → 复制 Response 的 JSON
3. 把 JSON 粘贴进输入框，点击「提交反馈」
4. 重复 2–3 直到命中（页面会实时显示剩余候选、下一步建议、属性分布）

### 反馈格式示例

```json
{
  "nationality": { "result": "INCORRECT", "value": "Sweden" },
  "team": { "result": "INCORRECT", "data": { "name": "Ninjas in Pyjamas" } },
  "age": { "result": "HIGH_NOT_CLOSE", "value": 31 }
}
```

支持的反馈类型：`CORRECT`、`INCORRECT`、`HIGH_NOT_CLOSE`、`LOW_NOT_CLOSE`、`HIGH_CLOSE`、`LOW_CLOSE`。

### 全自动脚本（可选）

[`src/auto_solve.py`](src/auto_solve.py) 直接调用官方 `guesses` 接口提交猜测并用真实反馈自动迭代，无需手动复制 JSON：

```bash
cd src
python auto_solve.py
```

## 功能二：浏览器插件自动完成

Chrome 扩展（Manifest V3），在对战房间页面右上角浮层实时显示轮次、下一步建议、剩余候选数，并支持「自动弗」模式自动提交猜测。

### 安装

1. 打开 `chrome://extensions`，开启右上角「开发者模式」
2. 点击「加载已解压的扩展程序」，选择 [`browser_extension/`](browser_extension/) 目录
3. 进入对战房间 `https://blast.tv/counter-strikle/multiplayer/*`，右上角出现浮层即生效

### 原理

- 以 Manifest V3 原生 `world: "MAIN"` 在 `document_start` 注入 [`ws_hook.js`](browser_extension/ws_hook.js)，劫持 `window.WebSocket`（绕开页面 CSP，且保证在页面创建连接前生效）
- [`content_script.js`](browser_extension/content_script.js) 解析对局状态，用 [`analyzer.js`](browser_extension/analyzer.js)（与 `caice.py` 等价的 JS 版信息熵算法）计算最优猜测，Shadow DOM 浮层展示
- 「自动弗」模式下反向通过 `postMessage` 让被劫持的 WebSocket 直接 `send()` 提交猜测

## 项目结构

```
forsaken/
├── src/                      # 功能一：本地每日挑战
│   ├── caice.py              # 核心算法（信息熵）
│   ├── api.py                # Flask API 服务
│   ├── auto_solve.py         # 全自动脚本（直连官方接口）
│   ├── paqu.py               # 选手数据爬虫
│   └── static/index.html     # Web 界面
├── browser_extension/        # 功能二：对战模式插件（MV3）
│   ├── manifest.json
│   ├── ws_hook.js            # MAIN world WebSocket 劫持
│   ├── content_script.js     # 状态解析 + UI 面板
│   ├── analyzer.js           # 信息熵算法（JS 版）
│   ├── panel.css
│   └── players_data.json     # 选手数据
├── Data/                     # 选手数据（Excel）
│   ├── cs_player_pro.xlsx     # Pro 难度（默认，每日挑战）
│   └── cs_player_noob.xlsx    # Noob 难度
├── requirements.txt
├── README.md
└── BLOG.md                   # 算法原理详解
```

## 更新选手数据

运行 [`src/paqu.py`](src/paqu.py) 爬虫重新抓取，覆盖 `Data/cs_player_pro.xlsx` 即可（保持原字段格式）：

```bash
cd src
python paqu.py
```

## 算法原理

核心思想：每一步选择**期望信息增益最大**的猜测，最快缩小候选范围。详见 [BLOG.md](BLOG.md)。

## 致谢

- 感谢 BLAST.tv 提供的游戏
- 特别感谢玩机器 machine 的弗开策略

## 联系方式

问题或建议欢迎提交 Issue，或邮件 panmingh@outlook.com

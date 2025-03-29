# BLAST弗一把速通脚本（算法层）

一个基于信息熵的CS:GO职业选手猜测游戏，通过智能算法帮助你快速找到目标选手。

## 项目简介

本项目是一个基于信息熵的智能猜测系统，专门用于CS:GO职业选手猜测游戏。系统通过分析选手的各种属性（国籍、队伍、年龄、Major出场次数、角色），使用信息熵算法选择最优的猜测策略，帮助用户快速找到目标选手。

### 主要特性

- 🧠 基于信息熵的智能猜测算法
- 🌐 直观的Web界面
- 🔄 RESTful API支持
- 📊 实时统计分析
- 🎯 支持多种反馈类型
- ⚡ 高效的猜测策略

## 快速开始

### 环境要求

- Python 3.7+
- 现代浏览器（Chrome/Firefox/Safari）
- 基本的CS:GO职业选手知识

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/snowcatsmoking/forsaken.git
cd forsaken
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 启动后端服务
```bash
cd src
python api.py
```

4. 在浏览器中打开`src/static/index.html`

### 使用说明

1. 程序会自动选择第一个猜测（默认为"friberg"）//尊重玩机器machine
2. 从游戏网站获取反馈，复制JSON格式的反馈内容

这边内容较为复杂，需要User用F12进入开发者见面，然后在Network大类里面找到guess请求，并且把guess里面response的json内容复制下来。

这也将是本脚本的优化方向！

3. 将反馈粘贴到输入框中，点击"提交反馈"
4. 重复步骤2-3直到找到正确答案//一般2-3次即可获得正确答案

### 反馈格式示例

```json
{
    "nationality": {
        "result": "INCORRECT",
        "value": "Sweden"
    },
    "team": {
        "result": "INCORRECT",
        "data": {
            "name": "Ninjas in Pyjamas"
        }
    },
    "age": {
        "result": "HIGH_NOT_CLOSE",
        "value": 31
    }
}
```

## 项目结构

```
forsaken/
├── src/              # 源代码目录
│   ├── api.py        # API服务
│   ├── caice.py      # 核心算法实现
│   └── static/       # 静态文件
│       └── index.html # Web界面
├── Data/             # 数据文件目录
│   └── cs_player_Pro.xlsx  # 选手数据
├── requirements.txt  # 依赖列表
├── README.md        # 项目说明
└── BLOG.md          # 技术博客
```

## 算法原理

本项目使用了基于信息熵的智能猜测算法，通过计算每个可能猜测的期望信息增益来选择最优的下一个猜测。详细算法说明请参考[BLOG.md](BLOG.md)。

BLOG内容也将发布在作者的个人网站上:panmingh.com 欢迎访问！

## 常见问题

1. **Q: 为什么第一个猜测总是"friberg"？**
   A: 这是为了致敬CS:GO职业解说玩机器machine，尊重弗开。（虽然说从算法层面信息熵最高的是Hooxi）

2. **Q: 如何更新选手数据？**
   A: 直接更新`Data/cs_player_Pro.xlsx`文件即可，确保保持原有的数据格式。paqu.py就是我们的爬虫程序，简单易用。

    注：默认设置为Pro版本，主要是针对每日挑战，开挂PVP不提倡！！！

3. **Q: 支持哪些反馈类型？**
   A: 支持CORRECT、INCORRECT、HIGH_NOT_CLOSE、LOW_NOT_CLOSE、HIGH_CLOSE、LOW_CLOSE六种反馈类型。

## 致谢

- 感谢BLAST.tv给出这么好玩的一个游戏
- 特别感谢玩机器machine给出的弗开策略
- 感谢牢大的诋毁让作者在公式的路上一去不复返

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交Issue
- 发送邮件至：[panmingh@outlook.com]
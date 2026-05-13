# 曾国藩语录国风卡片生成器

一个小型 Python 项目，用结构化 JSON 管理曾国藩语录，并生成水墨国风语录卡片。

## 目录

- `data/quotes.json`：50 条语录，覆盖修身、处世、治学、识人、持家。
- `data/prompt_templates.json`：fal.ai 背景图 Prompt 模板。
- `generate_card.py`：生成卡片的命令行脚本。
- `output/`：生成结果目录。

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

如果只生成离线样卡，系统已有 Pillow 时也可以直接运行：

```bash
python3 generate_card.py --offline
```

## 使用

随机生成一张离线样卡：

```bash
python3 generate_card.py --offline
```

指定分类：

```bash
python3 generate_card.py --offline --category 修身
```

指定语录 ID：

```bash
python3 generate_card.py --offline --quote-id zgf_001
```

使用 fal.ai 生成背景：

```bash
export FAL_KEY="你的 fal.ai API key"
python3 generate_card.py
```

> 建议让 fal.ai 只生成“无文字背景”，中文正文由 Python 叠加，避免模型生成错字。

## 数据说明

曾国藩语录流传版本很多，本库第一版把不少常见语句标为 `medium` 或 `low` 可信度，适合做内容产品原型。若用于出版、商业账号长期内容库，建议后续逐条对照《曾国藩家书》《曾国藩日记》《曾国藩全集》《冰鉴》等版本校勘。


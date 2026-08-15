# viz-universal

[![CI](https://github.com/tanglp5655/viz-universal/actions/workflows/ci.yml/badge.svg)](https://github.com/tanglp5655/viz-universal/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/tanglp5655/viz-universal)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![GitHub stars](https://img.shields.io/github/stars/tanglp5655/viz-universal)](https://github.com/tanglp5655/viz-universal)

把任意行业的明细数据（Excel / CSV / JSON / SQLite / URL）转成一个 **单文件 HTML 看板**：脱敏、可选密码加密（默认免密）、完全离线、手机/电脑可用，并通过 **声明式 viz-schema** 让不同行业用一份配置即可适配，无需改代码。

> 跨行业通用可视化 · 图表 + 真实中国地图（省→市→区钻取）+ 人物画像 · 脱敏 + 加密 · 全图点击联动

## ✨ 特性

- **11+ 图表类型**：KPI / 月度走势 / 维度排行 / 转化漏斗 / 矩阵热力 / 流向桑基 / 多维雷达 / 目标仪表盘 / 层级树图 / 关系拓扑 / 留存矩阵
- **真实中国地图**：合规边界（DataV GeoJSON，离线无 key）+ 金额颜色深浅 + 省→市→区逐级钻取 + 双向联动筛选
- **脱敏分级**：L0–L3（原样 / 姓名掩码 / 编号化 / 编号+代号+金额缩放）
- **密码加密**：SHA256-KDF（12 万次迭代）+ CTR 流加密，`file://` 双击即用，纯 JS 解密
- **声明式 schema**：行业差异 = 一个 JSON，7 个行业开箱即用（generic / sales / education / retail / clinic / logistics / b2b），新增行业零改引擎
- **10 套视觉主题**：apple-glass / stripe / vercel / linear / bloomberg / notion / neubrutalism / tokyo-night / nordic / cyberpunk
- **单文件交付**：内嵌图表库，双击打开，断网可用；可部署任意静态托管

## 🚀 快速上手

```bash
# 方式一：可编辑安装（推荐，保留 assets/references 数据目录引用）
pip install -e .
viz-anonymize -i 数据.xlsx -o data_masked.json --level L2 --industry education
viz-build -i data_masked.json -o 看板.html -p 你的密码 --industry education

# 方式二：直接跑脚本（无需安装，任意平台）
python scripts/anonymize.py -i 数据.xlsx -o data_masked.json --level L2
python scripts/build_dashboard.py -i data_masked.json -o 看板.html --no-lock

# 方式三：stdin 管道（JSON 从标准输入读入，-i -）
cat data.json | python scripts/anonymize.py -i - -o data_masked.json --level L2
```

> 注：普通 `pip install .`（非 editable）会把 scripts 拷贝到 site-packages，而 assets/references 数据目录在仓库根，运行时需要 `VIZ_UNIVERSAL_HOME` 指向仓库根；推荐始终用 `pip install -e .` 或直接运行脚本。

免密码直开用 `--no-lock`（数据仍脱敏）；查看全部主题：`viz-build --list-themes`。

## 📖 文档

| 文档 | 说明 |
|---|---|
| [SKILL.md](SKILL.md) | 完整使用指南（三步流程 / 参数表 / 9 类图配置说明 / 安全边界） |
| [references/FAQ.md](references/FAQ.md) | 常见问题与故障排查 |
| [references/THEMES.md](references/THEMES.md) | 10 套主题清单与新增主题方法 |
| [references/schema/example.json](references/schema/example.json) | 最全 schema 示例（含全部可选面板） |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构设计 |
| [CHANGELOG.md](CHANGELOG.md) | 变更记录 |

## 🧪 回归测试

```bash
python test_all_industries.py        # 7 行业端到端：脱敏→加密→node 真解密→泄漏检查
python test_all_industries.py --keep # 保留产物便于检查
```

退出码 0 = 全通过。

## 🛡 安全边界

1. HTML 只存密码校验串，不存密码本身；密钥派生 12 万次迭代。
2. 这是"防偷看"级，非金融级；真正机密勿外发。
3. `mapping.json`（编号↔真名对照表）本地留存，绝不随看板发出。
4. 对外版脚注提示"请勿转发截图至外部渠道"。

## 📜 License

[MIT](LICENSE)

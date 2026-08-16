---
name: viz-universal
title: 跨行业通用可视化（数据看板生成器）
description: 【中文名：跨行业通用可视化（数据看板生成器）】跨行业通用的数据/流程可视化技能，把任意结构化数据（Excel/CSV/JSON/SQLite/URL，覆盖销售、运营、物流、医疗、教育、零售、外贸等）做成「脱敏 + 可选密码加密（默认免密）」的单文件交互看板：KPI/走势/排行/漏斗/热力/桑基/雷达/仪表盘/树图/拓扑/留存/人物画像/明细表 + 真实中国地图（省→市→区钻取）+ 世界地图（22 国州/省地图下钻）+ 全图点击联动 + 手机端。声明式 viz-schema 零代码适配不同行业。触发词：跨行业通用可视化、数据看板生成器、可视化、看板、数据可视化、图表、报表、数据大屏、销售看板、收入分析、经营分析、行业看板、地图可视化、脱敏、加密看板、做个看板、dashboard、BI。
metadata:
  author: WorkBuddy
  version: "0.8.0"
  agent_created: true
---

# 跨行业通用可视化 (viz-universal)

把任意行业的明细数据（Excel / CSV / JSON / SQLite / URL）转成一个 **单文件 HTML 看板**：
脱敏、可选密码加密（默认免密直开）、完全离线、手机/电脑可用，并通过 **声明式 viz-schema** 让不同行业用一份配置即可适配，无需改代码。

继承自 `sales-viz-secure` 的成熟能力：脱敏、加密、离线单文件、真实中国地图（合规边界+颜色深浅+钻取）、双向联动。在此之上新增「配置即行业」的通用化抽象。

> **📑 按需跳读**（本文件较长，不必一次读完）：
> - 新手快速上手 → [README「3 分钟起步」](README.md)
> - 行业配置（schema）→ [§声明式 viz-schema](#声明式-viz-schema跨行业适配核心)
> - 面板/图表配置 → [§看板功能](#看板功能) · [§更多面板配置](#更多面板配置)
> - 报告/输出规范 → [§交付方式](#交付方式) · [§输出规范（通用条款）](#输出规范通用条款--所有行业适用缺失字段处理)
> - 脱敏/加密/安全 → [§安全边界](#安全边界)
> - 问题排查 → [references/FAQ.md](references/FAQ.md)

## 何时使用

用户说"做个看板""数据可视化""行业看板""地图可视化""数据要脱敏/加密码""把这个 Excel 做成能看的图表"——用本技能。
与 `sales-viz-secure` 的区别：本技能面向**任意行业**，行业差异由 `references/schema/*.json` 配置驱动。

## 三步流程

### 第 0 步：访问方式（默认免密直开，密码为可选接口）
- **默认**：不传 `-p` → 免密直开（数据仍脱敏），做完看板后随时可用。
- **可选**：传 `-p 你的密码` → 加密（建议 8 位以上）；以后要补密码随时重新生成一次即可。

### 第 1 步：确认信息
数据文件（必问）、脱敏等级（默认 L2）、**行业/配置**（决定看板标签与面板）；密码可选（不问则免密直开，先出结果再补加密）。

### 第 2 步：脱敏 + 标准化
```bash
# 解释器与技能目录可用环境变量覆盖（VIZ_UNIVERSAL_HOME 指向技能根目录）；已 pip install -e . 则直接 viz-anonymize
PY="${PYTHON:-C:/Users/jiang/.workbuddy/binaries/python/versions/3.13.12/python.exe}"
SK="${VIZ_UNIVERSAL_HOME:-C:/Users/jiang/.workbuddy/skills/viz-universal}"
"$PY" "$SK/scripts/anonymize.py" -i 数据.xlsx -o data_masked.json --level L2 --industry generic
```
`--industry` 决定列语义识别（generic/education/retail/clinic/b2b，见 `references/industry/`）。也支持 stdin 管道：`cat data.json | "$PY" "$SK/scripts/anonymize.py" -i - -o data_masked.json --level L2`。**多源输入**：xlsx / csv / json / sqlite（`--sheet` 指定表名）/ http(s) URL / stdin 六种，`-i` 直接传即可。

### 第 3 步：生成看板（携带 viz-schema）
```bash
# 方式一：按行业自动加载 references/schema/<industry>.json
"$PY" "$SK/scripts/build_dashboard.py" -i data_masked.json -o 看板.html -p 用户密码 --industry sales
# 方式二：显式指定 schema 文件（也支持 stdin：-i -）
"$PY" "$SK/scripts/build_dashboard.py" -i data_masked.json -o 看板.html --no-lock --schema "$SK/references/schema/logistics.json"
```
不传 `--schema`/`--industry` 时回退 `generic.json`（中性、通用）。

| 参数 | 说明 |
|---|---|
| `--schema path.json` | 声明式行业配置（面板显隐/顺序/标签/主题/安全），生成前自动校验 |
| `--industry X` | 自动加载 `references/schema/X.json`，默认 `generic` |
| `-p` / `--no-lock` | 【可选】`-p 密码` 加密访问；不传默认免密直开（数据仍脱敏） |
| `--viewer-password` | 【可选·分级权限】访客密码：配 `-p` 使用，访客打开仅见聚合视图（自动排除敏感字段） |
| `--viewer-fields` | 访客视图排除的敏感字段，默认 `n,teacher,signer` |
| `--wizard` | 交互向导：逐项问答生成参数（仅终端） |
| `--sample N` | 随机采样 N 条生成（大数据演示，固定种子可复现） |
| `--title` / `--lock-title` | 看板标题 / 锁屏标题（别写公司名） |
| `--default-chart` | 维度图样式 barv/barh/area/line |
| `--theme` | 视觉主题 id（10 套，见 `references/THEMES.md`） |
| `--cdn` | 图表库走 CDN（需联网，体积小） |

## 声明式 viz-schema（跨行业适配核心）

**行业差异全部沉淀为配置文件，引擎代码零改动。** 每个行业 = 一个 JSON：

```json
{
  "meta":   {"industry": "logistics", "title_default": "仓网分析看板", "lang": "zh", "compliance": "cn"},
  "labels": {"geo": "仓网分布", "gender": "人员性别", "age": "人员年龄"},
  "panels": ["geo", "table"],
  "theme":  {"palette": "logistics"},
  "security":{"anonymize": "L1", "encrypt": true, "passwordByUser": true}
}
```

| 字段 | 作用 |
|---|---|
| `meta.industry` | 行业标识；`--industry` 据此自动匹配文件 |
| `labels.geo/gender/age` | 覆盖面板标题（如把"地区分布"改"仓网分布"） |
| `panels` | 面板**显隐与顺序**：`gauge`(目标达成率仪表盘)、`funnel`(转化漏斗)、`sankey`(流向桑基)、`treemap`(层级占比树图)、`topology`(关系拓扑图)、`heatmap`(矩阵热力)、`radar`(多维对比雷达)、`cohort`(转化留存矩阵)、`geo`(真实地图/地区钻取)、`gender`(男女比例)、`age`(年龄结构)、`table`(明细)；基础面板 KPI/月度走势/维度排行始终渲染 |
| `funnel` | 漏斗图配置（见下），`panels` 含 `funnel` 且配置存在时才渲染 |
| `heatmap` | 矩阵热力图配置（见下），`panels` 含 `heatmap` 且配置存在时才渲染 |
| `theme.palette` | 配色主题（占位，预留） |
| `security` | 默认脱敏等级、是否加密、密码是否用户自定 |

**漏斗图 `funnel` 配置**（解析阶段列聚合，按 `stages` 顺序自上而下展示，随筛选联动重算）：

```json
"funnel": {
  "title": "销售转化漏斗",
  "stageKey": "stage",          // 数据中表示「阶段」的列（标准 key；中文列名如「阶段/状态」会被 anonymize 自动归并到 stage）
  "measure": "a",               // "a"=按金额汇总；"count"=按行数计数
  "stages": ["线索", "商机", "报价", "谈判", "成交"]  // 自上而下顺序；未列出的阶段值自动追加在末尾
}
```

**矩阵热力图 `heatmap` 配置**（任意两个维度列做行/列，颜色深浅 = 指标值，随筛选联动重算）：

```json
"heatmap": {
  "title": "城市 × 转化阶段 金额热力",
  "rowKey": "city",           // 行维度（标准 key：city/prov/stage/c/src/signer/gender...）
  "colKey": "stage",          // 列维度（同上）
  "measure": "a"              // "a"=按金额汇总；"count"=按行数计数
}
```

> 矩阵热力不依赖日期列，任意两个分类维度即可交叉（如 `city×stage`、`prov×月份`、`科目×来源`）；行/列数 ≤ 较多时不旋转标签，过多自动旋转避免重叠。

**桑基图 `sankey` 配置**（展示「源→目标」的流量分配，支持多级串联链路；数据需含源节点列与目标节点列，随筛选联动重算）。`ssrc`/`star` 为标准 key，由 anonymize 从中文列名（源节点/上游/父节点、目标节点/下游/子节点）自动归并，且**不进维度排行**——仅服务桑基图：

```json
"sankey": {
  "title": "招生渠道 → 转化路径 流向图",
  "sourceKey": "ssrc",          // 上游/来源节点（标准 key；中文列名如「源节点/上游/父节点」会被 anonymize 归并到 ssrc）
  "targetKey": "star",          // 下游/去向节点（标准 key；中文列名如「目标节点/下游/子节点」会被 anonymize 归并到 star）
  "measure": "a"                // "a"=按金额汇总；"count"=按行数计数
}
```

> 桑基图天然支持多级链路：每行是一条相邻节点的流（如 `渠道→试听`、`试听→科目`），节点可同时是某条的 target 与另一条的 source，自动串联成多级流向；中间节点入=出时即守恒图。源/目标列值非 PII，原样保留，不脱敏。

**多维对比雷达图 `radar` 配置**（同一组对象在多个维度上的能力/指标对比，如"各城市在 线索→成交 各阶段的金额""各校区在各科目上的营收"；复用现有标准 key 即可，**无需 anonymize 新增角色**）：

```json
"radar": {
  "title": "城市 × 阶段 转化能力雷达",
  "seriesKey": "city",          // 每条线一个分组值（标准 key：city/prov/signer/campus...）
  "axisKey": "stage",           // 雷达轴：每个取值一个轴（标准 key：stage/c/src/p...）
  "measure": "a",              // "a"=按金额汇总；"count"=按行数计数
  "seriesLabel": "城市",       // 可选：提示语里的分组名（默认"系列"）
  "axisLabel": "转化阶段"       // 可选：提示语里的轴名（默认"维度"）
}
```

> 雷达图要点：① 各轴**独立最大值归一化**（量纲/量级差大时不压扁小值系列，避免守恒对比失真）；② 系列超过 6 条时按聚合值取 top6，防线条堆叠；③ 随筛选联动重算；④ 颜色复用维度图配色，与漏斗/桑基一致。城市×阶段是最直观的"转化能力雷达"，换成 `signer×c`（签单人×科目）即"销售能力雷达"。

**目标达成率仪表盘 `gauge` 配置**（单指标 KPI 总览：当前合计 / 目标，达成率着色：≥100%绿、≥70%蓝、≥40%金、<40%红；随筛选联动重算）：

```json
"gauge": {
  "title": "销售目标达成率",
  "measure": "a",            // 汇总字段（默认 a=金额）
  "target": 800000,         // 目标值（必填，达成率=合计/目标）；不填则只显示合计
  "label": "累计销售额"       // 可选：提示语/量程下方文字
}
```

**层级占比树图 `treemap` 配置**（按多列层级嵌套，方块面积=金额，点击上层下钻；适合"渠道→科目""省→市→科目"等部分-整体拆解）：

```json
"treemap": {
  "title": "渠道 → 科目 营收树图",
  "keys": ["src", "c"],      // 层级顺序（标准 key 数组，1~N 级）；取值非 PII 原样保留
  "measure": "a"            // 汇总字段（默认 a）
}
```

**关系拓扑图 `topology` 配置**（力导向网络，节点=实体、连线=关系、节点大小=关联度数；复用源/目标列，直观呈现"谁连着谁"）：

```json
"topology": {
  "title": "渠道 → 阶段 关系拓扑",
  "sourceKey": "src",        // 源节点列（标准 key：src/ssrc/signer/city...）
  "targetKey": "stage",      // 目标节点列（标准 key：star/stage/c/prov...）
  "measure": "a"            // 连线权重（默认 a）
}
```

**转化留存矩阵 `cohort` 配置**（分组 × 阶段 矩阵，每行按该组峰值归一化为 0~100%，色深=该阶段占该组峰值的比；适合看"各渠道在各阶段的转化留存构成"）：

```json
"cohort": {
  "title": "渠道 × 阶段 转化留存矩阵",
  "groupKey": "src",         // 行分组（标准 key：src/c/signer/campus...）
  "stepKey": "stage",        // 列阶段（标准 key：stage/c/月份...）
  "measure": "a"            // 汇总字段（默认 a）
}
```

> 这 4 类图均复用现有标准 key，**无需 anonymize 新增角色**。gauge 需业务目标值（写死在 schema）；treemap/topology/cohort 全部可由 `keys`/`sourceKey`/`groupKey` 指向任意维度列组合，"配置即行业"。

**新增一个行业 = 在 `references/schema/` 放一个 `<industry>.json`**，生成时 `--industry <industry>` 即生效。现有示例（共 7 个）：`generic`（默认中性）、`sales`（销售/招生通用，金额漏斗）、`education`（教育培训：招生漏斗+课程+校区）、`retail`（零售：会员漏斗+商品+门店）、`clinic`（医疗诊所：就诊漏斗+科室+院区）、`logistics`（履约漏斗·仓网分布）、`b2b`（B2B制造：商机漏斗+产品+部门，无人物画像）。

自动渲染守卫：`funnel` 仅在 schema 配置了 `funnel` 且 `panels` 含 `funnel` 时渲染；`geo` 仅在数据含地区列时渲染；`gender`/`age` 仅在数据含性别/年龄列时渲染——所以一份配置可安全用于无此类列的数据。

## 看板功能

- 锁屏解密（进度条）
- 期间切换：全部 / 环比对比 / 各月
- **图表样式切换**：横向柱/竖向柱/面积/曲线
- KPI 四格（金额/笔数/客单价/数量，自动环比）
- 月度走势（柱=金额 + 线=笔数）
- 每个维度排行榜，**点柱条下钻筛选**，标签可逐个清除
- **真实地图**（数据含地区时）：**中国**=合规省界 + 金额颜色深浅 + 省→市→区钻取 + 面包屑返回；**世界**=数据含「国家」列时自动切换（217 国离线内嵌，中文名自动映射，点击国家联动筛选）；数据含「国家+省/州」时**点击国家地图下钻**（中国=省界地图、美国=州界地图，预置见 `assets/countries/`，未预置国家自动柱状排行兜底）；离线内嵌
- **双向联动**：点地图区域→其它面板筛该区域；切月份/标签→地图重算；**所有图表可点击筛选**（柱/饼/漏斗/热力/桑基/雷达/树图/拓扑/留存矩阵点击 → 写入筛选 → 全盘联动重算）
- **悬停提示**：全部图表支持鼠标悬停查看数值明细（移动端触摸同样可触发）
- **人物画像**（数据含性别/年龄时）：男女比例**厕所标识风格人形图标卡片**（男蓝/女粉 SVG 人形 + 金额 + 占比进度条，比环形图更直观）、年龄结构柱状图
- **转化漏斗**（schema 配置 `funnel` 时）：按阶段列聚合、金额/行数双口径、随筛选联动重算
- **矩阵热力图**（schema 配置 `heatmap` 时）：任意两维度交叉、颜色深浅=指标值、随筛选联动，视觉定位「高/低热区」
- **流向桑基图**（schema 配置 `sankey` 时）：源→目标流量分配、多级链路串联、带宽=流量、随筛选联动重算，直观呈现渠道/资金/用户路径的来龙去脉
- **多维对比雷达图**（schema 配置 `radar` 时）：每个分组对象一条闭合曲线、各维度为轴、各轴独立归一、top6 系列防堆叠，直观对比"谁在哪些维度强"，如各城市转化能力 / 各签单人科目结构 / 各校区营收分布
- **目标达成率仪表盘**（schema 配置 `gauge` 时）：单指标 KPI 总览，当前合计 vs 目标，达成率着色（≥100%绿/≥70%蓝/≥40%金/<40%红），随筛选联动重算
- **层级占比树图**（schema 配置 `treemap` 时）：按 `keys` 多列嵌套、方块面积=金额、随筛选联动，适合"渠道→科目""省→市→科目"部分-整体拆解
- **关系拓扑图**（schema 配置 `topology` 时）：力导向网络，节点=实体、连线=关系、节点大小=关联度，直观呈现"谁连着谁"，随筛选联动重算
- **转化留存矩阵**（schema 配置 `cohort` 时）：分组×阶段矩阵、每行按该组峰值归一化着色 0~100%，看各分组在阶段的转化留存构成，随筛选联动重算
- **分级权限**（`-p` + `--viewer-password` 时）：主密码=全量视图；访客密码=聚合视图（自动排除客户/老师/签单人等敏感字段，标题带「访客视图」徽标）
- 明细表：搜索/分页/横向滚动
- 右上角「锁定」按钮

## 交付方式

**本地**：HTML 发给对方，双击浏览器打开（内嵌图表库，断网可用）。
**网页**：放进独立目录重命名为 `index.html`，用 CloudStudio 部署拿分享链接。
```bash
mkdir -p dist && cp 看板.html dist/index.html   # 然后调用 cloudstudio 部署工具
```

## 输出规范（通用条款 · 所有行业适用）：缺失字段处理

生成**报告/文案/分析结论**（含看板中的文字叙述、表格说明）时，若数据字段缺失或无法获取（如性别、转化路径、年龄、签单人、城市等），必须遵守：

1. **正文不留白**：正文采用自然流畅的表述，**不得出现空白单元格、空占位符、空括号或未完成语句**；
2. **星号对应标注**：正文中相关位置用 `*` 标注，文末统一按字段列出补充说明（如 `* 性别：缺失 23 条（25%），未纳入统计`）；正文标记与文末条目一一对应；
3. **无法获取仅提示**：确实无法获取的字段，仅在文末简要提示原因，**不在正文强填或留白**；
4. **图表保持可读**：图表/看板中缺失维度统一显示为「未提供」（不得显示空白、NaN 或乱码）；
5. **适用性**：该条款对**所有行业**（销售、教育、医疗、零售、物流、外贸等）一律适用，不因行业 schema 不同而豁免。

## 安全边界

1. HTML 只存密码校验串，不存密码本身；密钥派生 12 万次迭代。
2. 这是"防偷看"级，非金融级；真正机密勿外发。
3. `mapping.json`（编号↔真名对照表）本地留存，绝不随看板发出——发出即脱敏失效。
4. 对外版脚注提示"请勿转发截图至外部渠道"。

## 更多文档

- `references/FAQ.md`：常见问题与故障排查（密码错误/地图无数据/文件太大/加密说明等 16 条）
- `references/THEMES.md`：10 套主题清单与新增主题方法
- `references/schema/example.json`：全功能 schema 示例（含全部可选面板）
- `docs/ARCHITECTURE.md`：架构设计
- `docs/PERFORMANCE.md`：大数据性能基线（10 万行）
- `CHANGELOG.md`：变更记录
- 无障碍审计：`python scripts/audit_accessibility.py`（主题对比度 WCAG 自检）
- 性能压测：`python scripts/benchmark.py [行数]`（默认 10 万）

## 回归测试

`test_all_industries.py` 内置多行业虚构数据，端到端跑「脱敏→生成加密看板」并校验：支付归并、脱敏、金额一致、HTML 无明文泄漏、锁屏标题中性、node 真解密。
```bash
cd C:/Users/jiang/.workbuddy/skills/viz-universal
python test_all_industries.py --keep
```
退出码 0 = 全通过。

## 技术实现

- 加密：`SHA256-KDF + SHA256-CTR`（file:// 兼容，纯 JS 解密）
- 渲染：Chart.js（基础图表：月度走势/维度排行/地区钻取/年龄）+ ECharts（真实地图 / 漏斗图 / 热力图 / 桑基图 / 雷达图 / 仪表盘 / 树图 / 拓扑图 / 留存矩阵，含以上任一类或地区时内嵌）
- 合规地图：DataV 中国边界 GeoJSON（含台湾/港澳/南海），离线、无 key

## 文件结构

```
viz-universal/
├── SKILL.md
├── test_all_industries.py
├── scripts/
│   ├── anonymize.py          脱敏与标准化
│   ├── build_dashboard.py    看板生成（读取 viz-schema）
│   └── crypto_util.py        加密核心
├── assets/
│   ├── template.html         看板模板（schema 驱动面板/标签）
│   ├── crypto.js             解密核心
│   ├── echarts.min.js        真实地图（按需内嵌）
│   ├── china_province.json   合规省级边界（中国地图）
│   ├── world_countries.json  世界地图（217 国，含国家列时自动启用）
│   ├── countries/            国家内州/省界（`<英文国家名>.json`，如 `United States.json` 50 州；数据命中即地图下钻）
│   └── vendor/chart.umd.min.js
└── references/
    ├── industry/             列语义预置（generic/education/retail/clinic/b2b）
    └── schema/               跨行业配置 ← 新增行业只改这里
        ├── generic.json      通用（默认中性）
        ├── sales.json        销售/招生通用（金额漏斗）
        ├── education.json    教育培训（招生漏斗+课程+校区）
        ├── retail.json       零售（会员漏斗+商品+门店）
        ├── clinic.json       医疗诊所（就诊漏斗+科室+院区）
        ├── logistics.json    物流（履约漏斗·仓网分布）
        └── b2b.json          B2B制造（商机漏斗+产品+部门，无人物画像）
```

## 路线（分期）

- **P0（当前）**：抽出 schema 引擎，sales 作为首个 schema 实例跑通，证明零代码适配。
- **P1**：可视化类型扩展 —— ✅ 漏斗图（funnel，08-11）；✅ 矩阵热力图（heatmap，08-12）；✅ 桑基图（sankey，08-12）；✅ 多维对比雷达图（radar，08-12）；✅ 仪表盘（gauge，08-12）；✅ 层级树图（treemap，08-12）；✅ 关系拓扑图（topology，08-12）；✅ 转化留存矩阵（cohort，08-12）。**P1 全部完成 ✅**
- **P2**：多源接入（API/DB/非结构化抽取）。
- **P3**：多形态输出（静态导出/可嵌入/实时看板）。
- **P4**：行业包 + 大数据性能 + 分级权限。

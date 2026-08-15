# viz-universal 架构

## 总览

```
┌────────────┐    ┌──────────────────────┐    ┌─────────────────────────────┐
│  数据输入   │ →  │  anonymize.py（脱敏） │ →  │  build_dashboard.py（生成） │
│ xlsx/csv/  │    │  列语义识别 + L0–L3   │    │  读取 viz-schema + 主题      │
│ json/stdin │    │  支付归并/科目重映射   │    │  加密(可选) + 内嵌图表库      │
└────────────┘    └──────────────────────┘    └─────────────┬───────────────┘
                                                           ↓
                                              ┌────────────────────────┐
                                              │  单文件 HTML 看板        │
                                              │  解密锁(可选) + 图表      │
                                              │  地图钻取 + 双向联动      │
                                              └────────────────────────┘
```

## 模块职责

| 模块 | 职责 |
|---|---|
| `scripts/anonymize.py` | 读取任意格式 → 列语义识别（COLUMN_HINTS）→ 行业预置（references/industry/*.json）→ 脱敏 L0–L3 → 输出标准 JSON（rows/dims/level/meta）|
| `scripts/build_dashboard.py` | 读标准 JSON + 声明式 schema（references/schema/*.json）→ 主题皮肤（scripts/themes.py）→ 可选加密（scripts/crypto_util.py）→ 模板渲染（assets/template.html）→ 单文件 HTML |
| `scripts/themes.py` | 10 套视觉主题 token（背景/文字/卡片/渐变/图表调色板/地图色阶/男女图标色），`--theme` 注入 CSS 变量 + `window.THEME` |
| `scripts/crypto_util.py` | SHA256-KDF（12 万次迭代）+ SHA256-CTR 流加密；纯 JS 可解密，兼容 `file://` |
| `scripts/errors.py` | 统一退出码（0/1/2/3）与中文提示前缀 |
| `assets/template.html` | 看板模板：锁屏/期间切换/图表样式切换/KPI/走势/排行/地图钻取/人物画像/明细表；`__PAYLOAD__` 等占位符由生成器替换 |
| `assets/china_province.json` | 合规省级边界（DataV，离线）；市/县边界生成时按需联网拉取并内嵌 |
| `references/industry/*.json` | 行业列语义预置（generic/education/retail/clinic/b2b）|
| `references/schema/*.json` | 声明式行业配置（面板显隐/顺序/标签/漏斗/热力/桑基/雷达/仪表盘/树图/拓扑/留存/安全）|

## 关键设计

### 1. 配置即行业（schema 驱动）
行业差异全部沉淀为 `references/schema/<industry>.json`，引擎代码零改动。`panels` 数组控制面板显隐与顺序；`funnel/heatmap/sankey/radar/gauge/treemap/topology/cohort` 键提供对应图的维度映射；渲染端有自动守卫（无地区列不渲染地图、无性别列不渲染人物画像）。

### 2. 脱敏与加密分层
- 脱敏：L0 原样 / L1 姓名掩码 / L2 客户编号化（默认）/ L3 编号+代号+金额缩放+日期偏移；mapping 对照表本地隔离。
- 加密：HTML 内只存密码校验串（verify）与密文，密钥不落盘；12 万次迭代派生防暴力破解。**"防偷看"级，非金融级。**

### 3. 单文件离线
图表库（Chart.js/ECharts）与地图 GeoJSON 内嵌进 HTML，双击即开、断网可用；`--cdn` 可选走 CDN 减小体积。

### 4. 主题即皮肤
主题只覆盖"皮肤"（CSS 变量 + `window.THEME` 常量），图表/数据逻辑零改动；新增主题只需在 `themes.py` 的 `THEMES` 字典加一项。

## 数据流（一次生成）

```
文件 → read_any → build() 脱敏 → {rows,dims,level,meta}
                                          ↓
                    build_dashboard: load_schema() → build_geo()(可选) → payload
                                          ↓
                    加密(可选) → template.html 占位符替换 → 单文件 HTML
```

## 回归验证

`test_all_industries.py`：7 行业虚构数据端到端跑「脱敏→加密→生成」并校验支付归并/脱敏生效/金额一致/HTML 无明文泄漏/锁屏中性/node 真解密（对错密码分别验证）。

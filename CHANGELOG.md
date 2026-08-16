# 变更记录（Changelog）

本项目遵循语义化版本；重大功能与修复在此记录。

## [0.8.0] - 2026-08-16 — 智能经营分析报告 + 新手引导（P0 差异化）

### 新增
- **智能经营分析报告**（`--report <path>`，规则引擎离线可用）：自动生成「经营分析报告」——
  总体概览（总额/笔数/客单价/环比）、月度走势（含趋势判断）、构成分析（各维度 Top3 占比）、
  地区分布、风险提示、行动建议（环比驱动/头部集中度风险/缺失提示）；缺失字段遵循输出规范（正文*标注+文末补充）。
- **新手引导**：看板右上角「❓ 帮助」→ 使用说明弹层（点击联动/地图钻取/主题切换/图表样式/导出/安全/离线 7 条）。
- 回归 90/90 全过。

## [0.7.3] - 2026-08-16 — 缺失字段输出规范（通用条款）

### 新增
- **输出规范（通用条款 · 所有行业适用）**：生成报告/文案时缺失字段（性别、转化路径、年龄等）处理——
  1) 正文不留白（无空单元格/空占位符/空括号）；2) 正文 `*` 标注 + 文末按字段补充说明一一对应；
  3) 无法获取字段仅文末提示；4) 图表缺失维度显示「未提供」；5) 所有行业一律适用。
- **占位符优化**：'未填写' → '未提供'（更自然可读，图表不留空白/NaN）。
- 回归 90/90 全过。

## [0.7.2] - 2026-08-16 — 世界地图内中国三级钻取 + 边界按需挂载

### 新增
- **世界地图内中国 省→市→区 三级地图钻取**：点中国 → 35 省地图 → 点省 → 该省市级地图（生成时联网拉取 DataV 合规市界内嵌）→ 点市 → 全盘联动；数据含「区/县」列自动继续下钻区级。
- **州/省界按需挂载**：仅对"数据中真实出现省/州值"的国家加载州界（未提供省份数据的国家保持国家级联动）——包更小、部署更快。
- **修复**：anonymize 缺失省份占位符'未填写'曾导致每个国家都误挂州界（18MB），现视为缺失。
- **中文检索**：description 明确中文名「跨行业通用可视化（数据看板生成器）」+ 触发词扩充（数据大屏/销售看板/收入分析/BI…）。
- 回归 90/90 全过。

## [0.7.1] - 2026-08-16 — 主题切换修复 + 图表样式按钮完善

### 修复
- **主题下拉切换真正生效**：根因 `<style>` 用 `display:none` 不能禁用 CSS 规则（标准行为），10 套主题规则同时生效互相覆盖；改用 `disabled` 属性（build 时非激活主题默认 `disabled`，前端切换 `el.disabled`）。
- **面积图真正填充**：Chart.js line 默认 `fill:false`，area 模式此前与折线几乎无差异；加 `fill:true` 后切"面积"显示金色填充区。
- **chartTypeBtns 默认显示**：4 个图表样式按钮不再隐藏；副标/悬停提示标明作用域（横向/柱状=维度排行，面积/曲线=月度走势+排行）。

## [0.7.0] - 2026-08-16 — 运行时主题下拉切换

### 新增
- **顶部「主题」下拉菜单**：生成时注入全部 10 套主题（CSS + 数据），用户打开看板即可下拉切换视觉主题并**实时预览**（切换 → 全盘重绘，图表/地图同步换肤）。
  - 10 套：Apple 液态玻璃 / Stripe 科技渐变 / Vercel 极简纯黑 / Linear 深紫靛蓝 / Bloomberg 终端 / Notion 暖白编辑 / Neubrutalism 撞色 / Tokyo Night / Nordic MUJI / Cyberpunk 霓虹
  - 选择记入 `localStorage`，下次打开自动恢复
  - 未指定 `--theme` 时默认 apple-glass，外观与之前一致
- 实现：`themes.py` 新增 `theme_data/all_themes_html/all_themes_js`；`build_dashboard.py` 注入全部主题；`template.html` 新增 `initThemeSel/switchTheme`。
- 回归 90/90 全过。

## [0.6.0] - 2026-08-15 — 国家州/省界按需自动下载

### 新增
- **"有数据就加载、没有就降级"** — 完善世界地图下钻：
  - 缓存优先：`assets/countries/<英文国家名>.json` 存在即用
  - 自动联网：`fetch_sub_geo()` 通过 **geoBoundaries API**（gbOpen/CC-BY 0）按数据中的国家自动下载 ADM1 简化版 GeoJSON，剥行政区后缀（Prefecture/State/Province/Oblast/...）让短名与数据匹配，保留 `_fullName` 用于 tooltip 显示全称
  - 内置 ~80 国 ISO3 映射（中日美英德法韩印俄等）
  - 失败提示：生成时 main() 输出"⚠ 以下国家未加载 + 从 https://www.geoboundaries.org/ 下载并放入 assets/countries/<英文国家名>.json"
  - 已成功自动加载示例：United States（50 州，folium 源）、Japan（47 县，geoBoundaries）、Singapore（5 区）、Germany（16 州）等
- 演示看板更新：world + 中国 + 美国（地图下钻）+ 日本/新加坡（临时柱状兜底）
- 回归 90/90 全过

## [0.5.0] - 2026-08-15 — 国家内地图下钻（州/省界）

### 新增
- **国家内下钻升级为地图**：数据含「国家+省/州」时，点击国家直接渲染**该国州/省界地图**（不再只是柱状排行）：
  - 预置离线州/省界：`assets/countries/` 目录，文件名=国家英文名（如 `United States.json` 50 州，folium 官方源）；**中国**复用合规省界（35 省）；
  - 生成时自动按数据中的国家挂载对应州界（`geoJSONs[国家英文名]`），前端 `geoGoto` 按 nameMap 英文名查地图；
  - 未预置州界的国家（如日本/新加坡）保持柱状排行兜底；新增国家只需在 `assets/countries/` 放 `<英文名>.json` 一个文件。
- 回归世界用例：新增「美国州界已挂载(地图下钻)」，**90/90 全过**。

## [0.4.0] - 2026-08-15 — 世界地图向下钻取

### 新增
- **世界地图下钻**：数据含「国家 + 省/州」两列时，点击国家可向下钻取：
  - **中国** → 离线省界地图（复用 china_province.json，35 省着色，面包屑「全球 › 中国」）；
  - **其它国家** → 无离线省界时自动降级为「省/州柱状排行」，点击柱条 = 筛选「国家+省」并全盘联动；
  - 国家名经 `nameMap`（中文→英文）匹配世界地图着色，树/钻取/筛选保留数据原值，多级链路自洽。
- 回归世界用例升级至 9 个（含 regionKeys=[country,prov]、中国省界挂载、国家内省份保留），**89/89 全过**。

## [0.3.0] - 2026-08-15 — 世界地图

### 新增
- **世界地图**：数据含「国家/国别/country」列时自动切换世界地图（不再局限中国）。
  - 离线内嵌 217 国 GeoJSON（ECharts 官方源，合规：不含台湾/港澳为独立国家，作为中国整体渲染）；
  - 中文国家名自动映射英文（`references/country_map.json` 145 条常用映射，映射值均校验存在于世界地图）；
  - 世界模式：点击国家 = 筛选该国家并全盘联动；面包屑根显示「全球」；无 adcode 层级。
  - 中国模式完全不受影响（regionKeys 首列 prov 走原逻辑，省→市→区钻取保留）。
- 回归新增 7 个世界地图用例（regionKeys 检测/世界标志/GeoJSON 内嵌/中文名映射/金额一致），**87/87 全过**。

## [0.2.2] - 2026-08-15 — P2 分级权限

### 新增
- **分级权限（双密码）**：`build_dashboard.py` 新增 `--viewer-password`（访客密码）与 `--viewer-fields`（默认排除 `n,teacher,signer`）。
  - 主密码（`-p`）→ 全量视图（含明细/签单人/老师）；
  - 访客密码 → 聚合视图：自动排除敏感字段（行级删字段 + dims 同步过滤），页面标题显示「访客视图 · 部分数据」徽标；
  - 前端 `doUnlock` 依次尝试两个密码，错密码统一拦截。
- 验证：双 payload 解密差异（主含 n/signer/teacher、访客仅聚合字段）、错密码拦截、内联 JS `node --check`、回归 68/68。

## [0.2.1] - 2026-08-15 — 免密默认 + 全图联动 + 多源接入

### 变更
- **默认免密直开**：`build_dashboard.py` 不再强制要求密码，不传 `-p` 即免密直开（数据仍脱敏）；`-p 密码` 变为可选加密接口，随时可补（用同一份脱敏 JSON 重跑加 `-p` 即可）。SKILL.md 流程第 0 步/参数表、FAQ Q4 已同步。

### 新增
- **全图点击联动**：除已有的维度排行/地图联动外，漏斗、热力、桑基（节点）、雷达（系列）、树图、拓扑（节点）、留存矩阵（分组）均可点击 → 写入筛选 → 全盘重算（render 末尾 `bindChartClicks()`，先 off 再 on 防重复绑定）。
- **多源接入（P2 部分）**：anonymize.py 支持 SQLite（`.db/.sqlite/.sqlite3`，`--sheet` 可指定表名）与 http(s) URL（自动识别 JSON/CSV），加 xlsx/csv/json/stdin 共 6 种输入。
- **手机端适配**：新增 `@media(max-width:700px)`（单列、图表高度 220px、触屏友好按钮、明细表横向滚动、锁屏窄版）。

### 说明
- 悬停数据提示：全部图表已有 tooltip（Chart.js 默认 + 9 个 ECharts 图逐一配置），无需新增。
- 分级权限（按密码等级显示字段）依赖密码体系，密码接口就绪后实施；上架市场需发布后操作，均顺延至下一迭代。

## [0.2.0] - 2026-08-15 — P1 能力增强

### 新增
- `--wizard` 交互向导：anonymize.py 与 build_dashboard.py 均支持逐项问答生成参数（仅交互终端，管道/CI 自动跳过，被中断时优雅退出 exit 1）。
- `--sample N` 随机采样：大数据演示模式，固定种子可复现（两脚本均支持）。
- 导出能力：看板头部新增「⬇ 导出 PNG」按钮（遍历 Chart.js/ECharts 全部实例逐个下载）；`@media print` 打印友好样式（隐藏按钮/锁屏，图表保色）。
- 无障碍：新增 `scripts/audit_accessibility.py`（WCAG 对比度审计，正文/次要 ≥4.5、坐标轴 ≥3.0，支持渐变背景解析）；修正 4 套主题 5 处不达标色（notion/tokyo-night/nordic/cyberpunk），现 30/30 达标；看板图表容器自动补 `role="img"` + `aria-label`。
- schema 校验器：`build_dashboard.py` 生成前校验 panels 白名单与各图配置必填字段，坏配置打印明细并 exit 2。
- 性能基线：`scripts/benchmark.py` 一键压测（10 万行基线：脱敏 26.4s / 免密生成 14.9s / 加密生成 30.8s），产出 `docs/PERFORMANCE.md`。

## [0.1.0] - 2026-08-15 — P0 工程化（发布就绪）

### 新增
- 开源发布就绪包：`LICENSE`(MIT)、`README.md`、`.gitignore`、`.github/workflows/ci.yml`（3 个 Python 版本矩阵跑回归 + stdin 冒烟）、`pyproject.toml`（可 `pip install -e .`，提供 `viz-anonymize` / `viz-build` 命令）。
- `scripts/errors.py`：统一退出码约定（0 成功 / 1 输入错误 / 2 配置环境错误 / 3 运行时错误）与中文提示前缀 `[错误]/[警告]/[信息]`。
- stdin 管道输入：`anonymize.py` 与 `build_dashboard.py` 均支持 `-i -`。
- 跨平台化：`test_all_industries.py` 的 node 探测改为 env → PATH → 常见路径；SKILL.md 命令示例支持 `PYTHON` / `VIZ_UNIVERSAL_HOME` 环境变量覆盖。
- 文档：`references/FAQ.md`（16 条常见问题与排查）、`references/schema/example.json`（全功能 schema 示例）、`docs/ARCHITECTURE.md`（架构图）、`CHANGELOG.md`。

### 修复
- 资源缺失时给出明确中文错误而非裸 traceback（build_dashboard.py 生成前检查模板/加密库/图表库）。

## [0.1.0-alpha] - 2026-08-11 ~ 08-14 — 功能演进

- 08-14 主题系统：`scripts/themes.py` 内置 10 套主题（apple-glass/stripe/vercel/linear/bloomberg/notion/neubrutalism/tokyo-night/nordic/cyberpunk），`--theme` 切换；修复深色主题地图色阶低端过暗致省份"隐身"（亮度差>40）；修复地图 GEOJSON 内联残留 `{}` 致整页脚本解析失败；过滤南海诸岛无名要素（营收热力图只画省级单元）。
- 08-12 图表扩展：桑基（sankey）/ 雷达（radar）/ 仪表盘（gauge）/ 树图（treemap）/ 拓扑（topology）/ 留存矩阵（cohort）。
- 08-11 schema 引擎：声明式 viz-schema 跨行业适配，7 行业包（generic/sales/education/retail/clinic/logistics/b2b）。
- 08-10 前身 sales-viz-secure：脱敏 L0–L3、SHA256-KDF+CTR 加密（12 万次迭代）、合规中国地图（省→市→区钻取）、双向联动、人物画像。

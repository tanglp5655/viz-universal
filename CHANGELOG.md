# 变更记录（Changelog）

本项目遵循语义化版本；重大功能与修复在此记录。

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

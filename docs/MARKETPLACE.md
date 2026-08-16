# 上架 & 变现材料（SkillHub / SkillPay）

> 用途：复制下面内容到 SkillHub「发布 skill」表单 / SkillPay「封装 Pay Skill」配置页。
> 技术名 `viz-universal` 已与仓库 SKILL.md 一致，无需改。

---

## 一、基础信息（表单字段）

| 字段 | 内容 |
| --- | --- |
| 显示名 | 跨行业通用可视化（数据看板生成器） |
| 技术名 | viz-universal |
| 分类 | 数据 / 分析（Data & Analytics） |
| 标签 | 数据可视化, 看板, 图表, 中国地图, 报表, 脱敏, 加密, dashboard, ECharts, BI |
| 一句话简介 | 把 Excel/CSV/JSON/SQLite/URL 明细数据一键变成「脱敏 + 可选加密」的单文件交互看板：13+ 图表、真实中国地图钻取、全图点击联动、手机端可用。 |

---

## 二、技能介绍（详细描述，支持图文）

只需一份明细数据（销售、运营、物流、医疗、教育等任意行业），即可生成一个**单文件 HTML 看板**：脱敏、可加密（默认免密直开）、完全离线，手机/电脑浏览器双击即开，无需部署。

**核心能力**
- **13+ 图表类型**：KPI / 月度走势 / 维度排行 / 转化漏斗 / 矩阵热力 / 流向桑基 / 多维雷达 / 目标仪表盘 / 层级树图 / 关系拓扑 / 留存矩阵 / 人物画像 / 明细表
- **真实中国地图**：合规边界（DataV GeoJSON，离线无 key）+ 金额颜色深浅 + 省→市→区逐级钻取 + 双向联动
- **全图点击联动**：点任意图表（柱/地图/漏斗/桑基/雷达/热力/树图/拓扑/留存）→ 全盘筛选重算；悬停显示数值
- **脱敏分级**：L0–L3（原样 / 姓名掩码 / 编号化 / 编号+代号+金额缩放），`mapping` 对照表本地隔离
- **加密（可选）**：SHA256-KDF（12 万次迭代）+ CTR 流加密，`file://` 双击即用；**分级权限**：主密码=全量、访客密码=聚合视图
- **多源接入**：Excel / CSV / JSON / SQLite / URL / stdin 六种输入
- **声明式 schema**：行业差异 = 一个 JSON，7 个行业开箱即用（generic/sales/education/retail/clinic/logistics/b2b），新增行业零改引擎
- **10 套视觉主题**：apple-glass / stripe / vercel / linear / bloomberg / notion / neubrutalism / tokyo-night / nordic / cyberpunk
- **导出与打印**：一键导出全部图表 PNG；打印友好样式
- **手机端适配**：单列布局、触屏友好、明细表横向滑动

**适用场景**
- 运营/销售/财务把月度数据做成给老板看的管理看板
- 教育机构招生、零售门店、医疗诊所、B2B 商机的行业分析
- 需要"脱敏后可对外分享"的案例、汇报、投标演示

**质量保证**
- 自动化回归 80/80 全过（7 行业端到端：脱敏→加密→node 真解密→明文泄漏检查→分级权限）
- 主题对比度无障碍审计 30/30 达标（WCAG AA）
- 大数据压测基线：10 万行 脱敏 26s / 生成 15-31s
- 已脱敏：输出默认不含真名/敏感字段（客户编号化、人员化名）
- MIT 许可，可自由使用

---

## 三、英文介绍（如市场要求双语）

**Display name**: 跨行业通用可视化（数据看板生成器） — Cross-industry Data Dashboard Generator (viz-universal)
**Category**: Data & Analytics
**Tags**: data-viz, dashboard, charts, china-map, report, anonymize, encrypt, ECharts, BI

**One-liner**: Turn any Excel/CSV/JSON/SQLite detail data into a single-file interactive HTML dashboard with 13+ chart types, real China map drill-down, cross-chart linking, masking and optional encryption — works offline on mobile & desktop.

**Key features**
- 13+ chart types (KPI, funnel, heatmap, sankey, radar, gauge, treemap, topology, cohort, gender, age, table)
- Real China map (compliant DataV GeoJSON, offline, province→city→district drill-down, bi-directional linking)
- Click-any-chart cross-filtering + hover tooltips
- Data masking L0–L3 with isolated mapping table
- Optional encryption (SHA256-KDF 120k iterations, pure-JS decrypt, file:// compatible); graded access (owner password = full view, viewer password = aggregated view)
- Multi-source input: xlsx / csv / json / sqlite / url / stdin
- Declarative schema: 7 industries out-of-box, zero-code adaptation
- 10 visual themes, PNG export & print-friendly, mobile responsive
- 80/80 regression tests, WCAG AA contrast audit, MIT license

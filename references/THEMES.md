# 看板视觉主题库（Themes）

viz-universal 内置一套可选视觉主题，生成任意看板时通过 `--theme <id>` 指定，
让用户自行挑选「看板长什么样」，无需改动图表逻辑。

## 可用主题（id / 中文名 / 气质）

| id | 中文名 | 模式 | 气质 |
|---|---|---|---|
| apple-glass | Apple 液态玻璃 | dark | 极深底 · 多层霓虹光晕 · 清玻璃卡 |
| stripe | Stripe 科技渐变 | dark | 深蓝底 · 蓝紫青渐变 · 玻璃拟态 |
| vercel | Vercel 极简纯黑 | dark | 纯黑底 · 发丝边框 · 零渐变 · 极致克制 |
| linear | Linear 深紫靛蓝 | dark | 深靛底 · 细线条 · 产品感强 |
| bloomberg | Bloomberg 终端 | dark | 黑底 · 琥珀/绿 · 等宽数据 |
| notion | Notion 暖白编辑 | light | 暖白纸 · 衬线标题 · 干净 |
| neubrutalism | Neubrutalism 撞色 | light | 粗硬描边 · 撞色块 · 活泼 |
| tokyo-night | Tokyo Night | dark | 雾紫蓝粉 · IDE 配色 |
| nordic | Nordic / MUJI | light | 米白 · 大地色 · 大量留白 |
| cyberpunk | Cyberpunk 霓虹 | dark | 黑底 · 青/品红 · 网格光 |

查看完整清单：
```
python scripts/build_dashboard.py --list-themes
python build_multimonth.py --list-themes
```

## 实现位置与用法

- 主题定义： `scripts/themes.py` 的 `THEMES` 字典（每个主题含 bg/text/surface/border/
  radius/blur/shadow/grad/accent/palette/mcolor/mapVisualMap/mapArea/genderM/F/grid/axis/tooltipBg）。
- 展开函数： `expand(tid)` → 输出 `:root{...}` CSS 变量 + `const THEME={...}` JS 常量；
  `override_css(tid)` → 给通用模板用的 `!important` chrome 覆盖；`window_js(tid)` → `window.THEME`。

### 月度对比看板（build_multimonth.py，全量主题驱动）
```
python build_multimonth.py                       # 默认 apple-glass
python build_multimonth.py --theme vercel        # 换肤
python build_multimonth.py --theme notion        # 浅色
```
模板用 `var(--bg)` 等 CSS 变量 + `THEME` JS 常量，所有图表（含地图/男女）自动套用主题色。

### 通用加密看板（build_dashboard.py，chrome + 图表调色板）
```
python build_dashboard.py -i 数据.json -o 看板.html --no-lock --theme tokyo-night
```
注入 `theme-override` 样式覆盖页面 chrome，并暴露 `window.THEME` 供维度图/趋势图取色
（`template.html` 的 `COLORS` 已回退到 `window.THEME.palette`）。不传 `--theme` 时保持原深蓝默认风。

## 新增主题
在 `scripts/themes.py` 的 `THEMES` 字典中追加一项即可，字段见文件头注释；
无需改动任何生成器或模板。

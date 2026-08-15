# viz-universal 常见问题（FAQ）

## 安装 / 环境

**Q1：报 `ModuleNotFoundError: openpyxl`？**
Excel 读取依赖 openpyxl：`pip install openpyxl`。只读 CSV/JSON 不需要。

**Q2：`import errors` / `import themes` 失败？**
scripts 目录内的模块互相引用。请始终通过 `scripts/anonymize.py`、`scripts/build_dashboard.py` 的绝对路径调用（脚本会自动把自身目录加入 sys.path），不要单独复制脚本文件出来。

**Q3：旧版 Excel（.xls）读不了？**
只支持 `.xlsx/.xlsm`。老 `.xls` 请先在 Excel/WPS 里另存为 .xlsx，或用 pandas 转换。

## 看板生成

**Q4：打开看板提示"密码错误"，但我确定密码没错？**
- 默认生成是**免密直开**（不传 `-p` 时无需密码）；
- 只有用 `-p 密码` 生成过的看板才需要输入密码；请确认该文件是否加密版本、密码是否与生成时完全一致（大小写/空格）；
- 若重新生成过且换了 `--iter`，旧文件用旧迭代次数，需重新生成。
- 想给已生成的免密看板补密码：用同一份脱敏 JSON 重新跑一次生成命令加 `-p` 即可。

**Q5：生成很慢？**
12 万次密钥迭代是刻意的（防暴力破解），首次生成 1~3 秒属正常。内部联调可用 `--iter 1000` 加速，对外发布请保持默认。

**Q6：文件太大？**
默认内嵌图表库（Chart.js ~200KB + ECharts ~1MB）+ 地图 GeoJSON。可选：`--cdn` 让图表库走 CDN（体积小但需联网）；数据量大时先在上游筛选/汇总。

**Q7：HTML 打开只有标题、图表全空？**
几乎都是内联脚本语法错误或浏览器缓存：
1. 强制刷新（Ctrl+F5）排除缓存；
2. 重新运行生成命令（确保是最新生成器）；
3. 若仍复现，检查生成日志是否有 `[错误]`，把报错贴给维护者。
> 历史教训：模板占位符若自带 `{}` 而替换串不含它，会在 JSON 后残留 `{}` 导致整页 JS 解析失败（`const GEOJSON={...}{};`）。生成器已修复此问题。

## 地图

**Q8：地图省份不显示颜色/像"没数据"？**
两个已知坑：
1. **省名对齐**：数据里的 `region/prov` 必须是 GeoJSON 全称（如 `山东省` 而非 `山东`），或用 `PROV_FIX` 简称映射兜底；
2. **深色主题色阶**：地图 visualMap 色阶最低端亮度必须高于背景（亮度差建议 >40），否则低值省份在深底上隐身。两处已在生成器/主题库内建修复。

**Q9：地图下方有块孤形/像个小岛？**
那是**南海诸岛**（中国领土，但不在 34 个省级营收统计单元内、无营收数据）。营收热力图默认只画有数据的省级单元（BI 通用做法），生成器会自动过滤该无名要素，不影响 34 省着色。

**Q10：地图钻取显示"该层级降级为列表"？**
生成时需联网拉取市/县边界（DataV），无网时自动降级为列表。联网重跑即可。

## 脱敏 / 安全

**Q17：怎么让"老板看全量、别人看汇总"？**
用分级权限：生成时同时给主密码和访客密码
```bash
python scripts/build_dashboard.py -i data_masked.json -o 看板.html -p 老板密码 --viewer-password 访客密码
```
老板用 `-p` 的密码打开=全量视图（含明细/签单人/老师）；访客用 `--viewer-password` 的密码打开=聚合视图（自动排除 `n/teacher/signer`，可用 `--viewer-fields` 调整），标题带「访客视图」徽标。

**Q11：`mapping.json` 是什么？会外发吗？**
编号↔真名的对照表，**本地留存、绝不随看板外发**——发出即脱敏失效。删除后无法还原真名。

**Q12：加密是金融级吗？**
不是。这是"防偷看"级（12 万次迭代 SHA256 派生），防止拿到 HTML 的人直接看源码。真正机密数据请勿外发。

**Q13：为什么 L3 金额会变？**
L3 支持 `--scale` 金额缩放与 `--date-shift` 日期偏移，用于对外案例分享，刻意与真实值不完全一致。

## 主题 / 扩展

**Q14：`--theme xxx` 没反应？**
先 `build_dashboard.py --list-themes` 确认 id（apple-glass/stripe/vercel/linear/bloomberg/notion/neubrutalism/tokyo-night/nordic/cyberpunk），注意拼写。

**Q15：新增一个行业要改代码吗？**
不用。在 `references/schema/` 放一个 `<industry>.json`（参考 `example.json`），生成时 `--industry <industry>` 即生效。

## 部署

**Q16：怎么给同事/客户看？**
- 本地：HTML 直接发，双击浏览器打开（离线可用）；
- 网页：文件重命名为 `index.html` 放独立目录，用 CloudStudio 部署拿分享链接。

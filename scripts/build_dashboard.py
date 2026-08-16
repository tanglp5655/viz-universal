# -*- coding: utf-8 -*-
"""
sales-viz-secure · 加密看板生成器

把脱敏后的标准 JSON 打包成一个「单文件 + 密码加密」的 HTML 看板。
手机 / 电脑浏览器均可打开，可双击本地运行，也可上传到任意静态托管。

用法:
  python build_dashboard.py -i data_masked.json -o 看板.html -p 你的密码 --title "2026年5-8月销售分析"
  python build_dashboard.py -i data_masked.json -o 看板.html --no-lock --title "2026年5-8月销售分析"

参数:
  -i/--input     脱敏脚本产出的 JSON（也接受纯记录数组）
  -o/--output    输出 HTML
  -p/--password  【可选】访问密码；不传默认免密直开（数据仍为脱敏内容）
  --no-lock      强制免密直开（与 -p 同时给时按免密处理）
  --title        看板标题
  --subtitle     副标题
  --lock-title   锁屏标题（默认"数据看板"，不要写公司名）
  --filter-dim   顶部快捷筛选用的维度 key，默认第一个维度
  --qty-label    数量字段显示名（如"课次""件数"）
  --amount-label 金额字段显示名（默认"金额"）
  --default-chart 维度图默认样式：barv竖柱/barh横柱/area面积/line曲线，默认 barh
  --cdn          图表库走 CDN（体积小 30KB，但需联网）；默认内嵌离线
  --iter         密钥派生迭代次数，默认 120000（越大越慢越安全）
  --schema       声明式 viz-schema JSON（跨行业配置：面板显隐/顺序/标签/主题/安全）
  --industry     行业标识，自动加载 references/schema/<industry>.json，默认 generic
"""
import argparse
import json
import os
import sys
from datetime import datetime
import urllib.request
import ssl
import re
import io, zipfile
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from crypto_util import encrypt_text, DEFAULT_ITERATIONS  # noqa: E402
from errors import EXIT_OK, EXIT_USAGE, EXIT_CONFIG, EXIT_RUNTIME, err, warn, info  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    sys.path.insert(0, os.path.join(BASE, 'scripts'))
    from themes import (THEMES, list_themes, override_css, window_js,
                        all_themes_html, all_themes_js, DEFAULT_THEME as _DEF_THEME)
except Exception:
    THEMES = None
TPL = os.path.join(BASE, 'assets', 'template.html')
CRYPTO = os.path.join(BASE, 'assets', 'crypto.js')
CHARTJS = os.path.join(BASE, 'assets', 'vendor', 'chart.umd.min.js')
CDN_TAG = "document.write('<scr'+'ipt src=\"https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js\"></scr'+'ipt>');"
SCHEMA_DIR = os.path.join(BASE, 'references', 'schema')


def load_schema(args):
    """加载声明式 viz-schema：优先 --schema 指定文件，否则按 --industry 自动匹配，
    再回退到 generic。这是跨行业通用化的核心——行业差异全部沉淀为配置文件。"""
    if getattr(args, 'schema', None) and os.path.exists(args.schema):
        with open(args.schema, encoding='utf-8') as f:
            return json.load(f)
    ind = getattr(args, 'industry', None) or 'generic'
    cand = os.path.join(SCHEMA_DIR, ind + '.json')
    if os.path.exists(cand):
        with open(cand, encoding='utf-8') as f:
            return json.load(f)
    gen = os.path.join(SCHEMA_DIR, 'generic.json')
    if os.path.exists(gen):
        with open(gen, encoding='utf-8') as f:
            return json.load(f)
    return {}


# ---------- viz-schema 校验（P1：坏配置快速报错，而非渲染期才崩） ----------
PANEL_WHITELIST = {'gauge', 'funnel', 'heatmap', 'sankey', 'radar', 'treemap',
                   'topology', 'cohort', 'geo', 'gender', 'age', 'table'}
CONFIG_KEYS = ('funnel', 'heatmap', 'sankey', 'radar', 'gauge', 'treemap', 'topology', 'cohort')
REQUIRED_FIELDS = {
    'funnel': ('stageKey', 'stages'),
    'heatmap': ('rowKey', 'colKey'),
    'sankey': ('sourceKey', 'targetKey'),
    'radar': ('seriesKey', 'axisKey'),
    'treemap': ('keys',),
    'topology': ('sourceKey', 'targetKey'),
    'cohort': ('groupKey', 'stepKey'),
}


def validate_schema(schema):
    """校验 viz-schema 结构；返回错误列表（空 = 合法）。"""
    errs = []
    if not isinstance(schema, dict):
        return ['schema 必须是 JSON 对象']
    panels = schema.get('panels')
    if panels is not None:
        if not isinstance(panels, list):
            errs.append('panels 必须是数组（当前 %s）' % type(panels).__name__)
        else:
            for p in panels:
                if p not in PANEL_WHITELIST:
                    errs.append('panels 含未知面板 %r（可选：%s）'
                                % (p, '、'.join(sorted(PANEL_WHITELIST))))
    for k in CONFIG_KEYS:
        cfg = schema.get(k)
        if cfg is None:
            continue
        if not isinstance(cfg, dict):
            errs.append('%s 配置必须是对象（当前 %s）' % (k, type(cfg).__name__))
            continue
        for f in REQUIRED_FIELDS.get(k, ()):
            v = cfg.get(f)
            if v in (None, '', []):
                errs.append('%s.%s 必填（参考 references/schema/example.json）' % (k, f))
        if cfg.get('measure') not in (None, 'a', 'count'):
            errs.append('%s.measure 只能是 "a" 或 "count"' % k)
        if k == 'gauge' and cfg.get('target') is not None and not isinstance(cfg.get('target'), (int, float)):
            errs.append('gauge.target 必须是数值')
    return errs


LABEL_OF = {'c': '科目/产品', 'src': '来源', 'signer': '签单人',
            'teacher': '服务人员', 'p': '支付方式', 'campus': '校区'}


_SUB_GEO_FAILS = []   # 收集加载失败的国家，便于 main() 汇总提示用户手动补

def fetch_sub_geo(en, iso3=None):
    """按需加载国家内州/省/县地图：缓存优先→geoBoundaries API。受限网络下 API 不可达则失败。"""
    cache = os.path.join(COUNTRY_SUB_DIR, en + '.json')
    if os.path.exists(cache):
        try:
            with open(cache, encoding='utf-8') as f: return json.load(f)
        except Exception: pass
    iso3 = iso3 or EN_ISO3.get(en)
    if not iso3:
        _SUB_GEO_FAILS.append((en, 'ISO3 缺失'))
        return None
    try:
        api_url = GB_API.format(ISO3=iso3)
        req = urllib.request.Request(api_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as r:
            meta = json.loads(r.read().decode('utf-8'))
    except Exception:
        _SUB_GEO_FAILS.append((en, 'API/网络不可达'))
        return None
    for url_key in ('simplifiedGeometryGeoJSON','gjDownloadURL','staticDownloadLink'):
        geo_url = meta.get(url_key)
        if not geo_url: continue
        try:
            if geo_url.endswith('.zip'):
                req2 = urllib.request.Request(geo_url, headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req2, timeout=25) as r2:
                    z = zipfile.ZipFile(io.BytesIO(r2.read()))
                    inner = [n for n in z.namelist() if n.endswith('.geojson')]
                    if not inner: continue
                    data = json.loads(z.read(inner[0]).decode('utf-8'))
            else:
                req2 = urllib.request.Request(geo_url, headers={'User-Agent':'Mozilla/5.0'})
                with urllib.request.urlopen(req2, timeout=25) as r2:
                    text = r2.read().decode('utf-8', errors='ignore')
                if 'git-lfs' in text[:80]: continue
                data = json.loads(text)
        except Exception:
            continue
        os.makedirs(COUNTRY_SUB_DIR, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        return data
    _SUB_GEO_FAILS.append((en, 'API 数据未取得'))
    return None


# ---------- 真实地图（合规 GeoJSON + ECharts，离线内嵌） ----------
GEO_PROV = os.path.join(BASE, 'assets', 'china_province.json')
GEO_WORLD = os.path.join(BASE, 'assets', 'world_countries.json')
COUNTRY_SUB_DIR = os.path.join(BASE, 'assets', 'countries')   # 国家内州/省/县地图（<英文国家名>.json）
GEO_ECHARTS = os.path.join(BASE, 'assets', 'echarts.min.js')
GEO_API = 'https://geo.datav.aliyun.com/areas_v3/bound/{adcode}_full.json'
GB_API = 'https://www.geoboundaries.org/api/current/gbOpen/{ISO3}/ADM1/'  # 受限网络下不可达
COUNTRY_MAP = {}
_country_map_file = os.path.join(BASE, 'references', 'country_map.json')
if os.path.exists(_country_map_file):
    with open(_country_map_file, encoding='utf-8') as _f:
        COUNTRY_MAP = json.load(_f)
# 英文国家名 → ISO3（geoBoundaries API 用），覆盖常用 ~80 国
EN_ISO3 = {
    'China':'CHN','United States of America':'USA','United States':'USA','Japan':'JPN',
    'South Korea':'KOR','Korea':'KOR','India':'IND','Singapore':'SGP','Germany':'DEU',
    'United Kingdom':'GBR','France':'FRA','Italy':'ITA','Spain':'ESP','Netherlands':'NLD',
    'Russia':'RUS','Canada':'CAN','Australia':'AUS','Brazil':'BRA','Mexico':'MEX',
    'Indonesia':'IDN','Thailand':'THA','Vietnam':'VNM','Malaysia':'MYS','Philippines':'PHL',
    'Saudi Arabia':'SAU','United Arab Emirates':'ARE','Turkey':'TUR','Egypt':'EGY',
    'Switzerland':'CHE','Sweden':'SWE','Norway':'NOR','Denmark':'DNK','Finland':'FIN',
    'Poland':'POL','Czech Rep.':'CZE','Austria':'AUT','Belgium':'BEL','Portugal':'PRT',
    'Greece':'GRC','Ireland':'IRL','Hungary':'HUN','Romania':'ROU','NewNew Zealand':'NZL',
    'South Africa':'ZAF','Argentina':'ARG','Chile':'CHL','Colombia':'COL','Peru':'PER',
    'Israel':'ISR','Pakistan':'PAK','Bangladesh':'BGD','Sri Lanka':'LKA','Ukraine':'UKR',
    'New Caledonia':'NCL','Puerto Rico':'PRI','Fr. Polynesia':'PYF','Dominican Rep.':'DOM',
    'Costa Rica':'CRI','Panama':'PAN','Cuba':'CUB','Jamaica':'JAM','Myanmar':'MMR',
    'Mongolia':'MNG','Kazakhstan':'KAZ','Uzbekistan':'UZB','Dem. Rep. Korea':'PRK',
}


def _norm_geo(n):
    if not n:
        return n
    return re.sub(r'(省|市|壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|地区|盟|自治州)$', '', n)


def _fetch_geo(adcode, timeout=25):
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(GEO_API.format(adcode=adcode),
                                     headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print('  ⚠ 未获取到边界 adcode=%s（%s），该层级将降级为列表展示' % (adcode, e))
        return None


def build_geo(rows, meta):
    """有省/市/县分层时，构建真实地图所需的树 + 内嵌 GeoJSON。无网时降级。
    regionKeys 首列为 country 时自动切世界地图（中文国家名经 country_map 映射为英文）。"""
    rk = meta.get('regionKeys') or []
    if not rk:
        return None
    is_world = (rk[0] == 'country')
    if not is_world and 'prov' not in rk:
        return None

    root = {}
    for r in rows:
        a = r.get('a', 0)
        node = root
        for key in rk:
            nm = r.get(key)
            if not nm or nm == '未提供':
                break   # 缺失/占位值不进入地区层级（如无省份数据的国家）
            if nm not in node:
                node[nm] = {'a': 0, 'c': 0, 'children': {}}
            node[nm]['a'] += a
            node[nm]['c'] += 1
            node = node[nm]['children']

    if is_world:
        # ---------- 世界地图（国家级；数据含省/州时支持向下钻取） ----------
        try:
            with open(GEO_WORLD, encoding='utf-8') as fp:
                world_geo = json.load(fp)
        except Exception as e:
            print('  ⚠ 缺少世界边界文件 assets/world_countries.json：%s' % e)
            return None
        geoJSONs = {'world': world_geo}
        world_names = {(f.get('properties') or {}).get('name') for f in world_geo['features']}
        # 中文国家名 → 英文（数据原值保留在树里，渲染时经 nameMap 转英文匹配地图）
        name_map = {}
        for nm in root:
            en = COUNTRY_MAP.get(nm, nm)
            if en in world_names:
                name_map[nm] = en
        if name_map and len(name_map) < len(root):
            print('  ⚠ 部分国家名未匹配到世界地图：%s（参考 references/country_map.json）'
                  % '、'.join(k for k in root if k not in name_map))
        # 国家内下钻：仅对"数据中真有省/州值"的国家挂载州/省界地图（按需：缓存 → geoBoundaries API → 失败降级柱状）
        if 'prov' in rk:
            for nm, node in root.items():
                if not (node.get('children') or {}):
                    continue   # 该国无下级数据（如只有国家列的值）→ 不加载地图，保持国家级联动
                en = name_map.get(nm, nm)
                if en == 'China':
                    try:
                        with open(GEO_PROV, encoding='utf-8') as fp:
                            geoJSONs['China'] = json.load(fp)
                    except Exception:
                        continue
                    # 中国内 省→市→区 三级（复用中国模式拉取逻辑，联网失败自动降级）
                    p_alias = {}
                    for f in geoJSONs['China']['features']:
                        p = f.get('properties') or {}
                        pnm, pad = p.get('name'), p.get('adcode')
                        if pnm and pad:
                            p_alias[pnm] = str(pad)
                            p_alias[_norm_geo(pnm)] = str(pad)
                    for prov_nm, pnode in (node.get('children') or {}).items():
                        pad = p_alias.get(prov_nm) or p_alias.get(_norm_geo(prov_nm))
                        if not pad:
                            continue
                        cg = _fetch_geo(pad)
                        if not cg:
                            continue
                        geoJSONs[pad] = cg
                        c_alias = {}
                        for f in cg['features']:
                            p = f.get('properties') or {}
                            cnm, cad = p.get('name'), p.get('adcode')
                            if cnm and cad:
                                c_alias[cnm] = str(cad)
                                c_alias[_norm_geo(cnm)] = str(cad)
                        if 'city' in rk and ('county' in rk or 'dist' in rk):
                            for city_nm in (pnode.get('children') or {}):
                                cad = c_alias.get(city_nm) or c_alias.get(_norm_geo(city_nm))
                                if not cad:
                                    continue
                                dg = _fetch_geo(cad)
                                if dg:
                                    geoJSONs[cad] = dg
                    continue
                sub = fetch_sub_geo(en)
                if sub:
                    # 预剥离行政区后缀，让 features.name 与用户数据短名匹配（如 'Osaka Prefecture'→'Osaka'），并保留 _fullName
                    for f in sub.get('features', []):
                        p = f.setdefault('properties', {})
                        orig = p.get('name') or p.get('shapeName') or ''
                        if not orig: continue
                        p['_fullName'] = orig
                        short = re.sub(r' (Prefecture|State|Province|Oblast|Republic|Region|County|Autonomous Region|Department|Governorate|Regency|Capital District|Municipality|SAR|道|府|州|県|都)\s*$', '', orig).strip() or orig
                        p['name'] = short
                    geoJSONs[en] = sub
        return {'root': {'a': 0, 'c': 0, 'children': root}, 'geoJSONs': geoJSONs,
                'rk': rk, 'world': True, 'nameMap': name_map}

    # ---------- 中国地图（省→市→区钻取） ----------
    try:
        with open(GEO_PROV, encoding='utf-8') as fp:
            prov_geo = json.load(fp)
    except Exception as e:
        print('  ⚠ 缺少省级边界文件 assets/china_province.json：%s' % e)
        return None
    geoJSONs = {'100000': prov_geo}
    alias = {}
    for f in prov_geo['features']:
        p = f.get('properties') or {}
        nm, ad = p.get('name'), p.get('adcode')
        if nm and ad:
            alias[nm] = str(ad)
            alias[_norm_geo(nm)] = str(ad)
    present_provs = [p for p in root.keys() if p in alias]
    for p in present_provs:
        ad = alias[p]
        cg = _fetch_geo(ad)
        if not cg:
            continue
        geoJSONs[ad] = cg
        for f in cg['features']:
            p2 = f.get('properties') or {}
            nm, cad = p2.get('name'), p2.get('adcode')
            if nm and cad:
                alias[nm] = str(cad)
                alias[_norm_geo(nm)] = str(cad)
        if 'city' in rk and ('county' in rk or 'dist' in rk):
            for c in list(root.get(p, {}).get('children', {}).keys()):
                cad = alias.get(c)
                if not cad:
                    continue
                dg = _fetch_geo(cad)
                if not dg:
                    continue
                geoJSONs[cad] = dg
                for f in dg['features']:
                    p3 = f.get('properties') or {}
                    nm, coad = p3.get('name'), p3.get('adcode')
                    if nm and coad:
                        alias[nm] = str(coad)
                        alias[_norm_geo(nm)] = str(coad)
    return {'root': {'a': 0, 'c': 0, 'children': root}, 'geoJSONs': geoJSONs, 'rk': rk}


def load_data(path):
    if path == '-':
        # stdin 管道：如 anonymize -i - | build_dashboard -i - ...
        import sys as _sys
        d = json.load(_sys.stdin)
    else:
        with open(path, encoding='utf-8') as fp:
            d = json.load(fp)
    if isinstance(d, list):
        rows = d
        dims = [{'key': k, 'label': LABEL_OF.get(k, k)}
                for k in ('c', 'src', 'signer', 'teacher', 'p', 'campus')
                if any(k in r for r in rows)]
        return rows, dims, 'L0', {}
    return d.get('rows', []), d.get('dims', []), d.get('level', 'L0'), d.get('meta', {})


def run_wizard(args):
    """交互向导：逐项提问补齐缺失参数（仅交互终端可用，stdin 为管道时自动跳过）。"""
    def ask(prompt, default=None):
        if default:
            prompt = '%s [%s]' % (prompt, default)
        try:
            v = input(prompt + '：').strip()
        except (EOFError, KeyboardInterrupt):
            print('\n[错误] 向导被中断')
            raise SystemExit(EXIT_USAGE)
        return v or default

    if not args.input:
        args.input = ask('输入文件（xlsx/csv/json，或 - 用 stdin）')
    if not args.output:
        args.output = ask('输出看板文件')
    if not args.no_lock and not args.password:
        mode = ask('访问方式', '1 加密密码')
        if str(mode).strip().startswith('2'):
            args.no_lock = True
        else:
            args.password = ask('访问密码（8 位以上）')
    if args.title == '销售数据分析看板':
        t = ask('看板标题', '销售数据分析看板')
        args.title = t
    ind = ask('行业（generic/sales/education/retail/clinic/logistics/b2b）', args.industry)
    args.industry = ind or args.industry
    th = ask('主题 id（--list-themes 查看）', args.theme or '')
    args.theme = th or args.theme
    print()


def main():
    ap = argparse.ArgumentParser(description='生成加密销售看板')
    ap.add_argument('-i', '--input', required=False, default=None)
    ap.add_argument('-o', '--output', required=False, default=None)
    ap.add_argument('-p', '--password', default=None)
    ap.add_argument('--no-lock', action='store_true', help='强制免密直开（与 -p 同时给时按免密处理）')
    ap.add_argument('--viewer-password', default=None,
                    help='【可选】访客密码：与 -p 搭配实现分级权限。访客用此密码打开时仅见聚合视图（自动排除敏感字段）')
    ap.add_argument('--viewer-fields', default='n,teacher,signer',
                    help='访客视图排除的敏感字段（逗号分隔，默认 n,teacher,signer）')
    ap.add_argument('--wizard', action='store_true', help='交互向导：逐项提问生成参数（仅交互终端可用）')
    ap.add_argument('--sample', type=int, default=0,
                    help='随机采样 N 条生成（大数据演示用，固定种子可复现）')
    ap.add_argument('--title', default='销售数据分析看板')
    ap.add_argument('--subtitle', default='')
    ap.add_argument('--lock-title', default='数据看板')
    ap.add_argument('--filter-dim', default=None)
    ap.add_argument('--qty-label', default='数量')
    ap.add_argument('--amount-label', default='金额')
    ap.add_argument('--cdn', action='store_true')
    ap.add_argument('--default-chart', default='barh', choices=['barv', 'barh', 'area', 'line'],
                   help='维度图默认样式：barv竖向柱/barh横向柱/area面积/line曲线，默认 barh')
    ap.add_argument('--schema', default=None,
                   help='声明式 viz-schema JSON（跨行业配置：面板显隐/顺序/标签/主题/安全）。不填则按 --industry 自动匹配')
    ap.add_argument('--industry', default='generic',
                   help='行业标识，用于自动加载 references/schema/<industry>.json，默认 generic')
    ap.add_argument('--theme', default=None,
                   help='看板视觉主题 id（apple-glass/stripe/vercel/linear/bloomberg/notion/neubrutalism/tokyo-night/nordic/cyberpunk）。不填则保持原深蓝默认风')
    ap.add_argument('--list-themes', action='store_true', help='列出全部可选视觉主题后退出')
    ap.add_argument('--report', default=None, metavar='PATH',
                    help='【可选】同时生成经营分析报告 HTML 到 PATH（规则引擎，离线可用：概览/走势/构成/地区/风险/建议/缺失说明）')
    ap.add_argument('--report-pdf', default=None, metavar='PATH',
                    help='【可选】同时生成经营分析报告 PDF 到 PATH（需 pip install reportlab；自动使用系统中文字体）')
    ap.add_argument('--live', default=None, metavar='URL',
                    help='【可选】实时大屏：指向脱敏 JSON 数据源 URL，看板每 N 秒自动拉取并刷新全部图表（数据源需为 anonymize 产出的 masked JSON，且该 URL 可被浏览器 fetch）')
    ap.add_argument('--live-interval', type=int, default=30,
                    help='实时刷新间隔（秒，默认 30）')
    ap.add_argument('--iter', type=int, default=DEFAULT_ITERATIONS)
    args = ap.parse_args()

    if args.list_themes:
        if not THEMES:
            err('主题库未加载（scripts/themes.py 缺失）')
            return EXIT_CONFIG
        print('可选看板视觉主题（--theme <id>）：')
        for x in list_themes():
            print('  %-14s %s / %s  [%s]  %s' % (x['id'], x['cn'], x['en'], x['mode'], x['vibe']))
        return EXIT_OK

    if args.wizard and sys.stdin.isatty():
        run_wizard(args)

    if not args.input or not args.output:
        err('需要 -i 输入文件 与 -o 输出文件（或加 --list-themes 查看可选主题，或加 --wizard 交互向导）')
        return EXIT_USAGE

    # 默认免密直开（数据仍脱敏）；-p 传入密码时启用加密——密码是可选接口
    opened = args.no_lock or not args.password
    if opened:
        LOCKED = 'false'
        if args.no_lock and args.password:
            warn('同时指定 -p 与 --no-lock，按免密直开处理')
    else:
        LOCKED = 'true'
        if len(args.password) < 6:
            warn('密码少于 6 位，安全性不足，建议 8 位以上并混合字母数字')

    try:
        rows, dims, level, meta = load_data(args.input)
    except Exception as e:
        err('读取输入失败：%s' % e)
        return EXIT_RUNTIME
    if not rows:
        err('输入数据为空')
        return EXIT_RUNTIME
    if args.sample and 0 < args.sample < len(rows):
        import random
        random.seed(42)  # 固定种子，多次生成可复现
        src_len = len(rows)
        rows = random.sample(rows, args.sample)
        info('大数据演示模式：随机采样 %d 条（源 %d 条，种子固定）' % (args.sample, src_len))

    geo = build_geo(rows, meta)
    schema = load_schema(args)
    schema_errs = validate_schema(schema)
    for e in schema_errs:
        err('schema 配置错误：%s' % e)
    if schema_errs:
        return EXIT_CONFIG
    # 面板字段校验：schema 引用的字段在数据中不存在时警告（避免面板静默空白，如 sankey 缺 ssrc）
    if schema:
        _sf = {'funnel': ['stageKey'], 'heatmap': ['rowKey', 'colKey'],
               'sankey': ['sourceKey', 'targetKey'], 'radar': ['seriesKey', 'axisKey'],
               'gauge': ['measure'], 'treemap': ['keys'],
               'topology': ['sourceKey', 'targetKey'], 'cohort': ['groupKey', 'stepKey']}
        _data_keys = set()
        for _r in rows:
            _data_keys.update(_r.keys())
        for _p, _cfg in schema.items():
            if _p not in _sf or not isinstance(_cfg, dict):
                continue
            for _kk in _sf[_p]:
                _v = _cfg.get(_kk)
                if not _v:
                    continue
                _vals = [_v] if isinstance(_v, str) else _v
                for _f in _vals:
                    if _f in ('a', 'count', 'se'):
                        continue
                    if _f not in _data_keys:
                        print('  ⚠ 面板「%s」引用的字段「%s」在数据中不存在，该面板将无数据（请提供 %s 列，或修改 schema）'
                              % (_p, _f, _f))
    if geo:
        print('🌏 检测到地区分层，构建真实地图（合规 GeoJSON + 离线 ECharts）…')
    # 漏斗图 / 热力图 / 桑基图用 ECharts 渲染，schema 含对应配置时内嵌 ECharts
    need_echarts = bool(geo) or bool(
        schema and (
            (isinstance(schema.get('panels'), list) and any(
                p in schema['panels'] for p in ('funnel', 'heatmap', 'sankey', 'radar', 'gauge', 'treemap', 'topology', 'cohort')))
            or schema.get('funnel')
            or schema.get('heatmap')
            or schema.get('sankey')
            or schema.get('radar')
            or schema.get('gauge')
            or schema.get('treemap')
            or schema.get('topology')
            or schema.get('cohort')
        )
    )
    if need_echarts and not geo:
        print('🌊 检测到 ECharts 图表（漏斗图/热力图/桑基图/雷达图/仪表盘/树图/拓扑图/留存矩阵），内嵌 ECharts 渲染')

    payload_obj = {
        'title': args.title,
        'subtitle': args.subtitle,
        'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'level': level,
        'dims': dims,
        'meta': meta,
        'defaultChart': args.default_chart,
        'filterDim': args.filter_dim or (dims[0]['key'] if dims else None),
        'qtyLabel': args.qty_label,
        'amountLabel': args.amount_label,
        'rows': rows,
        'geo': geo,
        'schema': schema,
    }
    plain = json.dumps(payload_obj, ensure_ascii=False, separators=(',', ':'))
    viewer_out = None
    if opened:
        payload_out = payload_obj
        print(f'明文 {len(plain.encode("utf-8"))/1024:.1f} KB → 免密码直开模式（数据仍脱敏）')
        if args.viewer_password:
            warn('--viewer-password 仅在加密模式（-p）下生效，已忽略（本看板为免密直开）')
    else:
        try:
            enc = encrypt_text(plain, args.password, args.iter)
        except Exception as _e:
            print('  ⚠ 加密失败（%s），自动降级为免密直开（数据仍脱敏）' % _e)
            print('    可重试：换密码重跑；或加 --no-lock 强制免密')
            payload_out = payload_obj
            viewer_out = None
            opened = True
            args.no_lock = True
            LOCKED = 'false'
        else:
            payload_out = enc
            print(f'明文 {len(plain.encode("utf-8"))/1024:.1f} KB → 加密中（{args.iter} 次迭代）…')
            if args.viewer_password:
                exclude = set(f.strip() for f in (args.viewer_fields or 'n,teacher,signer').split(',') if f.strip())
                rows_v = [{k: v for k, v in r.items() if k not in exclude} for r in rows]
                dims_v = [d for d in dims if d['key'] not in exclude]
                pv = dict(payload_obj)
                pv['rows'] = rows_v
                pv['dims'] = dims_v
                viewer_out = encrypt_text(json.dumps(pv, ensure_ascii=False, separators=(',', ':')),
                                          args.viewer_password, args.iter)
                print('🔒 分级权限：访客密码已启用（排除字段：%s；主视图 %d 条 → 访客视图 %d 条）'
                      % ('/'.join(sorted(exclude)), len(rows), len(rows_v)))

    # 资源完整性检查（技能目录不完整时给出明确错误而非 traceback）
    for f, name in ((TPL, '看板模板'), (CRYPTO, '解密库 crypto.js'), (CHARTJS, '图表库 chart.umd.min.js')):
        if not os.path.exists(f):
            err('缺少%s文件：%s（技能目录不完整，请检查 assets/）' % (name, f))
            return EXIT_CONFIG

    with open(TPL, encoding='utf-8') as fp:
        html = fp.read()
    # 主题皮肤注入：注入全部 10 套主题（运行时下拉切换），激活 --theme 或默认 apple-glass
    if THEMES:
        tid = args.theme if (args.theme and args.theme in THEMES) else _DEF_THEME
        # 实时数据源注入（--live）：看板定时拉取最新脱敏 JSON 自动刷新（大屏场景）
        _live_js = ''
        if args.live:
            _live_js = ('<script>window.LIVE_DATA={url:%s,interval:%d};</script>'
                        % (json.dumps(args.live), args.live_interval or 30))
            print('🔴 实时大屏已开启：每 %d 秒自动拉取 %s 并刷新全部图表'
                  % (args.live_interval or 30, args.live))
        html = html.replace('</head>',
                            _live_js
                            + all_themes_html(tid)
                            + '<script>' + all_themes_js(tid) + '</script></head>')
        if args.theme and args.theme in THEMES:
            print('🎨 已应用主题：%s（运行时可用顶部下拉切换全部主题）' % args.theme)
        elif args.theme:
            print('⚠ 未知主题 %s，已用默认 %s（可用 --list-themes 查看）' % (args.theme, _DEF_THEME))
    with open(CRYPTO, encoding='utf-8') as fp:
        cjs = fp.read()
    if args.cdn:
        chart = CDN_TAG
    else:
        with open(CHARTJS, encoding='utf-8') as fp:
            chart = fp.read()

    html = html.replace('__PAGE_TITLE__', args.title if opened else args.lock_title)
    html = html.replace('__LOCK_TITLE__', args.lock_title)
    html = html.replace('__CRYPTO_JS__', cjs)
    html = html.replace('__CHART_JS__', chart)
    # 真实地图 / 漏斗图：geo 或 schema 含 funnel 时内嵌 ECharts（否则保持小体积）
    if need_echarts:
        with open(GEO_ECHARTS, encoding='utf-8') as fp:
            echarts_src = fp.read()
    else:
        echarts_src = ''
    html = html.replace('/*ECHARTS_SRC*/', echarts_src)
    html = html.replace('__PAYLOAD__', json.dumps(payload_out, ensure_ascii=False))
    html = html.replace('__PAYLOAD_VIEWER__', 'null' if viewer_out is None else json.dumps(viewer_out, ensure_ascii=False))
    html = html.replace('__LOCKED__', LOCKED)

    with open(args.output, 'w', encoding='utf-8') as fp:
        fp.write(html)

    # 可选：同时生成经营分析报告（规则引擎，离线）
    if args.report or args.report_pdf:
        try:
            sys.path.insert(0, os.path.join(BASE, 'scripts'))
            from report import analyze, render_html as _report_render
            _rpt = analyze({'rows': rows, 'dims': dims, 'level': level, 'meta': meta})
            if args.report:
                with open(args.report, 'w', encoding='utf-8') as fp:
                    fp.write(_report_render(_rpt, args.title or '经营分析报告'))
                print('📋 已生成经营分析报告 %s' % args.report)
            if args.report_pdf:
                try:
                    from report import render_pdf as _report_pdf
                except ImportError:
                    print('  ⚠ 生成 PDF 需要 reportlab：pip install reportlab（HTML 报告不受影响）')
                else:
                    _report_pdf(_rpt, args.title or '经营分析报告', args.report_pdf)
                    print('📄 已生成经营分析报告 PDF %s' % args.report_pdf)
        except Exception as _e:
            if 'reportlab' in str(_e):
                print('  ⚠ 生成 PDF 需要 reportlab：pip install reportlab（HTML 报告与看板不受影响）')
            else:
                print('  ⚠ 报告生成失败（不影响看板）：%s' % _e)

    total = sum(r.get('a', 0) for r in rows)
    size = os.path.getsize(args.output) / 1024
    print(f'✔ 已生成 {args.output}')
    print(f'  记录 {len(rows)} 条 / 合计 ¥{total:,.0f} / 脱敏 {level} / 文件 {size:.0f} KB')
    print(f'  访问方式：{"免密码直接打开" if opened else "密码保护（密码：" + args.password + "）"}')
    print(f'  离线可用：{"否（需联网加载图表库）" if args.cdn else "是（图表库已内嵌）"}')
    if geo:
        njson = len(geo['geoJSONs'])
        print(f'  🌏 真实地图：已内嵌 {njson} 份合规边界（省→市→县逐级钻取，金额按颜色深浅）')
    if _SUB_GEO_FAILS:
        print('  ⚠ 以下国家州/省地图未加载（网络受限或 ISO3 未内置），请从 https://www.geoboundaries.org/ 下载简化版 GeoJSON 并放入 assets/countries/<英文国家名>.json')
        for nm, why in _SUB_GEO_FAILS:
            print(f'     · {nm} ({why})')
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())

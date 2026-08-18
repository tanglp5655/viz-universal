# -*- coding: utf-8 -*-
"""经营分析报告生成器（规则引擎，离线可用）

输入 anonymize 产出的 masked JSON（含 rows/meta/dims/level），自动生成「经营分析报告」：
总体概览 / 月度走势 / 构成分析 / 地区发现 / 风险与缺失 / 行动建议。
缺失字段遵循 SKILL.md 输出规范：正文 * 标注，文末按字段补充说明。
"""
import json
import os
import sys
from collections import OrderedDict

MONEY = lambda v: '¥{:,.0f}'.format(v or 0)


def _pct(cur, prev):
    if not prev:
        return None
    return (cur - prev) / prev * 100


def analyze(data):
    rows = data.get('rows', [])
    meta = data.get('meta', {}) or {}
    dims = data.get('dims', []) or []
    level = data.get('level', 'L2')
    r = {'level': level, 'rows': len(rows)}

    if not rows:
        return {'summary': '无数据', 'sections': []}

    total = sum(x.get('a', 0) for x in rows)
    cnt = len(rows)
    months = sorted({x['d'][:7] for x in rows if x.get('d')})
    r['total'] = total
    r['cnt'] = cnt
    r['months'] = months

    # 月度序列
    month_amt = OrderedDict()
    for m in months:
        month_amt[m] = sum(x.get('a', 0) for x in rows if x['d'][:7] == m)
    r['month_amt'] = month_amt
    r['month_cnt'] = OrderedDict((m, sum(1 for x in rows if x['d'][:7] == m)) for m in months)

    # ---- 数据完整性预检（对齐 DA"数据真实性判断"高地）----
    # 月度覆盖天数：统计每月数据覆盖到几号
    month_maxday = OrderedDict()
    for m in months:
        ds = [x['d'][8:10] for x in rows if x['d'][:7] == m and len(x['d']) >= 10]
        month_maxday[m] = max(int(d) for d in ds) if ds else 0
    # 最新月不完整判定：覆盖天数 < 15 或 笔数 < 前一月 30%
    integrity = {'incomplete_month': None, 'days_covered': 0, 'warnings': [],
                 'last_full_mom': None, 'last_full_pair': None}
    if len(months) >= 2:
        lm = months[-1]
        ldc = month_maxday.get(lm, 0)
        lcnt = r['month_cnt'].get(lm, 0)
        prev_cnt = r['month_cnt'].get(months[-2], 1)
        if ldc < 15 or lcnt < prev_cnt * 0.3:
            integrity['incomplete_month'] = lm
            integrity['days_covered'] = ldc
            integrity['warnings'].append(
                '最新月份 %s 数据仅覆盖至 %02d 日（%d 笔，上月 %d 笔）——该月不完整，环比以完整月为准'
                % (lm, ldc, lcnt, prev_cnt))
            # 用倒数第 2/3 完整月重算环比
            if len(months) >= 3:
                _p2, _p1 = month_amt[months[-3]], month_amt[months[-2]]
                integrity['last_full_mom'] = _pct(_p1, _p2)
                integrity['last_full_pair'] = (months[-3], months[-2])
        # 时间窗检查
        all_ds = sorted(x['d'] for x in rows if x.get('d'))
        if all_ds:
            integrity['window'] = (all_ds[0], all_ds[-1])
    r['integrity'] = integrity

    # 环比（若有完整性警告，mom 保留原始值，决策层用修正值）
    prev, cur = None, None
    if len(months) >= 2:
        prev, cur = month_amt[months[-2]], month_amt[months[-1]]
    r['mom'] = _pct(cur, prev) if cur is not None else None

    # ---- 深度分析（交叉/驱动分解/签单人矩阵/结构洞察）----
    r['deep'] = build_deep(rows, dims, months, r)

    # 维度构成（dims 排行前 3 + 占比）
    dims_top = []
    for d in dims:
        k = d.get('key')
        if not k:
            continue
        agg = {}
        for x in rows:
            v = x.get(k)
            if v is None or v == '' or v == '未提供':
                continue
            agg[v] = agg.get(v, 0) + x.get('a', 0)
        if not agg:
            continue
        top = sorted(agg.items(), key=lambda kv: -kv[1])[:3]
        top = [(n, a, a / total * 100 if total else 0) for n, a in top]
        dims_top.append({'key': k, 'label': d.get('label', k), 'top': top})
    r['dims_top'] = dims_top

    # 地区（prov）
    rk = meta.get('regionKeys') or []
    prov_key = 'prov' if 'prov' in rk else ('country' if rk and rk[0] == 'country' else None)
    reg_top = []
    if prov_key:
        agg = {}
        for x in rows:
            v = x.get(prov_key)
            if v is None or v == '' or v == '未提供':
                continue
            agg[v] = agg.get(v, 0) + x.get('a', 0)
        if agg:
            top = sorted(agg.items(), key=lambda kv: -kv[1])[:3]
            reg_top = [(n, a, a / total * 100 if total else 0) for n, a in top]
            r['region_label'] = '国家' if prov_key == 'country' else '省份'
    r['region_top'] = reg_top

    # 缺失统计（输出规范条款）
    missing = []
    cols = set()
    for x in rows:
        cols.update(x.keys())
    for c in sorted(cols - {'a', 'se', 'd', 'n'}):
        miss_n = sum(1 for x in rows if not x.get(c) or x.get(c) == '未提供')
        if miss_n:
            missing.append({'field': c, 'n': miss_n, 'pct': miss_n / len(rows) * 100})
    r['missing'] = missing

    # 数据口径溯源（来源文件/数据库）
    r['sources'] = (meta or {}).get('sources') or []

    # 建议（规则引擎）
    tips = []
    if r['mom'] is not None:
        if r['mom'] >= 10:
            tips.append('本月环比增长 %.1f%%，建议加大头部维度投放并强化老客复购' % r['mom'])
        elif r['mom'] <= -10:
            tips.append('本月环比下降 %.1f%%，建议优先排查头部维度下滑原因并启动挽留动作' % r['mom'])
        else:
            tips.append('本月环比变动 %.1f%%，整体平稳，可聚焦优化转化结构' % r['mom'])
    for dt in dims_top:
        t = dt['top'][0] if dt['top'] else None
        if t and t[2] >= 40:
            tips.append('%s「%s」占比 %.0f%%，集中度高，建议关注单一依赖风险' % (dt['label'], t[0], t[2]))
    if reg_top and reg_top[0][2] >= 50:
        tips.append('%s「%s」占比 %.0f%%，区域集中明显，建议评估区域扩展' % (r.get('region_label', '区域'), reg_top[0][0], reg_top[0][2]))
    if r['missing']:
        miss_total = sum(m['n'] for m in r['missing'])
        tips.append('存在 %d 个字段 %d 条缺失（详见文末 * 说明），建议完善采集口径' % (len(r['missing']), miss_total))
    if not tips:
        tips.append('数据整体健康，建议按月度持续跟踪头部维度变化')
    r['tips'] = tips
    # ---- 决策简报（决策问题→答案→置信度→注意事项→行动清单）----
    r['decisions'] = build_decisions(r)
    return r


def build_decisions(r):
    """把分析结果升级为"决策简报"：决策问题 → 简短答案 → 证据 → 置信度 → 注意事项 → 行动清单。
    对齐竞品 Data Analysis 的决策简报模板（评测维度：分析严谨性 / 分析深度）。"""
    months = r.get('months', [])
    seq = list(r.get('month_amt', {}).values())
    mom = r.get('mom')
    n_months = len(months)
    miss_rate = sum(m['n'] for m in r.get('missing', [])) / max(r.get('rows', 1), 1) * 100
    # 置信度规则：样本期>=6 高；3-5 中；<3 低；缺失率>10% 降一档
    def _conf(base):
        if miss_rate > 10:
            return {'高': '中', '中': '低', '低': '低'}[base]
        return base

    decs = []

    # 决策 1：趋势可持续性
    if n_months >= 2:
        inc = r.get('integrity') or {}
        # 数据完整性预检：最新月不完整 → 环比以完整月为准（对齐 DA"数据窗口假象"判断）
        fake_warning = None
        eff_mom = mom
        if inc.get('incomplete_month') and inc.get('last_full_mom') is not None:
            eff_mom = inc['last_full_mom']
            fake_warning = '⚠ 最新月份 %s 数据仅覆盖至 %02d 日（不完整月），原始环比 %+.1f%% 为数据窗口假象；' \
                           '剔除后最近完整月环比（%s→%s）为 %+.1f%%。' % (
                inc['incomplete_month'], inc.get('days_covered', 0), mom or 0,
                inc['last_full_pair'][0], inc['last_full_pair'][1], eff_mom)
        if len(seq) >= 3 and (eff_mom is None or eff_mom > 0) and seq[-1] > seq[-2] > seq[-3]:
            trend = '连续增长'
        elif len(seq) >= 3 and (eff_mom is None or eff_mom < 0) and seq[-1] < seq[-2] < seq[-3]:
            trend = '连续下滑'
        elif eff_mom is not None and abs(eff_mom) >= 10:
            trend = '环比' + ('增长' if eff_mom > 0 else '下滑') + ' %.1f%%' % abs(eff_mom)
        else:
            trend = '整体平稳'
        conf = _conf('高' if n_months >= 6 else ('中' if n_months >= 3 else '低'))
        ans = '样本期 %d 个月（%s），最近趋势：%s。月均金额 %s。' % (
            n_months, ' / '.join(months), trend, money_fn(r.get('total', 0) / max(n_months, 1)))
        if fake_warning:
            ans = fake_warning + ' ' + ans
        if r.get('region_top'):
            ans += ' 区域集中度 CR1=%.0f%%（%s）。' % (r['region_top'][0][2], r['region_top'][0][0])
        notes = ['样本期覆盖 %d 个月，若存在未纳入的大额/补录数据结论会被推翻' % n_months,
                 '高峰/低谷月若由活动或渠道投放驱动，趋势判断需结合外部信息',
                 '脱敏数据不含业务背景，置信度为统计层面']
        if fake_warning:
            notes.insert(0, '数据完整性预检已触发：%s 不完整，请拉取全月数据后重算趋势' % inc['incomplete_month'])
        actions = [
            {'action': ('拉取 %s 全月数据，重建连续月度曲线（当前仅覆盖至 %02d 日）'
                        % (inc['incomplete_month'], inc.get('days_covered', 0))) if fake_warning
                        else '补齐完整月份/年度数据，重建连续月度曲线',
             'owner': '数据负责人', 'due': '1 周内', 'benefit': '消除数据窗口假象，避免误判方向、错误投入'},
            {'action': '定位峰值月的驱动因素（活动/渠道/大单）', 'owner': '运营负责人', 'due': '2 周内',
             'benefit': '锁定增长/下滑主因，聚焦资源投放'},
        ]
        decs.append({
            'q': '近期营收%s是否可持续？' % ('增长' if '增长' in trend else ('下滑' if '下滑' in trend else '平稳')),
            'ans': ans,
            'conf': conf,
            'reason': '样本期 %d 个月' % n_months + ('；存在 %d 个字段缺失' % len(r.get('missing', [])) if r.get('missing') else ''),
            'notes': notes,
            'actions': actions,
        })

    # 决策 2：结构依赖风险（头部维度集中）
    for dt in r.get('dims_top', [])[:1]:
        t = dt['top'][0] if dt['top'] else None
        if t and t[2] >= 40:
            decs.append({
                'q': '是否应降低对「%s」的单一依赖？' % t[0],
                'ans': '「%s」占 %s 的 %.0f%%，集中度偏高，单一维度波动会主导整体表现。' % (t[0], dt['label'], t[2]),
                'conf': _conf('高' if t[2] >= 60 else '中'),
                'reason': 'CR1=%.0f%%（>40%% 触发提示）' % t[2],
                'notes': ['若该维度为自然业务重心（如核心产品），集中并非问题，需结合战略判断',
                          '可通过交叉维度（区域×产品、客户×产品）验证集中是否普遍'],
                'actions': [
                    {'action': '评估拓展次优维度（占比第 2/3 名）的投入', 'owner': '业务负责人', 'due': '2 周内',
                     'benefit': '降低单一依赖，打开第二增长线'},
                    {'action': '监控头部维度份额变化，设置集中度预警线', 'owner': '数据负责人', 'due': '1 个月内',
                     'benefit': '提前预警结构风险'},
                ],
            })

    # 决策 3：区域集中风险
    if r.get('region_top') and r['region_top'][0][2] >= 50:
        reg = r['region_top'][0]
        decs.append({
            'q': '是否应推进区域多元化？',
            'ans': '%s「%s」占比 %.0f%%，区域集中明显，单一市场波动将直接主导整体走势。' % (
                r.get('region_label', '区域'), reg[0], reg[2]),
            'conf': _conf('高' if reg[2] >= 65 else '中'),
            'reason': '区域 CR1=%.0f%%（>=50%% 触发）' % reg[2],
            'notes': ['若为本地化业务（如地方教培），区域集中是常态而非风险',
                      '需对比次优区域的获客成本与客户价值再决策'],
            'actions': [
                {'action': '评估次优区域的单客户价值 vs 主区域获客成本', 'owner': '增长负责人', 'due': '2 周内',
                 'benefit': '判断区域扩张 ROI，避免盲目投入'},
                {'action': '试点 1-2 个次优区域的投放验证', 'owner': '运营负责人', 'due': '1 个月内',
                 'benefit': '小成本验证新市场，可复制性强'},
            ],
        })

    # 决策 4：数据质量/缺失
    if r.get('missing'):
        decs.append({
            'q': '是否需要完善数据采集口径？',
            'ans': '存在 %d 个字段 %d 条缺失（%.1f%%），影响对应维度分析的完整度。' % (
                len(r['missing']), sum(m['n'] for m in r['missing']), miss_rate),
            'conf': '中',
            'reason': '缺失率 %.1f%%（>0%% 触发）' % miss_rate,
            'notes': ['缺失字段详见文末 * 补充说明', '补充完整口径后相关结论应复核'],
            'actions': [
                {'action': '在源头系统补充缺失字段的采集', 'owner': '数据负责人', 'due': '1 个月内',
                 'benefit': '提升分析完整度，减少决策盲区'},
                {'action': '对缺失率>20%% 的字段建立质量看板', 'owner': '数据负责人', 'due': '1 个月内',
                 'benefit': '数据质量问题可视化，源头可控'},
            ],
        })
    return decs


def money_fn(v):
    return '¥{:,.0f}'.format(v or 0)


def money_short(v):
    if v is None:
        return '0'
    v = float(v)
    if v >= 100000000:
        return '%.1f亿' % (v / 100000000)
    if v >= 10000:
        return '%.1f万' % (v / 10000)
    return '%.0f' % v


# ---------------- 报告 SVG 图表（离线、无外部库）----------------
_SVG_C = ['#5b7fff', '#40bfb0', '#d4a84b', '#e8767a', '#8a7cc0', '#5aa88a', '#3f8b9e']


def svg_bar(labels, values, h=170, fmt=None, maxw=400):
    """横向条形图（适合排行：科目/签单人/来源）"""
    n = len(labels)
    row = max(16, int((h - 20) / n))
    ph = n * row + 20
    maxv = max(values) or 1
    pad_l = 64
    bw_max = maxw - pad_l - 48
    out = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx;display:block">' % (maxw, ph, maxw)]
    for i, (lb, v) in enumerate(zip(labels, values)):
        y = 10 + i * row
        bw = bw_max * v / maxv
        out.append('<text x="%d" y="%d" font-size="9" fill="#5c6b85">%s</text>' % (0, y + 10, lb[:12]))
        out.append('<rect x="%d" y="%d" width="%.1f" height="%d" rx="3" fill="%s"/>' % (
            pad_l, y, max(bw, 2), row - 8, _SVG_C[i % len(_SVG_C)]))
        out.append('<text x="%d" y="%d" font-size="9" fill="#33415c">%s</text>' % (
            pad_l + bw + 5, y + 10, (fmt(v) if fmt else money_short(v))))
    out.append('</svg>')
    return ''.join(out)


def svg_trend(labels, amounts, cnts, h=180, maxw=400):
    """组合图：柱=金额（左轴）+ 折线=笔数（右轴）"""
    pad_l, pad_b, pad_t = 30, 20, 16
    plot_w = maxw - pad_l - 6
    plot_h = h - pad_t - pad_b
    maxa = max(amounts) or 1
    maxc = max(cnts) or 1
    n = len(labels)
    iw = plot_w / n
    out = ['<svg viewBox="0 0 %d %d" width="100%%" style="max-width:%dpx;display:block">' % (maxw, h, maxw)]
    # 网格
    for gi in range(4):
        gy = pad_t + plot_h * gi / 3
        out.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" stroke="#eef1f8" stroke-width="1"/>' % (pad_l, gy, maxw - 4, gy))
    # 柱
    for i, (lb, a) in enumerate(zip(labels, amounts)):
        x = pad_l + i * iw + iw * 0.18
        bw = iw * 0.56
        bh = plot_h * a / maxa
        y = h - pad_b - bh
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s"/>' % (x, y, bw, max(bh, 1), _SVG_C[i % len(_SVG_C)]))
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="8" fill="#7c8aa5">%s</text>' % (x + bw / 2, h - 6, lb))
    # 折线（笔数，右轴）
    pts = []
    for i, c in enumerate(cnts):
        x = pad_l + i * iw + iw * 0.46
        y = h - pad_b - plot_h * c / maxc
        pts.append('%.1f,%.1f' % (x, y))
    out.append('<polyline points="%s" fill="none" stroke="#e8767a" stroke-width="2"/>' % ' '.join(pts))
    for i, c in enumerate(cnts):
        x = pad_l + i * iw + iw * 0.46
        y = h - pad_b - plot_h * c / maxc
        out.append('<circle cx="%.1f" cy="%.1f" r="3" fill="#e8767a"/>' % (x, y))
        out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="8" fill="#e8767a">%d</text>' % (x, y - 6, c))
    out.append('</svg>')
    return ''.join(out)


def svg_donut(labels, values, h=150, maxw=150):
    """环形图（适合构成：来源/客单段）"""
    total = sum(values) or 1
    cx = cy = h / 2
    r_out, r_in = h / 2 - 6, h / 2 - 22
    ang = -90.0
    out = ['<svg viewBox="0 0 %d %d" width="%d" style="max-width:%dpx;display:block">' % (h, h, h, h)]
    for i, (lb, v) in enumerate(zip(labels, values)):
        a2 = ang + 360 * v / total
        a1r, a2r = ang * 3.14159 / 180, a2 * 3.14159 / 180
        x1, y1 = cx + r_out * _cos(a1r), cy + r_out * _sin(a1r)
        x2, y2 = cx + r_out * _cos(a2r), cy + r_out * _sin(a2r)
        x3, y3 = cx + r_in * _cos(a2r), cy + r_in * _sin(a2r)
        x4, y4 = cx + r_in * _cos(a1r), cy + r_in * _sin(a1r)
        large = 1 if (a2 - ang) > 180 else 0
        out.append('<path d="M%.1f %.1f A%.1f %.1f 0 %d 1 %.1f %.1f L%.1f %.1f A%.1f %.1f 0 %d 0 %.1f %.1f Z" fill="%s"/>' % (
            x1, y1, r_out, r_out, large, x2, y2, x3, y3, r_in, r_in, large, x4, y4, _SVG_C[i % len(_SVG_C)]))
        ang = a2
    out.append('<text x="%.1f" y="%.1f" text-anchor="middle" font-size="12" font-weight="700" fill="#1f2d4d">%s</text>' % (cx, cy, money_short(total)))
    out.append('</svg>')
    return ''.join(out)


def _cos(a):
    import math
    return math.cos(a)


def _sin(a):
    import math
    return math.sin(a)


def build_deep(rows, dims, months, r):
    """深度分析：交叉组合 / 环比驱动分解 / 签单人月度矩阵 / 结构洞察。
    目标：让报告从"泛泛而谈"升级为"有深度有广度"（交叉归因 + 驱动分解 + 业务结构）。"""
    total = r.get('total', 0) or 1
    deep = {'cross': [], 'drivers': [], 'signer_matrix': [], 'insights': []}
    if not rows:
        return deep

    def _dims(keys):
        return [d.get('key') for d in dims if d.get('key') in keys]

    # 1) 交叉组合：前两个可聚合维度（默认 src×c）Top6
    k1 = 'src' if any('src' in r for r in rows) else (_dims(['c', 'signer']) or ['c'])[0]
    k2 = 'c' if 'c' in rows[0] else (_dims(['signer', 'campus', 'teacher']) or [None])[0]
    if k1 and k2 and k1 != k2:
        agg = {}
        for x in rows:
            v1, v2 = x.get(k1, '-'), x.get(k2, '-')
            agg[(v1, v2)] = agg.get((v1, v2), 0) + x.get('a', 0)
        top = sorted(agg.items(), key=lambda kv: -kv[1])[:6]
        deep['cross'] = [{'k1': v1, 'k2': v2, 'a': a, 'pct': a / total * 100} for (v1, v2), a in top]

    # 2) 环比驱动分解：最近完整月 Δ 中 Top 贡献维度（按 src 与 c）
    if len(months) >= 2:
        lm, pm = months[-1], months[-2]
        # 完整性预检修正：最新月不完整时用倒数完整月对（pair = (旧月, 新月)）
        inc = r.get('integrity') or {}
        if inc.get('incomplete_month') and inc.get('last_full_pair'):
            lm, pm = inc['last_full_pair'][1], inc['last_full_pair'][0]
        for k in ('src', 'c', 'signer'):
            if not any(k in x for x in rows):
                continue
            cur_m, prev_m = {}, {}
            for x in rows:
                if x['d'][:7] == lm:
                    cur_m[x.get(k, '-')] = cur_m.get(x.get(k, '-'), 0) + x.get('a', 0)
                elif x['d'][:7] == pm:
                    prev_m[x.get(k, '-')] = prev_m.get(x.get(k, '-'), 0) + x.get('a', 0)
            if not cur_m or not prev_m:
                continue
            deltas = {kk: cur_m.get(kk, 0) - prev_m.get(kk, 0) for kk in set(cur_m) | set(prev_m)}
            top_d = sorted(deltas.items(), key=lambda kv: -kv[1])[:3]
            deep['drivers'].append({'key': k, 'pair': (pm, lm), 'top': top_d})

    # 3) 签单人月度矩阵（Top3 签单人 × 月份）
    if any('signer' in x for x in rows):
        sg = {}
        for x in rows:
            s = x.get('signer', '-')
            sg.setdefault(s, {})[x['d'][:7]] = sg.get(s, {}).get(x['d'][:7], 0) + x.get('a', 0)
        top_sg = sorted(sg.items(), key=lambda kv: -sum(kv[1].values()))[:3]
        deep['signer_matrix'] = [{'s': s, 'by_month': {m: msum.get(m, 0) for m in months}} for s, msum in top_sg]

    # 4) 结构洞察
    ins = []
    # 课程集中（教培语境）
    if any('c' in x for x in rows):
        cagg = {}
        for x in rows:
            cagg[x.get('c', '-')] = cagg.get(x.get('c', '-'), 0) + x.get('a', 0)
        cs = sorted(cagg.items(), key=lambda kv: -kv[1])
        if cs:
            _c_label = '主营结构'
            for _d in dims:
                if _d.get('key') == 'c' and _d.get('label'):
                    _c_label = _d['label']
                    break
            ins.append('%s：Top1「%s」占 %.0f%%，Top3 合计 %.0f%%（%s）'
                       % (_c_label, cs[0][0], cs[0][1] / total * 100,
                          sum(v for _, v in cs[:3]) / total * 100,
                          ' / '.join(n for n, _ in cs[:3])))
    # 来源结构（新生/老生）
    if any('src' in x for x in rows):
        sagg = {}
        for x in rows:
            sagg[x.get('src', '-')] = sagg.get(x.get('src', '-'), 0) + x.get('a', 0)
        ss = sorted(sagg.items(), key=lambda kv: -kv[1])
        if len(ss) >= 2:
            top_src, second_src = ss[0], ss[1]
            ins.append('来源结构：「%s」占 %.0f%%、「%s」占 %.0f%%——%s'
                       % (top_src[0], top_src[1] / total * 100, second_src[0], second_src[1] / total * 100,
                          '呈复购/续费驱动' if top_src[0] in ('老生', '老学员', '老客') else '获客与复购并重'))
    # 客单价对比（新生 vs 整体）
    if any('src' in x for x in rows) and any('n' in x for x in rows):
        new_src = [x for x in rows if x.get('src') in ('新生', '新客户', '新客')]
        if new_src and len(new_src) < len(rows):
            na = sum(x.get('a', 0) for x in new_src) / len(new_src)
            ins.append('新生客单价 ¥%.0f vs 整体 ¥%.0f（%s）'
                       % (na, r.get('total', 0) / max(r.get('cnt', 1), 1),
                          '新生获客单价偏低，需看续课验证' if na < r.get('total', 0) / max(r.get('cnt', 1), 1) else '新生结构健康'))
    # 签单人集中
    if deep['signer_matrix']:
        s0 = deep['signer_matrix'][0]
        ins.append('签单集中：Top1「%s」贡献 %.0f%%（%s 至 %s 累计）——%s'
                   % (s0['s'], sum(s0['by_month'].values()) / total * 100, months[0], months[-1],
                      '存在单点依赖风险' if sum(s0['by_month'].values()) / total > 0.4 else '结构分散，依赖可控'))
    # 课次/单价（教培）
    if any('se' in x for x in rows):
        se_sum = sum(x.get('se', 0) for x in rows)
        if se_sum:
            ins.append('平均课次单价 ¥%.0f/课次（累计课次 %d）' % (total / se_sum, se_sum))
    deep['insights'] = ins[:6]

    # ---- v0.9.3 深度对等：客单分位 / 老师结构 / 校区维度 / 个人状态 / 扩科专项 / 一句话结论 ----
    # 客单分位段
    amounts = sorted(x.get('a', 0) for x in rows if x.get('a'))
    if len(amounts) >= 4:
        def _q(p):
            i = int(len(amounts) * p)
            return amounts[min(i, len(amounts) - 1)]
        deep['price_segments'] = {
            'p50': _q(0.5), 'p75': _q(0.75), 'mean': sum(amounts) / len(amounts),
            'n': len(amounts),
            'high_ratio': sum(1 for a in amounts if a >= _q(0.75)) / len(amounts) * 100,
            'low_ratio': sum(1 for a in amounts if a <= _q(0.25)) / len(amounts) * 100,
        }
    # 客单分段（3 档：低/中/高，动态以 P50/P75 为界）
    if amounts:
        p50 = _q(0.5) if len(amounts) >= 4 else (amounts[len(amounts)//2] if amounts else 0)
        p75 = _q(0.75) if len(amounts) >= 4 else p50
        _k_low = '低（<%s）' % money_short(p50)
        _k_mid = '中（%s~%s）' % (money_short(p50), money_short(p75))
        _k_high = '高（>%s）' % money_short(p75)
        seg = {_k_low: 0, _k_mid: 0, _k_high: 0}
        for a in amounts:
            if a <= p50:
                key = _k_low
            elif a <= p75:
                key = _k_mid
            else:
                key = _k_high
            seg[key] = seg.get(key, 0) + 1
        deep['price_bands'] = {k: v for k, v in seg.items()}

    # 老师结构（teacher 列）
    if any('teacher' in x for x in rows):
        tagg = {}
        for x in rows:
            tagg[x.get('teacher', '-')] = tagg.get(x.get('teacher', '-'), 0) + x.get('a', 0)
        ts = sorted(tagg.items(), key=lambda kv: -kv[1])
        deep['teacher'] = [{'name': n, 'a': v, 'pct': v / total * 100} for n, v in ts[:5]]
        deep['teacher_dep'] = ts[0][1] / total * 100 if ts else 0
        # 兜底标签检测（兼职/外包/其他）
        deep['teacher_fallback'] = [n for n, _ in ts[:5] if any(w in n for w in ('兼职', '外包', '其他', '临时'))]

    # 校区维度（campus 列）
    if any('campus' in x for x in rows):
        cagg = {}
        for x in rows:
            cagg[x.get('campus', '-')] = cagg.get(x.get('campus', '-'), 0) + x.get('a', 0)
        cs = sorted(cagg.items(), key=lambda kv: -kv[1])
        deep['campus'] = [{'name': n, 'a': v, 'pct': v / total * 100} for n, v in cs[:5]]
        # 最新完整月新增校区检测
        inc = r.get('integrity') or {}
        pair = inc.get('last_full_pair') if inc.get('incomplete_month') else (months[-2], months[-1])
        if len(pair) == 2 and len(months) >= 2:
            old_c = {x.get('campus') for x in rows if x['d'][:7] == pair[0]}
            new_c = {x.get('campus') for x in rows if x['d'][:7] == pair[1]}
            deep['campus_new'] = sorted(new_c - old_c)[:3]

    # 签单人个人状态（Top3 最新完整月趋势）
    if deep.get('signer_matrix'):
        inc = r.get('integrity') or {}
        pair = inc.get('last_full_pair') if inc.get('incomplete_month') else (months[-2], months[-1])
        if len(pair) == 2 and pair[0] in months and pair[1] in months:
            for sm in deep['signer_matrix']:
                a, b = sm['by_month'].get(pair[0], 0), sm['by_month'].get(pair[1], 0)
                if a <= 0 and b <= 0:
                    sm['status'] = '无产出'
                elif a <= 0:
                    sm['status'] = '爆发（新增 %s）' % money_short(b)
                elif b >= a * 1.5:
                    sm['status'] = '爆发（%s → %s，+%.0f%%）' % (money_short(a), money_short(b), (b - a) / a * 100)
                elif b <= a * 0.5:
                    sm['status'] = '下滑（%s → %s，-%.0f%%）' % (money_short(a), money_short(b), (a - b) / a * 100)
                else:
                    sm['status'] = '平稳'

    # 扩科专项（src 含"扩科/加购/增购"）
    for kw in ('扩科', '加购', '增购', '增项'):
        if any(kw in str(x.get('src', '')) for x in rows):
            exp = [x for x in rows if kw in str(x.get('src', ''))]
            exp_total = sum(x.get('a', 0) for x in exp)
            deep['expansion'] = {
                'kw': kw, 'n': len(exp), 'a': exp_total,
                'pct': exp_total / total * 100,
                'top_c': sorted({(x.get('c', '-')): 0 for x in exp}.items())[:0] or None,
            }
            # 扩科科目 Top
            cexp = {}
            for x in exp:
                cexp[x.get('c', '-')] = cexp.get(x.get('c', '-'), 0) + x.get('a', 0)
            deep['expansion']['top_c'] = sorted(cexp.items(), key=lambda kv: -kv[1])[:3]
            # 与上月对比
            if len(months) >= 2:
                pm = months[-2]
                prev_exp = [x for x in rows if kw in str(x.get('src', '')) and x['d'][:7] == pm]
                if prev_exp:
                    deep['expansion']['prev_n'] = len(prev_exp)
                    deep['expansion']['prev_a'] = sum(x.get('a', 0) for x in prev_exp)
            break

    # 一句话结论（全行业通用：营收 + 环比 + Top 驱动 + 亮点/风险）
    inc = r.get('integrity') or {}
    mom_used = inc.get('last_full_mom') if inc.get('incomplete_month') and inc.get('last_full_mom') is not None else r.get('mom')
    parts = ['%s 营收 %s（%d 笔）' % (months[-1], money_fn(r.get('total', 0)), r.get('cnt', 0))]
    if mom_used is not None:
        parts.append('环比%s %.1f%%' % ('增长' if mom_used > 0 else '下滑', abs(mom_used)))
    if deep.get('drivers') and deep['drivers'][0]['top']:
        d0 = deep['drivers'][0]
        pos = [k for k, v in d0['top'] if v > 0]
        if pos:
            parts.append('主要由「%s」驱动' % '、'.join(pos[:2]))
    if deep.get('signer_matrix'):
        s0 = deep['signer_matrix'][0]
        parts.append('Top 签单人「%s」贡献 %.0f%%' % (s0['s'], sum(s0['by_month'].values()) / total * 100))
    if deep.get('teacher_dep') and deep['teacher_dep'] >= 30:
        parts.append('服务人员依赖度 %.0f%%' % deep['teacher_dep'])
    if deep.get('expansion'):
        parts.append('「%s」占比升至 %.1f%%' % (deep['expansion']['kw'], deep['expansion']['pct']))
    if inc.get('incomplete_month'):
        parts.append('⚠ %s 数据不完整（覆盖至 %02d 日）' % (inc['incomplete_month'], inc.get('days_covered', 0)))
    deep['summary'] = '；'.join(parts) + '。'

    # ---- v0.9.7 故事化：本月亮点 / 风险注意点 / 科目排名变化 / 最新月开局 ----
    hl, cn = [], []
    # 亮点 1：双签单引擎（Top2 合计占比 >=60%）
    if deep.get('signer_matrix') and len(deep['signer_matrix']) >= 2:
        sm = deep['signer_matrix']
        s0, s1 = sum(sm[0]['by_month'].values()), sum(sm[1]['by_month'].values())
        if (s0 + s1) / total >= 0.6:
            hl.append('双引擎驱动：「%s」%s + 「%s」%s 合计贡献 %.0f%%' % (
                sm[0]['s'], money_short(s0), sm[1]['s'], money_short(s1), (s0 + s1) / total * 100))
    # 亮点 2：扩科放量
    if deep.get('expansion') and deep['expansion']['pct'] >= 5:
        ex = deep['expansion']
        g = '，环比单数增长 %.0f 倍' % (ex['n'] / ex['prev_n']) if ex.get('prev_n') else ''
        hl.append('「%s」放量：%d 笔 %s（占 %.1f%%%s）' % (ex['kw'], ex['n'], money_short(ex['a']), ex['pct'], g))
    # 亮点 3：高客单结构
    if deep.get('price_segments') and deep['price_segments'].get('high_ratio', 0) >= 30:
        hl.append('高客单结构：>P75 客单段占 %.0f%%，中高客单主导' % deep['price_segments']['high_ratio'])
    # 亮点 4：营收高增
    mom_used = (inc.get('last_full_mom') if inc.get('incomplete_month') and inc.get('last_full_mom') is not None
                else r.get('mom'))
    if mom_used is not None and mom_used >= 30:
        hl.append('营收高增：完整月环比 %+.1f%%' % mom_used)
    # 亮点 5：新生结构（src 有"新生"类）
    if any('src' in x for x in rows):
        sagg = {}
        for x in rows:
            sagg[x.get('src', '-')] = sagg.get(x.get('src', '-'), 0) + x.get('a', 0)
        new_v = sum(v for k, v in sagg.items() if any(w in k for w in ('新生', '新客', '新客户')))
        if new_v and new_v / total >= 0.2:
            hl.append('新增量：新客来源贡献 %s（%.0f%%）' % (money_short(new_v), new_v / total * 100))
    # 注意点 1：科目"量大价低"
    if any('c' in x for x in rows):
        cagg_n, cagg_a = {}, {}
        for x in rows:
            cagg_a[x.get('c', '-')] = cagg_a.get(x.get('c', '-'), 0) + x.get('a', 0)
            cagg_n[x.get('c', '-')] = cagg_n.get(x.get('c', '-'), 0) + 1
        avg = total / max(r.get('cnt', 1), 1)
        for k in sorted(cagg_a, key=lambda k: -cagg_n.get(k, 0))[:3]:
            if cagg_n.get(k, 0) >= 3 and cagg_a.get(k, 0) / cagg_n[k] < avg * 0.6:
                cn.append('「%s」量大价低：%d 单 %s（客单 %s < 平均 %s 的 60%%）——低价/引流课占比高'
                          % (k, cagg_n[k], money_short(cagg_a[k]), money_short(cagg_a[k] / cagg_n[k]),
                             money_short(avg)))
                break
    # 注意点 2：服务人员依赖
    if deep.get('teacher_dep') and deep['teacher_dep'] >= 30:
        cn.append('服务人员依赖：Top1「%s」占 %.0f%%%s'
                  % (deep['teacher'][0]['name'], deep['teacher_dep'],
                     ('；「%s」为兜底标签' % deep['teacher_fallback'][0]) if deep.get('teacher_fallback') else ''))
    # 注意点 3：签单集中 + 个人下滑
    if deep.get('signer_matrix'):
        s0r = sum(deep['signer_matrix'][0]['by_month'].values()) / total
        if s0r > 0.4:
            cn.append('签单集中：Top1「%s」累计占比 %.0f%%，单点依赖风险'
                      % (deep['signer_matrix'][0]['s'], s0r * 100))
        for s in deep['signer_matrix']:
            if '下滑' in s.get('status', ''):
                cn.append('签单人下滑：「%s」%s' % (s['s'], s['status']))
    # 注意点 4：数据不完整
    if inc.get('incomplete_month'):
        cn.append('数据窗口：%s 仅覆盖至 %02d 日（不完整月），环比以完整月为准'
                  % (inc['incomplete_month'], inc.get('days_covered', 0)))
    deep['highlights'] = hl[:3]
    deep['concerns'] = cn[:4]

    # 科目排名变化（完整月对 Top3 环比 + 排名跃升）
    pair = (inc.get('last_full_pair') if inc.get('incomplete_month') and inc.get('last_full_pair')
            else ((months[-2], months[-1]) if len(months) >= 2 else None))
    if pair and any('c' in x for x in rows):
        cm = [{}, {}]
        for x in rows:
            if x['d'][:7] == pair[0]:
                cm[0][x.get('c', '-')] = cm[0].get(x.get('c', '-'), 0) + x.get('a', 0)
            elif x['d'][:7] == pair[1]:
                cm[1][x.get('c', '-')] = cm[1].get(x.get('c', '-'), 0) + x.get('a', 0)
        rk = [{k: i for i, (k, _) in enumerate(sorted(d.items(), key=lambda kv: -kv[1]))} for d in cm]
        chg = []
        for k in sorted(cm[1], key=lambda k: -cm[1][k])[:3]:
            prev_v = cm[0].get(k, 0)
            move = rk[0].get(k, 99) - rk[1].get(k, 99)
            chg.append({'name': k, 'cur': cm[1][k], 'prev': prev_v,
                        'move': ('上升%d位' % move) if move > 0 else ('下降%d位' % -move) if move < 0 else '持平',
                        'is_new': k not in cm[0]})
        deep['cat_change'] = {'pair': pair, 'top': chg}

    # 最新月开局解读（最新月份 笔数/金额 + 前 3 构成）
    lm = months[-1] if months else None
    if lm:
        lr = [x for x in rows if x['d'][:7] == lm]
        if lr:
            l_total = sum(x.get('a', 0) for x in lr)
            l_c = {}
            for x in lr:
                l_c[x.get('c', '-')] = l_c.get(x.get('c', '-'), 0) + x.get('a', 0)
            top_c = '、'.join('「%s」%s' % (k, money_short(v)) for k, v in sorted(l_c.items(), key=lambda kv: -kv[1])[:3])
            l_src = {}
            for x in lr:
                l_src[x.get('src', '-')] = l_src.get(x.get('src', '-'), 0) + 1
            top_src = '、'.join('「%s」%d单' % (k, v) for k, v in sorted(l_src.items(), key=lambda kv: -kv[1])[:2])
            pace = ''
            if inc.get('incomplete_month') == lm and inc.get('days_covered'):
                days = inc['days_covered']
                if days > 0 and l_total / days * 30 > r.get('total', 0) / max(len(months), 1) * 0.9:
                    pace = '按当前节奏推算，全月有望接近此前月均水平'
                else:
                    pace = '按当前节奏推算，全月或低于此前月均'
            deep['opening'] = {'month': lm, 'n': len(lr), 'a': l_total,
                               'top_c': top_c, 'top_src': top_src, 'pace': pace}
    return deep


def render_html(r, title='经营分析报告', theme='apple-glass'):
    """渲染为 HTML 报告页（暗色，无外部依赖）。"""
    def money(v):
        return '¥{:,}'.format(int(v))

    sec = []
    # 概览
    mom_txt = ''
    if r.get('mom') is not None:
        up = r['mom'] >= 0
        mom_txt = '<span style="color:%s">环比 %+.1f%%</span>' % ('#4fd0c0' if up else '#e8767a', r['mom'])
    # 数据完整性预检警告（对齐 DA"数据窗口假象"判断）
    _inc = r.get('integrity') or {}
    if _inc.get('incomplete_month'):
        sec.insert(0, '<div class="warn">⚠️ <b>数据完整性预检</b>：最新月份 %s 数据仅覆盖至 %02d 日（不完整月），'
                      '原始环比 %+.1f%% 可能为数据窗口假象——结论请以完整月为准（最近完整月环比 %+.1f%%）。</div>'
                      % (_inc['incomplete_month'], _inc.get('days_covered', 0), r.get('mom') or 0,
                         _inc.get('last_full_mom') or 0))
    sec.append('<div class="kpis">'
               '<div class="kpi"><div class="v">%s</div><div class="l">总金额</div></div>'
               '<div class="kpi"><div class="v">%s</div><div class="l">交易笔数</div></div>'
               '<div class="kpi"><div class="v">%s</div><div class="l">客单价</div></div>'
               '<div class="kpi"><div class="v">%s</div><div class="l">环比（%s vs %s）</div></div>'
               '</div>' % (money(r.get('total', 0)), r.get('cnt', 0),
                           money(r.get('total', 0) / r.get('cnt', 1)),
                           mom_txt, r.get('months', ['—', '—'])[-1],
                           r.get('months', ['—'])[-2] if len(r.get('months', [])) >= 2 else '—'))

    # 走势
    if r.get('month_amt'):
        rows_m = ''.join(
            '<tr><td>%s</td><td>%s</td><td>%d 笔</td></tr>' % (m, money(v), r['month_cnt'].get(m, 0))
            for m, v in r['month_amt'].items())
        _trd = svg_trend([m[2:] + '月' for m in r['month_amt'].keys()],
                         list(r['month_amt'].values()),
                         [r['month_cnt'].get(m, 0) for m in r['month_amt'].keys()])
        sec.append('<h3>一、月度走势</h3>%s<table><tr><th>月份</th><th>金额</th><th>笔数</th></tr>%s</table>'
                   % (_trd, rows_m))
        seq = list(r['month_amt'].values())
        if len(seq) >= 3 and seq[-1] > seq[-2] > seq[-3]:
            sec.append('<p>近三个月连续增长，趋势向好。</p>')
        elif len(seq) >= 3 and seq[-1] < seq[-2] < seq[-3]:
            sec.append('<p>近三个月连续下滑，需重点关注。</p>')
        elif len(seq) >= 2:
            sec.append('<p>近月波动，建议结合构成分析定位驱动因素。</p>')

    # 构成
    if r.get('dims_top'):
        sec.append('<h3>二、构成分析</h3>')
        for dt in r['dims_top']:
            if not dt['top']:
                continue
            items = '、'.join('「%s」占 %.1f%%' % (n, p) for n, a, p in dt['top'])
            sec.append('<p><b>%s</b>：%s。</p>' % (dt['label'], items))

    # 地区
    if r.get('region_top'):
        items = '、'.join('「%s」%.1f%%' % (n, p) for n, a, p in r['region_top'])
        sec.append('<h3>三、%s分布</h3><p>头部：%s。</p>' % (r.get('region_label', '区域'), items))

    # 风险与缺失（正文 * 标注）
    if r.get('missing'):
        stars = '；'.join('%s*' % m['field'] for m in r['missing'][:3])
        sec.append('<h3>四、数据质量</h3><p>部分字段存在缺失（%s），详见文末补充说明。</p>' % stars)
    elif r.get('tips'):
        sec.append('<h3>四、风险提示</h3><p>整体数据完整，无显著缺失。</p>')

    # 建议
    sec.append('<h3>五、行动建议</h3><ul>%s</ul>'
               % ''.join('<li>%s</li>' % t for t in r.get('tips', [])))

    # 深度分析（文字叙述为主、表格为辅——对齐专业经营报告风格）
    _dp = r.get('deep') or {}
    dsec = []
    # 交叉组合（叙述 + 科目条形图）
    if _dp.get('cross'):
        top3 = _dp['cross'][:3]
        items = '、'.join('「%s→%s」%s（%.1f%%）' % (c['k1'], c['k2'], money_fn(c['a']), c['pct']) for c in top3)
        dsec.append('<h3>交叉结构</h3><p>主力组合集中于 %s，反映核心客群与主打产品的高度绑定。%s</p>'
                    % (items, ('其余组合占比分散' if len(_dp['cross']) > 3 else '')))
        # 科目金额条形图（按 k2 聚合 Top5）
        k2agg = {}
        for c in _dp['cross']:
            k2agg[c['k2']] = k2agg.get(c['k2'], 0) + c['a']
        if k2agg:
            labs = [k for k, _ in sorted(k2agg.items(), key=lambda kv: -kv[1])[:5]]
            vals = [k2agg[k] for k in labs]
            dsec.append(svg_bar(labs, vals))
    # 驱动分解（叙述）
    if _dp.get('drivers'):
        d0 = _dp['drivers'][0]
        pos = [('「%s」%s' % (k, ('+%s' % money_fn(v)) if v >= 0 else ('-%s' % money_fn(-v)))) for k, v in d0['top'][:2]]
        dsec.append('<h3>增长/下滑驱动</h3><p>环比变动主要由 %s 贡献；分维度看，%s。</p>'
                    % ('、'.join(pos),
                       '；'.join('%s 维度：%s' % (dr['key'],
                                 '、'.join('「%s」%s' % (k, ('+%s' % money_fn(v)) if v >= 0 else ('-%s' % money_fn(-v)))
                                           for k, v in dr['top'][:2])) for dr in _dp['drivers'][1:])))
    # 签单人（叙述 + 条形图）
    if _dp.get('signer_matrix'):
        st_txt = '；'.join('「%s」%s' % (s['s'], s.get('status', '')) for s in _dp['signer_matrix'])
        dsec.append('<h3>签单人表现</h3><p>头部签单人：%s。%s</p>'
                    % (st_txt,
                       ('Top1「%s」累计贡献 %.0f%%，存在单点依赖风险'
                        % (_dp['signer_matrix'][0]['s'],
                           sum(_dp['signer_matrix'][0]['by_month'].values()) / max(r.get('total', 1), 1) * 100)
                        if sum(_dp['signer_matrix'][0]['by_month'].values()) / max(r.get('total', 1), 1) > 0.4 else '')))
        _sg_labs = [s['s'] for s in _dp['signer_matrix']]
        _sg_vals = [sum(s['by_month'].values()) for s in _dp['signer_matrix']]
        dsec.append(svg_bar(_sg_labs, _sg_vals))
    # 客单结构（叙述）
    if _dp.get('price_bands'):
        pj = _dp.get('price_segments') or {}
        seg_txt = '、'.join('「%s」%d 笔' % (k, v) for k, v in _dp['price_bands'].items())
        pj_txt = ''
        if pj:
            pj_txt = '客单中位 %s、P75 %s、均值 %s，高客单段（>P75）占 %.0f%%%s。' % (
                money_fn(pj.get('p50', 0)), money_fn(pj.get('p75', 0)), money_fn(pj.get('mean', 0)),
                pj.get('high_ratio', 0),
                '，客单结构整体偏高' if pj.get('high_ratio', 0) >= 40 else ('，客单中位低于均值，存在右偏' if pj.get('mean', 0) > pj.get('p50', 0) else ''))
        dsec.append('<h3>客单结构</h3><p>%s %s</p>' % (seg_txt, pj_txt))
        # 客单段环形图
        _pb_labs = list(_dp['price_bands'].keys())
        _pb_vals = list(_dp['price_bands'].values())
        dsec.append(svg_donut(_pb_labs, _pb_vals))
    # 老师结构（叙述 + 条形图）
    if _dp.get('teacher'):
        fb = _dp.get('teacher_fallback') or []
        t_txt = '、'.join('「%s」%s（%.0f%%）' % (t['name'], money_fn(t['a']), t['pct']) for t in _dp['teacher'][:3])
        dep = _dp.get('teacher_dep', 0)
        dsec.append('<h3>服务人员结构</h3><p>头部服务人员：%s%s%s。</p>'
                    % (t_txt,
                       ('；Top1 依赖度 %.0f%%，存在单点依赖' % dep) if dep >= 30 else '',
                       ('；「%s」为兜底标签，建议拆分口径' % fb[0]) if fb else ''))
        _t_labs = [t['name'] for t in _dp['teacher'][:5]]
        _t_vals = [t['a'] for t in _dp['teacher'][:5]]
        dsec.append(svg_bar(_t_labs, _t_vals))
    # 校区维度（叙述）
    if _dp.get('campus'):
        c_txt = '、'.join('「%s」%s（%.0f%%）' % (c['name'], money_fn(c['a']), c['pct']) for c in _dp['campus'][:3])
        new_txt = ('；新增场所：%s' % '、'.join(_dp['campus_new'])) if _dp.get('campus_new') else ''
        dsec.append('<h3>场所/门店结构</h3><p>头部场所：%s。%s</p>' % (c_txt, new_txt))
    # 扩科专项（叙述）
    if _dp.get('expansion'):
        ex = _dp['expansion']
        prev_txt = ''
        if ex.get('prev_a'):
            prev_txt = '；环比上月 %d 笔 %s，单数增长 %.0f 倍' % (
                ex['prev_n'], money_fn(ex['prev_a']),
                ex['n'] / ex['prev_n'] if ex.get('prev_n') else 0)
        topc = '、'.join('「%s」%s' % (n, money_short(v)) for n, v in ex.get('top_c', []))
        dsec.append('<h3>「%s」专项</h3><p>本月 %d 笔 %s，占 %.1f%%%s，集中于 %s——属于高价值增量，建议持续加码。</p>'
                    % (ex['kw'], ex['n'], money_fn(ex['a']), ex['pct'], prev_txt, topc))
    # 本月亮点（故事化）
    if _dp.get('highlights'):
        dsec.append('<h3>本月亮点</h3><ul>%s</ul>'
                    % ''.join('<li>✅ %s</li>' % i for i in _dp['highlights']))
    # 风险注意点（故事化）
    if _dp.get('concerns'):
        dsec.append('<h3>风险注意点</h3><ul>%s</ul>'
                    % ''.join('<li>⚠️ %s</li>' % i for i in _dp['concerns']))
    # 科目排名变化
    if _dp.get('cat_change'):
        cc = _dp['cat_change']
        items = '、'.join('「%s」%s（上月 %s，%s%s）' % (
            t['name'], money_fn(t['cur']), money_fn(t['prev']),
            '新上榜' if t['is_new'] else t['move'], '' if t['is_new'] else '') for t in cc['top'])
        dsec.append('<h3>主营结构变化（%s → %s）</h3><p>%s。</p>' % (cc['pair'][0], cc['pair'][1], items))
    # 最新月开局解读
    if _dp.get('opening'):
        op = _dp['opening']
        pace_txt = ('；%s' % op['pace']) if op.get('pace') else ''
        dsec.append('<h3>%s开局解读</h3><p>截至当前 %s 已有 %d 笔 %s，构成：%s；来源：%s。%s</p>'
                    % (op['month'][:7], op['month'], op['n'], money_fn(op['a']),
                       op['top_c'], op['top_src'], pace_txt.strip('；')))
    if _dp.get('insights'):
        dsec.append('<h3>结构洞察</h3><ul>%s</ul>'
                    % ''.join('<li>%s</li>' % i for i in _dp['insights']))
    if dsec:
        sec.append('\n'.join(dsec))
    # 一句话结论（放报告最前）
    if _dp.get('summary'):
        sec.insert(0, '<div class="sum">📌 <b>一句话结论</b>：%s</div>' % _dp['summary'])

    # 决策简报（决策问题→答案→置信度→注意事项→行动清单）
    if r.get('decisions'):
        conf_badge = {'高': '<span style="color:#4fd0c0">🟢 高</span>',
                      '中': '<span style="color:#ffb86c">🟡 中</span>',
                      '低': '<span style="color:#e8767a">🔴 低</span>'}
        dsec = ['<h3>📌 决策简报</h3>']
        for i, dc in enumerate(r['decisions'], 1):
            dsec.append('<div class="dc"><p><b>【决策 %d】%s</b></p>' % (i, dc['q']))
            dsec.append('<p><b>简短答案</b>：%s</p>' % dc['ans'])
            dsec.append('<p><b>置信度</b>：%s <span class="note2">%s</span></p>'
                        % (conf_badge.get(dc['conf'], dc['conf']), dc.get('reason', '')))
            dsec.append('<p><b>注意事项（什么会改变结论）</b>：</p><ul>%s</ul>'
                        % ''.join('<li>%s</li>' % n for n in dc.get('notes', [])))
            dsec.append('<table><tr><th>下一步行动</th><th>负责人</th><th>期限</th><th>预期收益</th></tr>%s</table>'
                        % ''.join('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                                  % (a['action'], a['owner'], a['due'], a.get('benefit', '')) for a in dc.get('actions', [])))
            dsec.append('</div>')
        sec.insert(0, '\n'.join(dsec))

    # 文末缺失补充说明（输出规范条款）
    foot = ''
    if r.get('missing'):
        foot = '<div class="note"><h3>数据缺失补充说明</h3><ul>%s</ul></div>' % ''.join(
            '<li><b>%s</b>：缺失 %d 条（%.0f%%），未纳入对应统计<sup>*</sup></li>'
            % (m['field'], m['n'], m['pct']) for m in r['missing'])

    html = """<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
body{{background:#f2f5fa;color:#2b3445;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:0;padding:34px 16px;line-height:1.7}}
.wrap{{max-width:820px;margin:0 auto}}
.paper{{background:#fff;border:1px solid #e4e9f2;border-radius:14px;padding:34px 40px;box-shadow:0 2px 18px rgba(30,60,120,.05)}}
h1{{font-size:23px;color:#1f2d4d;margin:0 0 6px;letter-spacing:.5px}} h2{{font-size:13px;color:#5b7fff;font-weight:600;margin:26px 0 10px}}
h3{{font-size:16px;color:#1f2d4d;margin:20px 0 8px;padding-left:10px;border-left:4px solid #5b7fff}}
p{{margin:6px 0;font-size:13.5px;color:#3a465e}}
.sub{{color:#7c8aa5;font-size:12px;margin-bottom:14px;border-bottom:1px solid #eef1f8;padding-bottom:12px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:16px 0}}
.kpi{{background:#f7f9fd;border:1px solid #e6ebf5;border-radius:10px;padding:14px}}
.kpi .v{{font-size:20px;font-weight:700;color:#1f2d4d}} .kpi .l{{font-size:11px;color:#7c8aa5;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:12.8px;margin:8px 0}}
th{{background:#f3f6fb;color:#33415c;text-align:left;padding:8px 10px;font-weight:600}} td{{padding:7px 10px;border-bottom:1px solid #eef1f8}}
ul{{padding-left:18px;font-size:13.5px;color:#3a465e}} li{{margin:5px 0}}
.note{{background:#fff8ef;border:1px solid #f3d9b0;border-radius:10px;padding:14px 18px;margin-top:22px;font-size:13px;color:#6b5a3a}}
.note sup{{color:#d9912f}} .tag{{display:inline-block;font-size:11px;color:#5b7fff;background:#eef3ff;border:1px solid #cdd9f7;border-radius:20px;padding:2px 10px;margin-left:8px;vertical-align:middle}}
.dc{{background:#f8faff;border:1px solid #dbe4f7;border-radius:10px;padding:14px 18px;margin:14px 0}} .dc p{{margin:6px 0}}
.warn{{background:#fef2f2;border:1px solid #f5c6c8;border-radius:10px;padding:12px 16px;margin:14px 0;font-size:13.5px;color:#a24a4e}}
.sum{{background:#eefaf6;border:1px solid #b5e6d6;border-radius:10px;padding:12px 16px;margin:14px 0;font-size:14px;color:#1f5c4a}}
.note2{{color:#7c8aa5;font-size:12px}} .dc table{{font-size:12.3px}}
@media print{{body{{background:#fff}} .paper{{border:none;box-shadow:none;padding:0}}}}
</style></head><body><div class="wrap"><div class="paper">
<h1>{title}<span class="tag">已脱敏 {level}</span></h1>
<div class="sub">生成时间 {ts} · 数据 {rows} 条 · 覆盖月份 {months}</div>
{sections}
{foot}
</div></div></body></html>""".format(
        title=title, level=r.get('level', 'L0'), ts='2026-08-16', rows=r.get('rows', 0),
        months=' / '.join(r.get('months', [])), sections='\n'.join(sec), foot=foot)
    return html


def render_pdf(r, title='经营分析报告', out_path=None):
    """渲染为 PDF 报告（reportlab + 中文字体，需 pip install reportlab）。
    中文字体按系统可用性注册：微软雅黑(msyh.ttc)/黑体(simhei.ttf)；无则回退英文。"""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    font = 'Helvetica'
    for cand, name in (('C:/Windows/Fonts/msyh.ttc', 'MSYH'),
                       ('C:/Windows/Fonts/simhei.ttf', 'SimHei'),
                       ('/System/Library/Fonts/PingFang.ttc', 'PingFang')):
        if os.path.exists(cand):
            try:
                pdfmetrics.registerFont(TTFont(name, cand, subfontIndex=0)
                                        if cand.endswith('.ttc') else TTFont(name, cand))
                font = name
                break
            except Exception:
                continue

    st = getSampleStyleSheet()
    st['Title'].fontName = font
    st['Heading2'].fontName = font
    st['BodyText'].fontName = font
    st['Title'].fontSize = 18
    st['Heading2'].fontSize = 13
    st['Heading2'].spaceBefore = 12
    st['BodyText'].fontSize = 10.5

    def money(v):
        return '¥{:,}'.format(int(v))

    story = [Paragraph(title, st['Title']),
             Paragraph('已脱敏 %s · 数据 %d 条 · 覆盖月份 %s'
                       % (r.get('level', 'L0'), r.get('rows', 0), ' / '.join(r.get('months', []))),
                       st['BodyText']), Spacer(1, 10)]
    # 概览
    kpi = [['总金额', '交易笔数', '客单价', '环比'],
           [money(r.get('total', 0)), r.get('cnt', 0),
            money(r.get('total', 0) / r.get('cnt', 1)),
            ('%+.1f%%' % r['mom']) if r.get('mom') is not None else '—']]
    t = Table(kpi, colWidths=[120, 100, 100, 110])
    t.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), font), ('FONTSIZE', (0, 0), (-1, -1), 10),
                           ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f7')),
                           ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d5dde5')),
                           ('ALIGN', (1, 1), (-1, -1), 'RIGHT')]))
    story += [t, Spacer(1, 8)]
    # 月度走势
    story.append(Paragraph('一、月度走势', st['Heading2']))
    mtab = [['月份', '金额', '笔数']] + [[m, money(v), r['month_cnt'].get(m, 0)]
                                          for m, v in r.get('month_amt', {}).items()]
    t = Table(mtab, colWidths=[120, 150, 100])
    t.setStyle(TableStyle([('FONTNAME', (0, 0), (-1, -1), font), ('FONTSIZE', (0, 0), (-1, -1), 10),
                           ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#eef2f7')),
                           ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d5dde5'))]))
    story.append(t)
    # 构成
    story.append(Paragraph('二、构成分析', st['Heading2']))
    for dt in r.get('dims_top', []):
        if dt['top']:
            items = '、'.join('「%s」占 %.1f%%' % (n, p) for n, a, p in dt['top'])
            story.append(Paragraph('<b>%s</b>：%s' % (dt['label'], items), st['BodyText']))
    # 地区
    if r.get('region_top'):
        items = '、'.join('「%s」%.1f%%' % (n, p) for n, a, p in r['region_top'])
        story.append(Paragraph('三、%s分布：%s' % (r.get('region_label', '区域'), items), st['Heading2']))
    # 建议
    story.append(Paragraph('四、行动建议', st['Heading2']))
    for tip in r.get('tips', []):
        story.append(Paragraph('· ' + tip, st['BodyText']))
    # 文末缺失说明
    if r.get('missing'):
        story.append(Paragraph('五、数据缺失补充说明', st['Heading2']))
        for m in r['missing']:
            story.append(Paragraph('· %s：缺失 %d 条（%.0f%%），未纳入对应统计*'
                                   % (m['field'], m['n'], m['pct']), st['BodyText']))
    SimpleDocTemplate(out_path, pagesize=A4, topMargin=36, bottomMargin=36).build(story)
    return out_path


def render_md(r, title='经营分析决策简报'):
    """渲染为 Markdown 决策简报（对齐 Data Analysis 的决策简报模板：决策问题→答案→证据→置信度→注意事项→行动清单）。"""
    L = []
    L.append('# %s' % title)
    L.append('')
    L.append('> 生成日期：%s · 数据 %d 条 · 覆盖月份 %s · 已脱敏 %s' % (
        '2026-08-17', r.get('rows', 0), ' / '.join(r.get('months', [])), r.get('level', 'L0')))
    # 数据口径溯源
    if r.get('sources'):
        L.append('')
        L.append('> 📋 数据口径：合并 %d 份来源（%s）→ 去重后 %d 条明细。'
                 % (len(r['sources']), '、'.join(r['sources']), r.get('rows', 0)))
    # 数据完整性预检（对齐 DA"数据窗口假象"）
    _inc = r.get('integrity') or {}
    # 一句话结论（放最前）
    _dp = r.get('deep') or {}
    if _dp.get('summary'):
        L.append('')
        L.append('> 📌 **一句话结论**：%s' % _dp['summary'])
    if _inc.get('incomplete_month'):
        L.append('')
        L.append('> ⚠️ **数据完整性预检**：最新月份 %s 数据仅覆盖至 %02d 日（%d 笔），该月不完整——'
                 '原始环比 %+.1f%% 可能为**数据窗口假象**；最近完整月环比（%s→%s）为 %+.1f%%。'
                 % (_inc['incomplete_month'], _inc.get('days_covered', 0),
                    r['month_cnt'].get(_inc['incomplete_month'], 0), r.get('mom') or 0,
                    _inc.get('last_full_pair', ('—', '—'))[0], _inc.get('last_full_pair', ('—', '—'))[1],
                    _inc.get('last_full_mom') or 0))
    L.append('')
    if not r.get('decisions'):
        L.append('（数据量过小或无明显决策点，仅给出描述性概览）')
    for i, dc in enumerate(r['decisions'], 1):
        L.append('## 决策 %d：%s' % (i, dc['q']))
        L.append('')
        L.append('**简短答案**：%s' % dc['ans'])
        L.append('')
        L.append('**置信度**：%s（%s）' % (dc['conf'], dc.get('reason', '')))
        L.append('')
        L.append('**注意事项（什么会改变结论）**：')
        for n in dc.get('notes', []):
            L.append('- %s' % n)
        L.append('')
        L.append('**下一步行动**：')
        L.append('| 行动 | 负责人 | 期限 | 预期收益 |')
        L.append('|---|---|---|---|')
        for a in dc.get('actions', []):
            L.append('| %s | %s | %s | %s |' % (a['action'], a['owner'], a['due'], a.get('benefit', '')))
        L.append('')
    # 深度分析（文字叙述为主、表格为辅）
    _dp = r.get('deep') or {}
    if _dp.get('cross') or _dp.get('drivers') or _dp.get('insights'):
        L.append('## 深度分析')
        L.append('')
        if _dp.get('cross'):
            top3 = _dp['cross'][:3]
            items = '、'.join('「%s→%s」%s（%.1f%%）' % (c['k1'], c['k2'], money_fn(c['a']), c['pct']) for c in top3)
            L.append('**交叉结构**：主力组合集中于 %s，反映核心客群与主打产品的高度绑定。' % items)
            L.append('')
        if _dp.get('drivers'):
            d0 = _dp['drivers'][0]
            pos = [('「%s」%s' % (k, ('+%s' % money_fn(v)) if v >= 0 else ('-%s' % money_fn(-v)))) for k, v in d0['top'][:2]]
            L.append('**增长/下滑驱动**：环比变动主要由 %s 贡献；分维度看，%s。' % (
                '、'.join(pos),
                '；'.join('%s 维度：%s' % (dr['key'],
                          '、'.join('「%s」%s' % (k, ('+%s' % money_fn(v)) if v >= 0 else ('-%s' % money_fn(-v)))
                                    for k, v in dr['top'][:2])) for dr in _dp['drivers'][1:])))
            L.append('')
        if _dp.get('signer_matrix'):
            st_txt = '；'.join('「%s」%s' % (s['s'], s.get('status', '')) for s in _dp['signer_matrix'])
            dep_txt = ''
            if sum(_dp['signer_matrix'][0]['by_month'].values()) / max(r.get('total', 1), 1) > 0.4:
                dep_txt = '；Top1「%s」累计贡献 %.0f%%，存在单点依赖风险' % (
                    _dp['signer_matrix'][0]['s'],
                    sum(_dp['signer_matrix'][0]['by_month'].values()) / max(r.get('total', 1), 1) * 100)
            L.append('**签单人表现**：%s%s。' % (st_txt, dep_txt))
            L.append('')
        if _dp.get('price_bands'):
            pj = _dp.get('price_segments') or {}
            seg_txt = '、'.join('「%s」%d 笔' % (k, v) for k, v in _dp['price_bands'].items())
            pj_txt = ''
            if pj:
                pj_txt = '客单中位 %s、P75 %s、均值 %s，高客单段（>P75）占 %.0f%%%s。' % (
                    money_fn(pj.get('p50', 0)), money_fn(pj.get('p75', 0)), money_fn(pj.get('mean', 0)),
                    pj.get('high_ratio', 0),
                    '，客单结构整体偏高' if pj.get('high_ratio', 0) >= 40 else ('，客单中位低于均值，存在右偏' if pj.get('mean', 0) > pj.get('p50', 0) else ''))
            L.append('**客单结构**：%s %s' % (seg_txt, pj_txt))
            L.append('')
        if _dp.get('teacher'):
            fb = _dp.get('teacher_fallback') or []
            t_txt = '、'.join('「%s」%s（%.0f%%）' % (t['name'], money_fn(t['a']), t['pct']) for t in _dp['teacher'][:3])
            dep = _dp.get('teacher_dep', 0)
            L.append('**服务人员结构**：头部服务人员：%s%s%s。' % (
                t_txt,
                ('；Top1 依赖度 %.0f%%，存在单点依赖' % dep) if dep >= 30 else '',
                ('；「%s」为兜底标签，建议拆分口径' % fb[0]) if fb else ''))
            L.append('')
        if _dp.get('campus'):
            c_txt = '、'.join('「%s」%s（%.0f%%）' % (c['name'], money_fn(c['a']), c['pct']) for c in _dp['campus'][:3])
            new_txt = ('；新增场所：%s' % '、'.join(_dp['campus_new'])) if _dp.get('campus_new') else ''
            L.append('**场所/门店结构**：头部场所：%s。%s。' % (c_txt, new_txt))
            L.append('')
        if _dp.get('expansion'):
            ex = _dp['expansion']
            prev_txt = ''
            if ex.get('prev_a'):
                prev_txt = '；环比上月 %d 笔 %s，单数增长 %.0f 倍' % (
                    ex['prev_n'], money_fn(ex['prev_a']),
                    ex['n'] / ex['prev_n'] if ex.get('prev_n') else 0)
            topc = '、'.join('「%s」%s' % (n, money_short(v)) for n, v in ex.get('top_c', []))
            L.append('**「%s」专项**：本月 %d 笔 %s，占 %.1f%%%s，集中于 %s——属于高价值增量，建议持续加码。' % (
                ex['kw'], ex['n'], money_fn(ex['a']), ex['pct'], prev_txt, topc))
            L.append('')
        # 本月亮点
        if _dp.get('highlights'):
            L.append('**本月亮点**：')
            for i in _dp['highlights']:
                L.append('- ✅ %s' % i)
            L.append('')
        # 风险注意点
        if _dp.get('concerns'):
            L.append('**风险注意点**：')
            for i in _dp['concerns']:
                L.append('- ⚠️ %s' % i)
            L.append('')
        # 主营结构变化
        if _dp.get('cat_change'):
            cc = _dp['cat_change']
            items = '、'.join('「%s」%s（上月 %s，%s）' % (
                t['name'], money_fn(t['cur']), money_fn(t['prev']),
                '新上榜' if t['is_new'] else t['move']) for t in cc['top'])
            L.append('**主营结构变化（%s → %s）**：%s。' % (cc['pair'][0], cc['pair'][1], items))
            L.append('')
        # 最新月开局解读
        if _dp.get('opening'):
            op = _dp['opening']
            pace_txt = ('；%s' % op['pace']) if op.get('pace') else ''
            L.append('**%s开局解读**：截至当前已有 %d 笔 %s，构成：%s；来源：%s。%s' % (
                op['month'][:7], op['n'], money_fn(op['a']), op['top_c'], op['top_src'], pace_txt.strip('；')))
            L.append('')
        if _dp.get('insights'):
            L.append('**结构洞察**：')
            for i in _dp['insights']:
                L.append('- %s' % i)
            L.append('')
    # 关键指标附录
    L.append('## 附：关键指标')
    L.append('| 指标 | 数值 |')
    L.append('|---|---|')
    L.append('| 总金额 | %s |' % money_fn(r.get('total', 0)))
    L.append('| 交易笔数 | %s |' % r.get('cnt', 0))
    L.append('| 客单价 | %s |' % money_fn(r.get('total', 0) / max(r.get('cnt', 1), 1)))
    if r.get('mom') is not None:
        L.append('| 最近环比 | %+.1f%% |' % r['mom'])
    for dt in r.get('dims_top', [])[:1]:
        if dt['top']:
            L.append('| %s 头部集中 CR1 | 「%s」%.0f%% |' % (dt['label'], dt['top'][0][0], dt['top'][0][2]))
    if r.get('region_top'):
        L.append('| %s 集中 CR1 | 「%s」%.0f%% |' % (r.get('region_label', '区域'), r['region_top'][0][0], r['region_top'][0][2]))
    if r.get('missing'):
        L.append('| 数据缺失 | %d 个字段（详见 * 说明） |' % len(r['missing']))
    L.append('')
    L.append('---')
    L.append('*本简报由 viz-universal 规则引擎生成；置信度为统计层面判断，业务决策请结合外部信息。*')
    return '\n'.join(L)


def main():
    import argparse
    ap = argparse.ArgumentParser(description='生成经营分析报告（规则引擎，离线）')
    ap.add_argument('-i', '--input', required=True, help='anonymize 产出的 masked JSON')
    ap.add_argument('-o', '--output', required=True, help='输出报告 HTML 路径')
    ap.add_argument('--title', default='经营分析报告', help='报告标题')
    args = ap.parse_args()
    data = json.load(open(args.input, encoding='utf-8'))
    r = analyze(data)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(render_html(r, args.title))
    print('✔ 报告已生成 %s（%d 条数据）' % (args.output, r.get('rows', 0)))


if __name__ == '__main__':
    main()

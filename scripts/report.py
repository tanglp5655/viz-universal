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
            {'action': '拉取 %s 全月数据，重建连续月度曲线（当前仅覆盖至 %02d 日）'
                       % (inc['incomplete_month'], inc.get('days_covered', 0)) if fake_warning
                       else '补齐完整月份/年度数据，重建连续月度曲线',
             'owner': '数据负责人', 'due': '1 周内'},
            {'action': '定位峰值月的驱动因素（活动/渠道/大单）', 'owner': '运营负责人', 'due': '2 周内'},
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
                    {'action': '评估拓展次优维度（占比第 2/3 名）的投入', 'owner': '业务负责人', 'due': '2 周内'},
                    {'action': '监控头部维度份额变化，设置集中度预警线', 'owner': '数据负责人', 'due': '1 个月内'},
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
                {'action': '评估次优区域的单客户价值 vs 主区域获客成本', 'owner': '增长负责人', 'due': '2 周内'},
                {'action': '试点 1-2 个次优区域的投放验证', 'owner': '运营负责人', 'due': '1 个月内'},
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
                {'action': '在源头系统补充缺失字段的采集', 'owner': '数据负责人', 'due': '1 个月内'},
                {'action': '对缺失率>20%% 的字段建立质量看板', 'owner': '数据负责人', 'due': '1 个月内'},
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
        sec.append('<h3>一、月度走势</h3><table><tr><th>月份</th><th>金额</th><th>笔数</th></tr>%s</table>' % rows_m)
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

    # 深度分析（交叉 / 驱动分解 / 签单人矩阵 / 结构洞察）
    _dp = r.get('deep') or {}
    dsec = []
    if _dp.get('cross'):
        dsec.append('<h3>六、交叉分析（来源 × 项目 Top 组合）</h3><table><tr><th>组合</th><th>金额</th><th>占比</th></tr>%s</table>'
                    % ''.join('<tr><td>%s → %s</td><td>%s</td><td>%.1f%%</td></tr>'
                              % (c['k1'], c['k2'], money_fn(c['a']), c['pct']) for c in _dp['cross']))
    if _dp.get('drivers'):
        dsec.append('<h3>七、环比驱动分解（%s → %s）</h3>'
                    % (_dp['drivers'][0]['pair'][0], _dp['drivers'][0]['pair'][1]))
        for dr in _dp['drivers']:
            items = '、'.join('「%s」%s' % (k, ('+%s' % money_fn(v)) if v >= 0 else ('-%s' % money_fn(-v)))
                              for k, v in dr['top'])
            dsec.append('<p><b>%s</b>：%s</p>' % (dr['key'], items))
    if _dp.get('signer_matrix'):
        rows_m = ''.join('<tr><td>%s</td>%s<td>%s</td></tr>' % (
            s['s'], ''.join('<td>%s</td>' % money_fn(s['by_month'].get(m, 0)) for m in r.get('months', [])),
            s.get('status', ''))
            for s in _dp['signer_matrix'])
        dsec.append('<h3>八、签单人月度贡献（含个人状态）</h3><table><tr><th>签单人</th>%s<th>状态</th></tr>%s</table>'
                    % (''.join('<th>%s</th>' % m for m in r.get('months', [])), rows_m))
    # 客单分位段
    if _dp.get('price_bands'):
        bands = ''.join('<tr><td>%s</td><td>%d 笔</td></tr>' % (k, v) for k, v in _dp['price_bands'].items())
        pj = _dp.get('price_segments') or {}
        pj_txt = ''
        if pj:
            pj_txt = '<p class="note2">客单中位 %s / P75 %s / 均值 %s；高客单段（>P75）占 %.0f%%</p>' % (
                money_fn(pj.get('p50', 0)), money_fn(pj.get('p75', 0)), money_fn(pj.get('mean', 0)), pj.get('high_ratio', 0))
        dsec.append('<h3>客单结构</h3><table><tr><th>客单段</th><th>笔数</th></tr>%s</table>%s' % (bands, pj_txt))
    # 老师结构
    if _dp.get('teacher'):
        trows = ''.join('<tr><td>%s%s</td><td>%s</td><td>%.0f%%</td></tr>' % (
            t['name'], '（兜底标签）' if t['name'] in (_dp.get('teacher_fallback') or []) else '',
            money_fn(t['a']), t['pct']) for t in _dp['teacher'])
        dsec.append('<h3>服务人员结构</h3><table><tr><th>人员</th><th>金额</th><th>占比</th></tr>%s</table>' % trows)
    # 校区维度
    if _dp.get('campus'):
        crows = ''.join('<tr><td>%s</td><td>%s</td><td>%.0f%%</td></tr>' % (c['name'], money_fn(c['a']), c['pct'])
                        for c in _dp['campus'])
        new_txt = ''
        if _dp.get('campus_new'):
            new_txt = '<p class="note2">新增：%s</p>' % '、'.join(_dp['campus_new'])
        dsec.append('<h3>场所/门店结构</h3><table><tr><th>场所</th><th>金额</th><th>占比</th></tr>%s</table>%s'
                    % (crows, new_txt))
    # 扩科专项
    if _dp.get('expansion'):
        ex = _dp['expansion']
        prev_txt = ''
        if ex.get('prev_a'):
            prev_txt = '（上月 %d 笔 %s，单数增长 %.0f 倍）' % (
                ex['prev_n'], money_fn(ex['prev_a']),
                ex['n'] / ex['prev_n'] if ex.get('prev_n') else 0)
        topc = '、'.join('「%s」%s' % (n, money_short(v)) for n, v in ex.get('top_c', []))
        dsec.append('<h3>「%s」专项</h3><p>本月 %d 笔 %s，占 %.1f%%%s；科目：%s。</p>'
                    % (ex['kw'], ex['n'], money_fn(ex['a']), ex['pct'], prev_txt, topc))
    if _dp.get('insights'):
        dsec.append('<h3>九、结构洞察</h3><ul>%s</ul>'
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
            dsec.append('<table><tr><th>下一步行动</th><th>负责人</th><th>期限</th></tr>%s</table>'
                        % ''.join('<tr><td>%s</td><td>%s</td><td>%s</td></tr>'
                                  % (a['action'], a['owner'], a['due']) for a in dc.get('actions', [])))
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
body{{background:#0b1219;color:#c8d6e5;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;margin:0;padding:32px 16px;line-height:1.7}}
.wrap{{max-width:760px;margin:0 auto}}
h1{{font-size:22px;color:#fff;margin:0 0 4px}} h2{{font-size:14px;color:#5b7fff;font-weight:600;margin:28px 0 10px;border-left:3px solid #5b7fff;padding-left:10px}}
h3{{font-size:16px;color:#fff;margin:22px 0 8px}}
p{{margin:6px 0;font-size:14px}} .sub{{color:#7d93a8;font-size:12px;margin-bottom:18px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:18px 0}}
.kpi{{background:#13202e;border:1px solid rgba(90,140,220,.14);border-radius:12px;padding:14px}}
.kpi .v{{font-size:18px;font-weight:700;color:#fff}} .kpi .l{{font-size:11px;color:#7d93a8;margin-top:4px}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin:8px 0}}
th{{background:#13202e;color:#9fb4c9;text-align:left;padding:8px 10px}} td{{padding:7px 10px;border-bottom:1px solid rgba(255,255,255,.05)}}
ul{{padding-left:18px;font-size:14px}} li{{margin:5px 0}}
.note{{background:rgba(255,184,108,.06);border:1px solid rgba(255,184,108,.25);border-radius:12px;padding:14px 18px;margin-top:26px;font-size:13px}}
.note sup{{color:#ffb86c}} .tag{{display:inline-block;font-size:11px;color:#ffb86c;border:1px solid rgba(255,184,108,.4);border-radius:20px;padding:2px 10px;margin-left:8px;vertical-align:middle}}
.dc{{background:rgba(91,127,255,.05);border:1px solid rgba(91,127,255,.22);border-radius:12px;padding:14px 18px;margin:14px 0}} .dc p{{margin:6px 0}}
.warn{{background:rgba(232,118,122,.08);border:1px solid rgba(232,118,122,.4);border-radius:12px;padding:12px 16px;margin:14px 0;font-size:13.5px;color:#e8b4b7}}
.sum{{background:rgba(79,208,192,.07);border:1px solid rgba(79,208,192,.35);border-radius:12px;padding:12px 16px;margin:14px 0;font-size:14px}}
.note2{{color:#7d93a8;font-size:12px}} .dc table{{font-size:12.5px}}
@media print{{body{{background:#fff;color:#222}}.kpi{{background:#f3f6fa;border-color:#dfe6ee}}.kpi .v{{color:#111}}h1,h3{{color:#111}}th{{background:#f3f6fa;color:#445}}}}
</style></head><body><div class="wrap">
<h1>{title}<span class="tag">已脱敏 {level}</span></h1>
<div class="sub">生成时间 {ts} · 数据 {rows} 条 · 覆盖月份 {months}</div>
{sections}
{foot}
</div></body></html>""".format(
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
        L.append('| 行动 | 负责人 | 期限 |')
        L.append('|---|---|---|')
        for a in dc.get('actions', []):
            L.append('| %s | %s | %s |' % (a['action'], a['owner'], a['due']))
        L.append('')
    # 深度分析（交叉/驱动/矩阵/洞察）
    _dp = r.get('deep') or {}
    if _dp.get('cross') or _dp.get('drivers') or _dp.get('insights'):
        L.append('## 深度分析')
        L.append('')
        if _dp.get('cross'):
            L.append('**交叉组合（来源 × 项目 Top6）**：')
            L.append('| 组合 | 金额 | 占比 |')
            L.append('|---|---|---|')
            for c in _dp['cross']:
                L.append('| %s → %s | %s | %.1f%% |' % (c['k1'], c['k2'], money_fn(c['a']), c['pct']))
            L.append('')
        if _dp.get('drivers'):
            L.append('**环比驱动分解（%s → %s）**：' % (_dp['drivers'][0]['pair'][0], _dp['drivers'][0]['pair'][1]))
            for dr in _dp['drivers']:
                items = '、'.join('「%s」%s' % (k, ('+%s' % money_fn(v)) if v >= 0 else ('-%s' % money_fn(-v)))
                                  for k, v in dr['top'])
                L.append('- %s：%s' % (dr['key'], items))
            L.append('')
        if _dp.get('signer_matrix'):
            L.append('**签单人月度贡献（含个人状态）**：')
            L.append('| 签单人 | %s | 状态 |' % ' | '.join(r.get('months', [])))
            L.append('|---|%s|---|' % '---|' * len(r.get('months', [])))
            for s in _dp['signer_matrix']:
                L.append('| %s | %s | %s |' % (
                    s['s'], ' | '.join(money_fn(s['by_month'].get(m, 0)) for m in r.get('months', [])),
                    s.get('status', '')))
            L.append('')
        if _dp.get('price_bands'):
            L.append('**客单结构**：')
            for k, v in _dp['price_bands'].items():
                L.append('- %s：%d 笔' % (k, v))
            pj = _dp.get('price_segments') or {}
            if pj:
                L.append('- 客单中位 %s / P75 %s / 均值 %s；高客单段（>P75）占 %.0f%%'
                         % (money_fn(pj.get('p50', 0)), money_fn(pj.get('p75', 0)),
                            money_fn(pj.get('mean', 0)), pj.get('high_ratio', 0)))
            L.append('')
        if _dp.get('teacher'):
            L.append('**服务人员结构**：')
            for t in _dp['teacher']:
                fb = '（兜底标签）' if t['name'] in (_dp.get('teacher_fallback') or []) else ''
                L.append('- %s%s：%s（%.0f%%）' % (t['name'], fb, money_fn(t['a']), t['pct']))
            L.append('')
        if _dp.get('campus'):
            L.append('**场所/门店结构**：')
            for c in _dp['campus']:
                L.append('- %s：%s（%.0f%%）' % (c['name'], money_fn(c['a']), c['pct']))
            if _dp.get('campus_new'):
                L.append('- 新增：%s' % '、'.join(_dp['campus_new']))
            L.append('')
        if _dp.get('expansion'):
            ex = _dp['expansion']
            prev_txt = ''
            if ex.get('prev_a'):
                prev_txt = '（上月 %d 笔 %s，单数增长 %.0f 倍）' % (
                    ex['prev_n'], money_fn(ex['prev_a']),
                    ex['n'] / ex['prev_n'] if ex.get('prev_n') else 0)
            topc = '、'.join('「%s」%s' % (n, money_short(v)) for n, v in ex.get('top_c', []))
            L.append('**「%s」专项**：本月 %d 笔 %s，占 %.1f%%%s；科目：%s。' % (
                ex['kw'], ex['n'], money_fn(ex['a']), ex['pct'], prev_txt, topc))
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

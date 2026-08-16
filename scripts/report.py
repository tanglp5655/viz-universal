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

    # 环比
    prev, cur = None, None
    if len(months) >= 2:
        prev, cur = month_amt[months[-2]], month_amt[months[-1]]
    r['mom'] = _pct(cur, prev) if cur is not None else None

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
    return r


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

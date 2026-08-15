# -*- coding: utf-8 -*-
"""无障碍审计：检查主题库各主题的文字/背景对比度是否达到 WCAG AA（正文 ≥4.5:1）。

用法:
  python scripts/audit_accessibility.py          # 审计全部主题
  python scripts/audit_accessibility.py --json   # 输出 JSON 报告

退出码: 0 = 全部达标；1 = 存在不达标项。
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from themes import THEMES  # noqa: E402

AA_TEXT = 4.5
AA_LARGE = 3.0
HEX_RE = re.compile(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$')


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexc):
    """WCAG 相对亮度（0~1）。仅支持 #rgb/#rrggbb；rgba/渐变返回 None。"""
    hexc = (hexc or '').strip()
    if not HEX_RE.match(hexc):
        return None
    hexc = hexc.lstrip('#')
    if len(hexc) == 3:
        hexc = ''.join(c * 2 for c in hexc)
    r, g, b = int(hexc[0:2], 16) / 255, int(hexc[2:4], 16) / 255, int(hexc[4:6], 16) / 255
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(fg, bg):
    """WCAG 对比度（≥1）。任一为 None 返回 None。"""
    l1, l2 = luminance(fg), luminance(bg)
    if l1 is None or l2 is None:
        return None
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def _base_bg(bg):
    """背景可能是多层 radial-gradient；取渐变串中最后一个 hex 色作为实际基底色近似。"""
    bg = (bg or '').strip()
    if HEX_RE.match(bg):
        return bg
    hexes = re.findall(r'#[0-9a-fA-F]{6}', bg)
    return hexes[-1] if hexes else None


def audit(theme_id=None):
    """审计全部（或指定）主题，返回逐项报告。
    标准：正文/次要文字 ≥4.5（AA 常规文本），坐标轴 ≥3.0（AA 大文本/UI 组件）。"""
    rows, bad = [], 0
    tids = [theme_id] if theme_id else list(THEMES.keys())
    for tid in tids:
        t = THEMES[tid]
        bg = _base_bg(t.get('bg', '#ffffff'))
        for role, key, limit in (('正文', 'text', AA_TEXT), ('次要', 'text2', AA_TEXT),
                                 ('坐标轴', 'axis', AA_LARGE)):
            fg = t.get(key)
            if not fg:
                continue
            c = contrast(fg, bg) if bg else None
            ok = (c is not None and c >= limit)
            bad += (not ok)
            rows.append({'theme': tid, 'role': role, 'fg': fg, 'bg': bg or t.get('bg', ''),
                         'contrast': round(c, 2) if c is not None else None,
                         'limit': limit,
                         'pass': bool(ok),
                         'note': '' if ok else ('无法解析背景色' if c is None else '对比度不达标')})
    return rows, bad


def main():
    ap = argparse.ArgumentParser(description='主题对比度审计（WCAG AA）')
    ap.add_argument('--json', action='store_true', help='输出 JSON 报告')
    ap.add_argument('--theme', default=None, help='只审计指定主题 id')
    args = ap.parse_args()

    rows, bad = audit(args.theme)
    if args.json:
        print(json.dumps({'rows': rows, 'bad': bad, 'aa_text': AA_TEXT, 'aa_large': AA_LARGE},
                         ensure_ascii=False, indent=1))
    else:
        print('%-14s %-6s %-9s %-9s %-7s %-6s %s' % ('主题', '角色', '前景', '背景', '对比度', '标准', '结果'))
        print('-' * 74)
        for r in rows:
            mark = '✅ 达标' if r['pass'] else ('⚠ %s' % r['note'])
            print('%-14s %-6s %-9s %-9s %-7s %-6s %s' % (
                r['theme'], r['role'], r['fg'], r['bg'],
                ('%.2f' % r['contrast']) if r['contrast'] is not None else '—',
                ('%.1f' % r['limit']), mark))
        print('-' * 74)
        print('不达标项: %d / %d（标准：正文/次要 ≥4.5，坐标轴 ≥3.0）' % (bad, len(rows)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())

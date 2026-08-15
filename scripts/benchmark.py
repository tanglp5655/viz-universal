# -*- coding: utf-8 -*-
"""大数据性能压测：生成 N 行虚构数据 → 脱敏 L2 → 生成（免密/加密）→ 输出 docs/PERFORMANCE.md。

用法:
  python scripts/benchmark.py               # 默认 10 万行
  python scripts/benchmark.py 200000        # 指定行数
"""
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(BASE, 'scripts')
ANON = os.path.join(SCRIPTS, 'anonymize.py')
BUILD = os.path.join(SCRIPTS, 'build_dashboard.py')
PY = sys.executable
OUT_DIR = os.path.join(BASE, 'tests', 'out')
DOC = os.path.join(BASE, 'docs', 'PERFORMANCE.md')


def gen(n, path):
    names = ['客户%d' % i for i in range(2000)]
    courses = ['课程A', '课程B', '课程C', '课程D', '课程E']
    srcs = ['新生', '老生', '转介绍']
    provs = ['浙江省', '广东省', '江苏省', '山东省', '四川省', '湖北省',
             '河南省', '福建省', '湖南省', '陕西省']
    base = datetime(2026, 1, 1)
    rnd = random.Random(42)
    rows = []
    for i in range(n):
        rows.append({
            '报名日期': (base + timedelta(days=rnd.randint(0, 210))).strftime('%Y-%m-%d'),
            '学员姓名': names[rnd.randint(0, len(names) - 1)],
            '课程': courses[rnd.randint(0, 4)],
            '金额': rnd.randint(500, 20000),
            '支付方式': rnd.choice(['微信', '支付宝', '银行卡', '现金']),
            '签单人': '销售%d' % rnd.randint(1, 10),
            '省份': provs[rnd.randint(0, 9)],
            '城市': '市%d' % rnd.randint(1, 20),
            '性别': rnd.choice(['男', '女']),
            '年龄': rnd.randint(5, 18),
        })
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(rows, f, ensure_ascii=False)
    return len(rows)


def run(cmd):
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
    return time.time() - t0, r.returncode


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    os.makedirs(OUT_DIR, exist_ok=True)
    raw, masked = os.path.join(OUT_DIR, 'bench_raw.json'), os.path.join(OUT_DIR, 'bench_masked.json')
    plain_html, enc_html = os.path.join(OUT_DIR, 'bench_plain.html'), os.path.join(OUT_DIR, 'bench_enc.html')

    print('生成 %d 行压测数据…' % n)
    gen(n, raw)
    print('  → 原始文件 %.1f MB' % (os.path.getsize(raw) / 1048576))

    t, rc = run([PY, ANON, '-i', raw, '-o', masked, '--level', 'L2'])
    print('[脱敏 L2] %.1fs rc=%d' % (t, rc))
    t_anon = t

    t, rc = run([PY, BUILD, '-i', masked, '-o', plain_html, '--no-lock', '--title', '压测-免密'])
    print('[生成-免密] %.1fs rc=%d 大小=%.1f MB' % (t, rc, os.path.getsize(plain_html) / 1048576))
    t_plain = t

    t, rc = run([PY, BUILD, '-i', masked, '-o', enc_html, '-p', 'bench123', '--title', '压测-加密'])
    print('[生成-加密] %.1fs rc=%d 大小=%.1f MB' % (t, rc, os.path.getsize(enc_html) / 1048576))
    t_enc = t

    lines = [
        '# 性能基线（PERFORMANCE）',
        '',
        '压测环境：' + sys.platform + ' / Python ' + sys.version.split()[0],
        '压测方式：`python scripts/benchmark.py %d`（虚构数据，固定随机种子可复现）' % n,
        '',
        '| 阶段 | 耗时 | 说明 |',
        '|---|---|---|',
        '| 数据生成 | 即时 | %d 行虚构明细 |' % n,
        '| 脱敏 L2 | %.1fs | 列语义识别 + 编号化 |' % t_anon,
        '| 生成（免密直开） | %.1fs | Chart.js/ECharts/地图内嵌，免加密 |' % t_plain,
        '| 生成（加密） | %.1fs | 含 12 万次密钥迭代 + CTR 加密 |' % t_enc,
        '',
        '产物大小：',
        '- 原始 JSON：%.1f MB' % (os.path.getsize(raw) / 1048576),
        '- 脱敏 JSON：%.1f MB' % (os.path.getsize(masked) / 1048576),
        '- 免密看板：%.1f MB（图表库+地图内嵌占大头，与行数关系小）' % (os.path.getsize(plain_html) / 1048576),
        '- 加密看板：%.1f MB' % (os.path.getsize(enc_html) / 1048576),
        '',
        '## 大数据前端降级策略（已内置）',
        '- 明细表：分页加载（初始 60 行，点「加载更多」+100），不一次性渲染全量。',
        '- 走势图：按月聚合为少量点；维度排行取 Top 60（可加载更多）。',
        '- 地图：按省/市/区聚合，颜色深浅 = 聚合值。',
        '- 演示模式：`--sample N` 随机采样 N 条生成（固定种子可复现），适合超大文件快速出图。',
        '',
        '## 说明',
        '- 加密耗时主要来自 12 万次密钥迭代（固定 ~1-3s）与全量 XOR/Base64（线性）。',
        '- 若需更快：内部联调可用 `--iter 1000`；对外发布请保持默认。',
    ]
    os.makedirs(os.path.dirname(DOC), exist_ok=True)
    with open(DOC, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n✔ 已写入 %s' % DOC)
    return 0


if __name__ == '__main__':
    sys.exit(main())

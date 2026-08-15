# -*- coding: utf-8 -*-
"""
sales-viz-secure · 一键回归测试（多行业）

用法（在技能根目录执行）:
  python test_all_industries.py
  python test_all_industries.py --keep        # 保留 tests/out 产物便于检查
  SVS_NODE="node" python test_all_industries.py

做什么:
  1. 内置 5 个行业的虚构合成数据（generic/education/retail/clinic/b2b）
  2. 对每个行业跑 anonymize.py --industry X --level L2 → build_dashboard.py -p 666
  3. 校验：
     - 支付归并是否符合各行业规则
     - 客户/人员/科目脱敏是否生效（前缀、化名、重映射）
     - 金额合计与输入一致（scale=1 时不应丢改）
     - HTML 加密载体里无任何明文真名/敏感词（泄漏检查）
     - 锁屏 <title> 中性（数据看板）
     - 用 node + crypto.js 真解密：密码 666 能解开、错密码被拦截
  4. 打印 PASS/FAIL 汇总，存在失败则退出码 1

全部数据均为虚构，仅用于自测，不含任何真实业务信息。
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

SKILL_ROOT = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(SKILL_ROOT, "scripts")
CRYPTO_JS = os.path.join(SKILL_ROOT, "assets", "crypto.js")
ANON = os.path.join(SCRIPTS, "anonymize.py")
BUILD = os.path.join(SCRIPTS, "build_dashboard.py")

# node：优先环境变量 SVS_NODE，其次 PATH 中的 node，最后常见托管路径（跨平台）
_NODE_CANDIDATES = [
    r"C:\Users\jiang\.workbuddy\binaries\node\versions\22.12.0\node.exe",
    r"C:\Program Files\nodejs\node.exe",
    "/usr/local/bin/node", "/usr/bin/node", "/opt/homebrew/bin/node",
]
NODE = (os.environ.get("SVS_NODE")
        or shutil.which("node")
        or next((p for p in _NODE_CANDIDATES if os.path.exists(p)), "node"))

PW = "666"  # 与用户样例一致的测试密码

# ---------------- 内置合成数据（全部虚构） ----------------
DATA = {
    "generic": {
        "label": "通用（默认）",
        "rows": [
            {"成交日期": "2026-05-03", "客户名称": "杭州云栖科技", "项目": "年度订阅-专业版", "金额": 88000, "收款方式": "对公转账", "业务员": "周敏", "部门": "华东"},
            {"成交日期": "2026-05-09", "客户名称": "宁波海创", "项目": "实施服务费", "金额": 24000, "收款方式": "银行汇款", "业务员": "周敏", "部门": "华东"},
            {"成交日期": "2026-06-12", "客户名称": "苏州河图", "项目": "增购坐席", "金额": 15600, "收款方式": "微信", "业务员": "李航", "部门": "华东"},
            {"成交日期": "2026-06-20", "客户名称": "无锡星澜", "项目": "年度订阅-旗舰版", "金额": 120000, "收款方式": "电汇", "业务员": "李航", "部门": "华东"},
            {"成交日期": "2026-07-05", "客户名称": "合肥微光", "项目": "定制开发", "金额": 64000, "收款方式": "承兑汇票", "业务员": "王启", "部门": "华中"},
            {"成交日期": "2026-07-18", "客户名称": "武汉江潮", "项目": "咨询项目", "金额": 32000, "收款方式": "对公转账", "业务员": "王启", "部门": "华中"},
            {"成交日期": "2026-08-02", "客户名称": "长沙岳云", "项目": "增购坐席", "金额": 9800, "收款方式": "支付宝", "业务员": "陈露", "部门": "华中"},
            {"成交日期": "2026-08-21", "客户名称": "南昌青松", "项目": "年度订阅-专业版", "金额": 76000, "收款方式": "月结", "业务员": "陈露", "部门": "华中"},
        ],
        # generic：不归并支付、不碰科目，原样保留
        "pay_exp": {"对公转账", "银行汇款", "微信", "电汇", "承兑汇票", "支付宝", "月结"},
        "cust_prefix": "客户",
        "subject_keep": True,
        "leak": ["杭州云栖科技", "宁波海创", "苏州河图", "无锡星澜", "合肥微光", "武汉江潮", "长沙岳云", "南昌青松"],
    },
    "education": {
        "label": "教育培训",
        "rows": [
            {"报名日期": "2026-05-02", "学员姓名": "范亚兰", "校区": "总校", "课程": "数学", "金额": 3200, "支付方式": "x微信", "签单人": "薛经理", "上课老师": "张伟"},
            {"报名日期": "2026-05-08", "学员姓名": "王思远", "校区": "总校", "课程": "英语", "金额": 3600, "支付方式": "现金收款", "签单人": "赵主管", "上课老师": "李娜"},
            {"报名日期": "2026-05-15", "学员姓名": "陈雨欣", "校区": "分校", "课程": "钢琴课", "金额": 4800, "支付方式": "银行转账", "签单人": "薛经理", "上课老师": "王芳"},
            {"报名日期": "2026-06-03", "学员姓名": "刘子涵", "校区": "分校", "课程": "围棋高段班", "金额": 4200, "支付方式": "支付宝(中国)", "签单人": "钱顾问", "上课老师": "张伟"},
            {"报名日期": "2026-06-19", "学员姓名": "杨帆", "校区": "总校", "课程": "托管", "金额": 3200, "支付方式": "微信", "签单人": "赵主管", "上课老师": "李娜"},
            {"报名日期": "2026-07-07", "学员姓名": "黄一鸣", "校区": "总校", "课程": "书法课", "金额": 3600, "支付方式": "对公转账", "签单人": "薛经理", "上课老师": "王芳"},
            {"报名日期": "2026-07-22", "学员姓名": "周倩", "校区": "分校", "课程": "数学", "金额": 2800, "支付方式": "现金", "签单人": "钱顾问", "上课老师": "张伟"},
            {"报名日期": "2026-08-10", "学员姓名": "吴桐", "校区": "分校", "课程": "英语", "金额": 4800, "支付方式": "银行", "签单人": "赵主管", "上课老师": "李娜"},
        ],
        "pay_exp": {"微信", "现金", "银行卡", "支付宝"},
        "cust_prefix": "学员",
        "subject_remap": {  # 期望的科目重映射结果
            "数学": "篮球", "英语": "钢琴", "围棋高段班": "篮球高阶班",
            "托管": "综合素养营", "书法课": "硬笔书法", "钢琴课": "其他兴趣课",
        },
        "leak": ["范亚兰", "王思远", "陈雨欣", "刘子涵", "杨帆", "黄一鸣", "周倩", "吴桐",
                 "张伟", "李娜", "王芳", "数学", "英语", "围棋高段班", "托管", "书法课"],
    },
    "retail": {
        "label": "餐饮零售",
        "rows": [
            {"日期": "2026-05-04", "门店": "中心店", "商品": "招牌牛排套餐", "数量": 12, "金额": 2988, "支付方式": "微信支付", "店员": "小林"},
            {"日期": "2026-05-11", "门店": "中心店", "商品": "海鲜拼盘", "数量": 8, "金额": 1760, "支付方式": "美团", "店员": "小林"},
            {"日期": "2026-05-18", "门店": "滨江店", "商品": "双人下午茶", "数量": 15, "金额": 2250, "支付方式": "支付宝扫码", "店员": "小美"},
            {"日期": "2026-06-02", "门店": "滨江店", "商品": "招牌牛排套餐", "数量": 20, "金额": 4980, "支付方式": "饿了么", "店员": "小美"},
            {"日期": "2026-06-15", "门店": "中心店", "商品": "红酒套餐", "数量": 6, "金额": 1680, "支付方式": "刷卡", "店员": "阿强"},
            {"日期": "2026-06-28", "门店": "滨江店", "商品": "亲子套餐", "数量": 10, "金额": 1980, "支付方式": "抖音", "店员": "小美"},
            {"日期": "2026-07-09", "门店": "中心店", "商品": "海鲜拼盘", "数量": 9, "金额": 1980, "支付方式": "现金", "店员": "阿强"},
            {"日期": "2026-07-25", "门店": "滨江店", "商品": "双人下午茶", "数量": 18, "金额": 2700, "支付方式": "POS", "店员": "小林"},
            {"日期": "2026-08-06", "门店": "中心店", "商品": "亲子套餐", "数量": 14, "金额": 2772, "支付方式": "京东", "店员": "阿强"},
        ],
        "pay_exp": {"微信", "其他", "支付宝", "银行卡", "现金"},
        "cust_prefix": None,  # 零售测试数据无客户列
        "staff_prefix": "店员",
        "subject_keep": True,
        "leak": ["美团", "饿了么", "抖音", "京东", "小林", "小美", "阿强"],
    },
    "clinic": {
        "label": "医疗诊所",
        "rows": [
            {"日期": "2026-05-06", "院区": "总院", "患者": "孙建国", "项目科室": "口腔种植", "金额": 9800, "支付方式": "医保卡", "医师": "高明"},
            {"日期": "2026-05-14", "院区": "总院", "患者": "马秀英", "项目科室": "眼科屈光", "金额": 12800, "支付方式": "微信", "医师": "林涛"},
            {"日期": "2026-05-23", "院区": "分院", "患者": "朱志强", "项目科室": "康复理疗", "金额": 3600, "支付方式": "现金", "医师": "赵慧"},
            {"日期": "2026-06-07", "院区": "分院", "患者": "胡文斌", "项目科室": "口腔种植", "金额": 9800, "支付方式": "支付宝", "医师": "高明"},
            {"日期": "2026-06-19", "院区": "总院", "患者": "郭丽华", "项目科室": "皮肤科", "金额": 5400, "支付方式": "社保", "医师": "林涛"},
            {"日期": "2026-07-03", "院区": "分院", "患者": "何俊杰", "项目科室": "康复理疗", "金额": 3600, "支付方式": "统筹", "医师": "赵慧"},
            {"日期": "2026-07-16", "院区": "总院", "患者": "罗永康", "项目科室": "眼科屈光", "金额": 12800, "支付方式": "医保卡", "医师": "高明"},
            {"日期": "2026-08-01", "院区": "分院", "患者": "梁静", "项目科室": "皮肤科", "金额": 5400, "支付方式": "微信", "医师": "赵慧"},
        ],
        "pay_exp": {"医保", "微信", "现金", "支付宝"},
        "cust_prefix": "患者",
        "staff_prefix": "医师",
        "subject_keep": True,
        "leak": ["孙建国", "马秀英", "朱志强", "胡文斌", "郭丽华", "何俊杰", "罗永康", "梁静",
                 "高明", "林涛", "赵慧", "医保卡", "社保", "统筹"],
    },
    "b2b": {
        "label": "B2B制造",
        "rows": [
            {"签单日期": "2026-05-05", "客户": "中宇重工", "产品": "液压阀组", "金额": 286000, "支付方式": "月结", "销售顾问": "郑涛", "部门": "华北"},
            {"签单日期": "2026-05-17", "客户": "海丰造船", "产品": "船用管路", "金额": 540000, "支付方式": "信用证", "销售顾问": "郑涛", "部门": "华北"},
            {"签单日期": "2026-06-08", "客户": "皖通装备", "产品": "控制柜", "金额": 168000, "支付方式": "承兑汇票", "销售顾问": "冯磊", "部门": "华东"},
            {"签单日期": "2026-06-21", "客户": "鲁泰机械", "产品": "液压阀组", "金额": 232000, "支付方式": "对公转账", "销售顾问": "冯磊", "部门": "华东"},
            {"签单日期": "2026-07-10", "客户": "川渝精密", "产品": "传感器模组", "金额": 94000, "支付方式": "账期", "销售顾问": "韩雪", "部门": "西南"},
            {"签单日期": "2026-07-26", "客户": "滇能电气", "产品": "控制柜", "金额": 176000, "支付方式": "LC", "销售顾问": "韩雪", "部门": "西南"},
            {"签单日期": "2026-08-12", "客户": "黔兴科技", "产品": "传感器模组", "金额": 88000, "支付方式": "支票", "销售顾问": "郑涛", "部门": "西南"},
            {"签单日期": "2026-08-25", "客户": "青蓝重工", "产品": "船用管路", "金额": 610000, "支付方式": "赊销", "销售顾问": "冯磊", "部门": "华东"},
        ],
        "pay_exp": {"月结", "信用证", "承兑汇票", "对公", "支票"},
        "cust_prefix": "客户",
        "subject_keep": True,
        "leak": ["中宇重工", "海丰造船", "皖通装备", "鲁泰机械", "川渝精密", "滇能电气", "黔兴科技", "青蓝重工"],
    },
    "geo": {
        # 含地区层级（省/市/区）+ 性别 + 年龄，用于验证钻取与人物画像
        "label": "地区+画像（通用）",
        "rows": [
            {"日期": "2026-05-02", "客户名称": "锦江商贸", "省份": "四川省", "城市": "成都市", "区": "武侯区", "商品": "智能终端", "金额": 56000, "支付方式": "对公转账", "性别": "男", "年龄": 34},
            {"日期": "2026-05-09", "客户名称": "嘉禾电子", "省份": "四川省", "城市": "绵阳市", "区": "涪城区", "商品": "配件", "金额": 12000, "支付方式": "微信", "性别": "女", "年龄": 28},
            {"日期": "2026-06-03", "客户名称": "云岭科技", "省份": "云南省", "城市": "昆明市", "区": "五华区", "商品": "智能终端", "金额": 78000, "支付方式": "电汇", "性别": "男", "年龄": 45},
            {"日期": "2026-06-18", "客户名称": "滇池实业", "省份": "云南省", "城市": "曲靖市", "区": "麒麟区", "商品": "配件", "金额": 21000, "支付方式": "支付宝", "性别": "女", "年龄": 52},
            {"日期": "2026-07-04", "客户名称": "黔山数据", "省份": "贵州省", "城市": "贵阳市", "区": "南明区", "商品": "云服务", "金额": 64000, "支付方式": "承兑汇票", "性别": "男", "年龄": 39},
            {"日期": "2026-07-21", "客户名称": "筑城网络", "省份": "贵州省", "城市": "遵义市", "区": "汇川区", "商品": "云服务", "金额": 33000, "支付方式": "月结", "性别": "女", "年龄": 31},
            {"日期": "2026-08-08", "客户名称": "蜀道物流", "省份": "四川省", "城市": "成都市", "区": "锦江区", "商品": "智能终端", "金额": 92000, "支付方式": "对公转账", "性别": "男", "年龄": 48},
            {"日期": "2026-08-22", "客户名称": "彩云商贸", "省份": "云南省", "城市": "昆明市", "区": "盘龙区", "商品": "配件", "金额": 15000, "支付方式": "微信", "性别": "女", "年龄": 26},
        ],
        "pay_exp": {"对公转账", "微信", "电汇", "支付宝", "承兑汇票", "月结"},
        "cust_prefix": "客户",
        "subject_keep": True,
        "leak": ["锦江商贸", "嘉禾电子", "云岭科技", "滇池实业", "黔山数据", "筑城网络", "蜀道物流", "彩云商贸"],
    },
}


# ---------------- 结果收集 ----------------
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    mark = "✔" if cond else "✘"
    line = f"  {mark} {name}"
    if detail:
        line += f"  — {detail}"
    print(line)


def run_py(script, args, cwd=None):
    cmd = [sys.executable, script] + args
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p


def extract_payload(html_text):
    m = re.search(r"var PAYLOAD = (\{[^}]*\});", html_text)
    if not m:
        return None
    return json.loads(m.group(1))


NODE_RUNNER = """const fs = require('fs');
const cryptoJs = process.argv[2];
const payload = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const pw = process.argv[4];
const code = fs.readFileSync(cryptoJs, 'utf8');
eval(code);
SVS.unlock(payload, pw).then(function (t) {
  process.stdout.write('DECRYPT_OK:' + t.length);
}).catch(function (e) {
  process.stdout.write('DECRYPT_FAIL:' + e);
});
"""

# 回传完整解密 JSON（用于校验 meta 里的地区/性别/年龄结构）
NODE_RUNNER_FULL = """const fs = require('fs');
const cryptoJs = process.argv[2];
const payload = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const pw = process.argv[4];
const out = process.argv[5];
const code = fs.readFileSync(cryptoJs, 'utf8');
eval(code);
SVS.unlock(payload, pw).then(function (t) {
  fs.writeFileSync(out, t);
  process.stdout.write('OK');
}).catch(function (e) {
  process.stdout.write('FAIL' + e);
});
"""


def raw_subject(row):
    """从原始行取出科目/商品/产品对应的原始值（不同行业列名不同）。"""
    for k in ("项目", "商品", "产品", "课程", "项目科室", "病种", "诊断", "科目", "报名科目"):
        if k in row:
            return row[k]
    return None


def safe_rmtree(path):
    """沙箱环境下 rmtree 可能被 safe-delete 拦截，best-effort 容错。"""
    try:
        shutil.rmtree(path)
    except OSError:
        pass


def node_decrypt(payload, pw, node_runner_path):
    d = os.path.dirname(node_runner_path)
    pl = os.path.join(d, "_payload.json")
    with open(pl, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False)
    p = subprocess.run([NODE, node_runner_path, CRYPTO_JS, pl, pw],
                       capture_output=True, text=True, timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    if out.startswith("DECRYPT_OK:"):
        return "OK", out
    if out.startswith("DECRYPT_FAIL:"):
        return "FAIL", out
    return "ERR", out


def node_decrypt_full(payload, pw, node_runner_full, out_path):
    d = os.path.dirname(node_runner_full)
    pl = os.path.join(d, "_payload.json")
    with open(pl, "w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False)
    p = subprocess.run([NODE, node_runner_full, CRYPTO_JS, pl, pw, out_path],
                       capture_output=True, text=True, timeout=180)
    out = (p.stdout or "") + (p.stderr or "")
    if out.startswith("OK") and os.path.exists(out_path):
        return json.load(open(out_path, encoding="utf-8"))
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="保留 tests/out 产物")
    args = ap.parse_args()

    out_dir = os.path.join(SKILL_ROOT, "tests", "out")
    os.makedirs(out_dir, exist_ok=True)
    node_runner = os.path.join(out_dir, "_node_check.js")
    with open(node_runner, "w", encoding="utf-8") as fp:
        fp.write(NODE_RUNNER)
    node_runner_full = os.path.join(out_dir, "_node_check_full.js")
    with open(node_runner_full, "w", encoding="utf-8") as fp:
        fp.write(NODE_RUNNER_FULL)

    node_ok = os.path.exists(NODE) and shutil.which(NODE) is not None or os.path.exists(NODE)
    print("=" * 64)
    print("sales-viz-secure 多行业回归测试")
    print(f"node: {NODE}  ({'可用' if os.path.exists(NODE) else '缺失，跳过真解密校验'})")
    print("=" * 64)

    for ind, cfg in DATA.items():
        print(f"\n### [{ind}] {cfg['label']}")
        in_path = os.path.join(out_dir, f"{ind}_input.json")
        masked_path = os.path.join(out_dir, f"{ind}_masked.json")
        map_path = os.path.join(out_dir, f"{ind}_map.json")
        html_path = os.path.join(out_dir, f"{ind}_看板.html")

        with open(in_path, "w", encoding="utf-8") as fp:
            json.dump(cfg["rows"], fp, ensure_ascii=False, indent=1)

        # 1) 脱敏
        p = run_py(ANON, ["-i", in_path, "-o", masked_path, "--industry", ind,
                          "--level", "L2", "--mapping-out", map_path])
        if p.returncode != 0:
            check(f"{ind}: anonymize 执行", False, p.stderr.strip().splitlines()[-1])
            continue
        check(f"{ind}: anonymize 执行", True)

        masked = json.load(open(masked_path, encoding="utf-8"))
        rows = masked["rows"]

        # 2) 金额合计一致（scale=1）
        in_sum = sum(r["金额"] for r in cfg["rows"])
        out_sum = sum(r.get("a", 0) for r in rows)
        check(f"{ind}: 金额合计一致", in_sum == out_sum, f"输入¥{in_sum:,} / 输出¥{out_sum:,}")

        # 3) 支付归并规则
        pays = set(r.get("p") for r in rows)
        check(f"{ind}: 支付归并符合行业规则", pays == cfg["pay_exp"], f"实际={sorted(pays)}")

        # 4) 客户脱敏前缀
        if cfg.get("cust_prefix"):
            custs = [r["n"] for r in rows if "n" in r]
            ok = all(c.startswith(cfg["cust_prefix"]) for c in custs) and len(custs) == len(cfg["rows"])
            check(f"{ind}: 客户编号化({cfg['cust_prefix']}***)", ok, f"样本={custs[:3]}")
        elif cfg.get("cust_prefix") is None:
            has_cust = any("n" in r for r in rows)
            check(f"{ind}: 无客户列（符合预期）", not has_cust, "未生成客户维度")

        # 5) 服务人员化名 / 代号化前缀
        if cfg.get("staff_prefix"):
            staffs = [r[k] for r in rows for k in ("teacher",) if k in r]
            ok = all(s.startswith(cfg["staff_prefix"]) for s in staffs)
            check(f"{ind}: 服务人员化名({cfg['staff_prefix']}*)", ok, f"样本={sorted(set(staffs))[:3]}")

        # 6) 科目重映射（education 精确校验）
        if cfg.get("subject_remap"):
            mp = json.load(open(map_path, encoding="utf-8")).get("subject", {})
            bad = {k: v for k, v in cfg["subject_remap"].items() if mp.get(k) != v}
            check(f"{ind}: 科目→兴趣课重映射", not bad, (f"不符: {bad}" if bad else f"命中 {len(mp)} 项"))
        elif cfg.get("subject_keep"):
            # 非教育行业：科目/商品应原样保留
            in_subj = [raw_subject(r) for r in cfg["rows"]]
            out_subj = [r.get("c") for r in rows]
            ok = set(in_subj) == set(out_subj)
            check(f"{ind}: 科目/商品原样保留", ok)

        # 7) 生成加密看板
        p = run_py(BUILD, ["-i", masked_path, "-o", html_path, "-p", PW,
                           "--title", f"{ind}行业测试"])
        if p.returncode != 0:
            check(f"{ind}: build_dashboard 执行", False, p.stderr.strip().splitlines()[-1])
            continue
        check(f"{ind}: build_dashboard 执行", True)

        html = open(html_path, encoding="utf-8").read()

        # 8) 锁屏标题中性
        m = re.search(r"<title>(.*?)</title>", html)
        check(f"{ind}: 锁屏标题中性", m and m.group(1) == "数据看板", f"<title>={m.group(1) if m else '?'}</title>")

        # 9) 泄漏检查（HTML 明文不应含任何真名/敏感词）
        hits = [w for w in cfg["leak"] if w in html]
        check(f"{ind}: HTML 无明文泄漏", not hits, (f"命中: {hits}" if hits else "0 命中"))

        # 10) 真加密校验（node 解密）
        if os.path.exists(NODE):
            payload = extract_payload(html)
            if payload and payload.get("salt"):
                status, _ = node_decrypt(payload, PW, node_runner)
                check(f"{ind}: 密码{PW}可解密", status == "OK", f"node={status}")
                status2, _ = node_decrypt(payload, "wrongpw", node_runner)
                check(f"{ind}: 错误密码被拦截", status2 == "FAIL", f"node={status2}")
            else:
                check(f"{ind}: 提取加密载荷", False, "HTML 中未找到 PAYLOAD")
        else:
            print("  · 跳过 node 真解密校验（node 不可用）")

        # 11) 地区钻取 + 人物画像（geo 场景额外校验 meta 与聚合）
        if ind == "geo" and os.path.exists(NODE):
            payload = extract_payload(html)
            dec = node_decrypt_full(payload, PW, node_runner_full, os.path.join(out_dir, "_geo_dec.json"))
            if not dec:
                check("geo: 解密 payload 失败", False)
            else:
                meta = dec.get("meta", {})
                check("geo: meta.regionKeys=省/市/区", meta.get("regionKeys") == ["prov", "city", "dist"], str(meta.get("regionKeys")))
                check("geo: meta.genderKey=gender", meta.get("genderKey") == "gender")
                check("geo: meta.ageKey=age", meta.get("ageKey") == "age")
                prov = {}
                for r in dec["rows"]:
                    prov[r["prov"]] = prov.get(r["prov"], 0) + r["a"]
                check("geo: 省级钻取聚合非空", len(prov) > 0 and sum(prov.values()) == sum(r["a"] for r in dec["rows"]), f"省份={list(prov.keys())}")
                gset = set(r["gender"] for r in dec["rows"])
                check("geo: 性别仅 男/女", gset <= {"男", "女"}, str(gset))
                ages_ok = all(isinstance(r["age"], (int, float)) for r in dec["rows"])
                check("geo: 年龄均为数值", ages_ok, f"n={len(dec['rows'])}")

    # ------------------------------------------------------------------
    # 分级权限（P2 双密码）：主=全量 / 访客=聚合视图
    # ------------------------------------------------------------------
    if os.path.exists(NODE):
        gr_rows = DATA["geo"]["rows"]
        gr_raw = os.path.join(out_dir, "_gr_raw.json")
        with open(gr_raw, "w", encoding="utf-8") as fp:
            json.dump(gr_rows, fp, ensure_ascii=False)
        gr_masked = os.path.join(out_dir, "_gr_masked.json")
        p = run_py(ANON, ["-i", gr_raw, "-o", gr_masked, "--level", "L2"])
        check("分级: anonymize 执行", p.returncode == 0)
        gr_html = os.path.join(out_dir, "_gr.html")
        p = run_py(BUILD, ["-i", gr_masked, "-o", gr_html, "-p", "boss123",
                           "--viewer-password", "guest456", "--title", "分级权限测试"])
        check("分级: 生成双密码看板", p.returncode == 0)
        if p.returncode == 0:
            html = open(gr_html, encoding="utf-8").read()
            main_pl = extract_payload(html)
            m2 = re.search(r"var PAYLOAD_VIEWER = (\{[^}]*\});", html)
            viewer_pl = json.loads(m2.group(1)) if m2 else None
            check("分级: 两个加密载荷都存在", bool(main_pl and viewer_pl))
            if main_pl and viewer_pl:
                # 各自密码可解
                s1, _ = node_decrypt(main_pl, "boss123", node_runner)
                s2, _ = node_decrypt(viewer_pl, "guest456", node_runner)
                check("分级: 主密码解全量", s1 == "OK", f"node={s1}")
                check("分级: 访客密码解聚合视图", s2 == "OK", f"node={s2}")
                # 交叉与错误密码必须拦截
                x1, _ = node_decrypt(main_pl, "guest456", node_runner)
                x2, _ = node_decrypt(viewer_pl, "boss123", node_runner)
                x3, _ = node_decrypt(main_pl, "wrong", node_runner)
                check("分级: 密码交叉不串", x1 == "FAIL" and x2 == "FAIL", f"x1={x1},x2={x2}")
                check("分级: 错误密码被拦截", x3 == "FAIL", f"node={x3}")
                # 访客视图内容：排除 n/teacher/signer，dims 同步过滤
                dec_v = node_decrypt_full(viewer_pl, "guest456", node_runner_full,
                                          os.path.join(out_dir, "_gr_viewer_dec.json"))
                if dec_v:
                    keys = set(dec_v["rows"][0].keys())
                    check("分级: 访客视图无敏感字段(n/teacher/signer)",
                          not keys & {"n", "teacher", "signer"}, f"字段={sorted(keys)}")
                    vkeys = [d["key"] for d in dec_v["dims"]]
                    check("分级: 访客视图 dims 同步过滤", "signer" not in vkeys and "teacher" not in vkeys, f"dims={vkeys}")
                    masked_rows = json.load(open(gr_masked, encoding="utf-8"))["rows"]
                    check("分级: 访客视图金额一致",
                          sum(r["a"] for r in dec_v["rows"]) == sum(r["a"] for r in masked_rows))
                else:
                    check("分级: 访客载荷可完整解密", False)

        # 免密默认：不传 -p 时 LOCKED=false 且无访客载荷
        gr_plain = os.path.join(out_dir, "_gr_plain.html")
        p = run_py(BUILD, ["-i", gr_masked, "-o", gr_plain, "--title", "免密默认"])
        if p.returncode == 0:
            html = open(gr_plain, encoding="utf-8").read()
            check("分级: 默认免密(LOCKED=false)", "var LOCKED = false" in html)
            check("分级: 免密无访客载荷", "var PAYLOAD_VIEWER = null" in html)
        else:
            check("分级: 默认免密生成", False)

    # ------------------------------------------------------------------
    # 世界地图模式（含"国家"列 → regionKeys=['country'] → 世界地图）
    # ------------------------------------------------------------------
    world_rows = [
        {"报名日期": "2026-05-01", "客户名称": "甲公司", "金额": 30000, "国家": "中国", "省份": "浙江省", "支付方式": "对公转账"},
        {"报名日期": "2026-05-02", "客户名称": "乙公司", "金额": 20000, "国家": "中国", "省份": "广东省", "支付方式": "电汇"},
        {"报名日期": "2026-06-03", "客户名称": "丙公司", "金额": 15000, "国家": "美国", "省份": "California", "支付方式": "微信"},
        {"报名日期": "2026-06-04", "客户名称": "丁公司", "金额": 10000, "国家": "美国", "省份": "New York", "支付方式": "支付宝"},
        {"报名日期": "2026-07-05", "客户名称": "戊公司", "金额": 12000, "国家": "日本", "省份": "Tokyo", "支付方式": "银行卡"},
    ]
    w_raw = os.path.join(out_dir, "_w_raw.json")
    with open(w_raw, "w", encoding="utf-8") as fp:
        json.dump(world_rows, fp, ensure_ascii=False)
    w_masked = os.path.join(out_dir, "_w_masked.json")
    p = run_py(ANON, ["-i", w_raw, "-o", w_masked, "--level", "L2"])
    check("世界地图: anonymize 执行", p.returncode == 0)
    if p.returncode == 0:
        wd = json.load(open(w_masked, encoding="utf-8"))
        check("世界地图: regionKeys=[country,prov]", wd["meta"].get("regionKeys") == ["country", "prov"],
              str(wd["meta"].get("regionKeys")))
        w_html = os.path.join(out_dir, "_w.html")
        p = run_py(BUILD, ["-i", w_masked, "-o", w_html, "--no-lock", "--title", "世界地图测试"])
        check("世界地图: 生成看板", p.returncode == 0)
        if p.returncode == 0:
            wh = open(w_html, encoding="utf-8").read()
            m = re.search(r'"geo": (\{.*?\}), "schema"', wh)
            geo = json.loads(m.group(1)) if m else None
            check("世界地图: 世界标志", bool(geo and geo.get("world")))
            check("世界地图: 内嵌世界 GeoJSON",
                  bool(geo and geo.get("geoJSONs", {}).get("world", {}).get("features", [])))
            check("世界地图: 中文国家名已映射英文",
                  bool(geo and geo.get("nameMap", {}).get("中国") == "China")
                  and geo["nameMap"].get("美国") == "United States")
            check("世界地图: 中国省界已挂载(地图下钻)",
                  bool(geo and geo.get("geoJSONs", {}).get("China", {}).get("features")))
            check("世界地图: 美国州界已挂载(地图下钻)",
                  bool(geo and geo.get("geoJSONs", {}).get("United States", {}).get("features")))
            check("世界地图: 国家内省份保留", bool(geo and geo.get("root", {}).get("children", {}).get("中国", {})
                                             .get("children", {}).get("浙江省")))
            check("世界地图: 聚合金额一致",
                  bool(geo and sum(c["a"] for c in geo["root"]["children"].values())
                       == sum(r["金额"] for r in world_rows)))

    # 汇总
    print("\n" + "=" * 64)
    passed = sum(1 for _, c, _ in RESULTS if c)
    total = len(RESULTS)
    print(f"结果: {passed}/{total} 通过")
    failed = [n for n, c, _ in RESULTS if not c]
    if failed:
        print("失败项:")
        for n in failed:
            print("  - " + n)
    print("=" * 64)
    if not args.keep:
        safe_rmtree(out_dir)
        print("（tests/out 已清理；加 --keep 可保留产物）")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())

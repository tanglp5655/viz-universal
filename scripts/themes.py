# -*- coding: utf-8 -*-
"""
viz-universal · 看板视觉主题库
================================
把「看板长什么样」从生成器里抽出来，沉淀成一份可选主题清单。
用户/智能体在生成看板时用 --theme <id> 指定风格，引擎注入对应的
CSS 变量 + 图表配色常量即可，零改动图表逻辑。

包含主题（id / 中文名 / 气质）：
  apple-glass    Apple 液态玻璃   极深底 + 多层霓虹光晕 + 清玻璃卡
  stripe         Stripe 科技渐变  深蓝底 + 蓝紫青渐变 + 玻璃拟态
  vercel         Vercel 极简纯黑  纯黑底 · 发丝边框 · 零渐变 · 极致克制
  linear         Linear 深紫靛蓝  深靛底 · 细线条 · 产品感强
  bloomberg      Bloomberg 终端   黑底 · 琥珀/绿 · 等宽数据
  notion         Notion 暖白编辑  暖白纸 · 衬线标题 · 干净
  neubrutalism   Neubrutalism    粗硬描边 · 撞色块 · 活泼
  tokyo-night    Tokyo Night     雾紫蓝粉 · IDE 配色
  nordic         Nordic / MUJI   米白 · 大地色 · 大量留白
  cyberpunk      Cyberpunk 霓虹  黑底 · 青/品红 · 网格光

每个主题字段说明：
  mode        dark / light（影响默认文字与网格色推导）
  bg          页面背景（可多层渐变）
  text/text2  主/次文字色
  surface     卡片背景（玻璃主题用半透明白渐变；纯色主题用实色）
  border      卡片边框
  radius      圆角
  blur        backdrop-filter 值（无则 "none"）
  shadow      卡片阴影（含 inset 高光则写在一起）
  grad        标题/数字渐变（浅色主题用实色 accent）
  accent      主强调色
  tabBg/tabColor  标签选中态底色/文字
  palette     图表主色板（7 色）
  mcolor      月度强调色 {月:色}（缺省由 palette 前 3 色推导）
  mapVisualMap 地图 visualMap 色阶（6 段）
  mapArea     地图无数据省区底色
  genderM/genderF  男女图标色
  grid/axis   图表网格线/坐标轴色
  tooltipBg   浮窗底色
"""
import os
import json


def _hexa(hexcolor, alpha):
    """#rrggbb + alpha -> rgba()"""
    h = hexcolor.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 'rgba(%d,%d,%d,%.3f)' % (r, g, b, alpha)


THEMES = {
    "apple-glass": {
        "label_cn": "Apple 液态玻璃", "label_en": "Apple Liquid Glass", "mode": "dark",
        "vibe": "极深底 · 多层霓虹光晕 · 清玻璃卡",
        "bg": "radial-gradient(1050px 720px at 6% -12%, rgba(124,92,255,.30), transparent 60%),"
              "radial-gradient(900px 660px at 98% 4%, rgba(255,110,199,.22), transparent 58%),"
              "radial-gradient(1050px 820px at 52% 116%, rgba(79,209,255,.20), transparent 60%),"
              "radial-gradient(720px 520px at 84% 84%, rgba(255,184,108,.12), transparent 55%),#05060c",
        "text": "#eef2fb", "text2": "#9aa3c4",
        "surface": "linear-gradient(160deg,rgba(255,255,255,.10),rgba(255,255,255,.028))",
        "border": "1px solid rgba(255,255,255,.12)",
        "radius": "22px", "blur": "blur(26px) saturate(140%)",
        "shadow": "0 14px 42px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.16)",
        "grad": "linear-gradient(92deg,#ffb6e2,#c4b5fd,#7fe3ff)",
        "accent": "#b794ff", "tabBg": "linear-gradient(135deg,rgba(255,110,199,.32),rgba(79,209,255,.18))",
        "tabColor": "#fff",
        "palette": ["#ff6ec7", "#b794ff", "#7c8cff", "#4fd1ff", "#5eead4", "#ffb86c", "#c4b5fd"],
        "mcolor": {"2026-05": "#b794ff", "2026-06": "#ff9ed8", "2026-07": "#4fd1ff"},
        "mapVisualMap": ["#3f35a8", "#5b4fd6", "#7c6cff", "#a596ff", "#d4ccff"],
        "mapArea": "#0c0a18",
        "genderM": "#7c8cff", "genderF": "#ff6ec7",
        "grid": "rgba(255,255,255,.05)", "axis": "#8b93b8", "tooltipBg": "rgba(8,10,18,.92)",
    },
    "stripe": {
        "label_cn": "Stripe 科技渐变", "label_en": "Stripe Gradient", "mode": "dark",
        "vibe": "深蓝底 · 蓝紫青渐变 · 玻璃拟态",
        "bg": "radial-gradient(1000px 700px at 8% -10%, rgba(99,91,255,.28), transparent 58%),"
              "radial-gradient(900px 680px at 96% 8%, rgba(34,211,238,.20), transparent 56%),"
              "radial-gradient(1000px 760px at 50% 115%, rgba(167,139,250,.18), transparent 60%),#0a0e1a",
        "text": "#e6ebf5", "text2": "#8b97b5",
        "surface": "linear-gradient(160deg,rgba(255,255,255,.07),rgba(255,255,255,.02))",
        "border": "1px solid rgba(255,255,255,.085)",
        "radius": "18px", "blur": "blur(16px) saturate(140%)",
        "shadow": "0 10px 30px rgba(0,0,0,.40), inset 0 1px 0 rgba(255,255,255,.08)",
        "grad": "linear-gradient(92deg,#b6bdff,#6ee7ff)",
        "accent": "#635bff", "tabBg": "linear-gradient(135deg,rgba(99,91,255,.30),rgba(34,211,238,.16))",
        "tabColor": "#fff",
        "palette": ["#635bff", "#7c8cff", "#a78bfa", "#22d3ee", "#5eead4", "#38bdf8", "#ff7eb6"],
        "mcolor": {"2026-05": "#7c8cff", "2026-06": "#a78bfa", "2026-07": "#22d3ee"},
        "mapVisualMap": ["#27489e", "#3a5bd6", "#5b7cff", "#7ea4ff", "#a8c8ff"],
        "mapArea": "#0e1726",
        "genderM": "#7c8cff", "genderF": "#ff7eb6",
        "grid": "rgba(255,255,255,.05)", "axis": "#8b93b8", "tooltipBg": "rgba(10,14,26,.92)",
    },
    "vercel": {
        "label_cn": "Vercel 极简纯黑", "label_en": "Vercel Geist", "mode": "dark",
        "vibe": "纯黑底 · 发丝边框 · 零渐变 · 极致克制",
        "bg": "#000000",
        "text": "#ededed", "text2": "#888888",
        "surface": "rgba(255,255,255,.03)",
        "border": "1px solid rgba(255,255,255,.10)",
        "radius": "12px", "blur": "none",
        "shadow": "0 1px 0 rgba(255,255,255,.04)",
        "grad": "#ffffff",
        "accent": "#ffffff", "tabBg": "#ffffff", "tabColor": "#000000",
        "palette": ["#ffffff", "#c9c9c9", "#9a9a9a", "#6e6e6e", "#4a4a4a", "#e6e6e6", "#b0b0b0"],
        "mcolor": {"2026-05": "#ededed", "2026-06": "#a1a1a1", "2026-07": "#6e6e6e"},
        "mapVisualMap": ["#3a3a3a", "#6e6e6e", "#9a9a9a", "#d0d0d0"],
        "mapArea": "#000000",
        "genderM": "#ffffff", "genderF": "#a1a1a1",
        "grid": "rgba(255,255,255,.08)", "axis": "#888888", "tooltipBg": "rgba(0,0,0,.92)",
    },
    "linear": {
        "label_cn": "Linear 深紫靛蓝", "label_en": "Linear Indigo", "mode": "dark",
        "vibe": "深靛底 · 细线条 · 产品感强",
        "bg": "radial-gradient(1000px 700px at 12% -10%, rgba(94,106,210,.22), transparent 58%),"
              "radial-gradient(900px 700px at 95% 10%, rgba(188,140,255,.16), transparent 56%),#0d0b1a",
        "text": "#c7c9d9", "text2": "#7a7d99",
        "surface": "rgba(255,255,255,.04)",
        "border": "1px solid rgba(255,255,255,.07)",
        "radius": "14px", "blur": "none",
        "shadow": "0 8px 24px rgba(0,0,0,.40)",
        "grad": "linear-gradient(92deg,#8b8ef0,#5e6ad2)",
        "accent": "#5e6ad2", "tabBg": "linear-gradient(135deg,rgba(94,106,210,.34),rgba(139,142,240,.16))",
        "tabColor": "#fff",
        "palette": ["#5e6ad2", "#8b8ef0", "#a78bfa", "#bc8cff", "#6e8bf5", "#9d7bff", "#c4b5ff"],
        "mcolor": {"2026-05": "#5e6ad2", "2026-06": "#8b8ef0", "2026-07": "#a78bfa"},
        "mapVisualMap": ["#3f3578", "#5a4f9e", "#6f64c9", "#8f87ee", "#b8b0ff"],
        "mapArea": "#0d0b1a",
        "genderM": "#8b8ef0", "genderF": "#bc8cff",
        "grid": "rgba(255,255,255,.06)", "axis": "#7a7d99", "tooltipBg": "rgba(13,11,26,.92)",
    },
    "bloomberg": {
        "label_cn": "Bloomberg 终端", "label_en": "Bloomberg Terminal", "mode": "dark",
        "vibe": "黑底 · 琥珀/绿 · 等宽数据",
        "bg": "#0a0e0a",
        "text": "#d8ffd8", "text2": "#7faf7f",
        "surface": "rgba(255,255,255,.03)",
        "border": "1px solid rgba(120,255,120,.12)",
        "radius": "10px", "blur": "none",
        "shadow": "0 6px 18px rgba(0,0,0,.40)",
        "grad": "#ffb000",
        "accent": "#ffb000", "tabBg": "#ffb000", "tabColor": "#000000",
        "palette": ["#ffb000", "#33ff66", "#ffd23f", "#7fffd4", "#ff8c42", "#9dff5b", "#ffe066"],
        "mcolor": {"2026-05": "#ffb000", "2026-06": "#33ff66", "2026-07": "#ffd23f"},
        "mapVisualMap": ["#1a5c38", "#2f9a55", "#3fd97a", "#7ff5a8", "#d0ffe0"],
        "mapArea": "#0a0e0a",
        "genderM": "#ffb000", "genderF": "#33ff66",
        "grid": "rgba(120,255,120,.10)", "axis": "#7faf7f", "tooltipBg": "rgba(10,14,10,.92)",
    },
    "notion": {
        "label_cn": "Notion 暖白编辑", "label_en": "Notion Editorial", "mode": "light",
        "vibe": "暖白纸 · 衬线标题 · 干净",
        "bg": "#ffffff",
        "text": "#37352f", "text2": "#6f6f6b",
        "surface": "#ffffff",
        "border": "1px solid #e9e9e7",
        "radius": "12px", "blur": "none",
        "shadow": "0 1px 3px rgba(15,15,15,.06)",
        "grad": "#2383e2",
        "accent": "#2383e2", "tabBg": "#2383e2", "tabColor": "#ffffff",
        "palette": ["#2383e2", "#f2c744", "#e2554b", "#0f9d58", "#9b59b6", "#ff8c42", "#16a085"],
        "mcolor": {"2026-05": "#2383e2", "2026-06": "#f2c744", "2026-07": "#e2554b"},
        "mapVisualMap": ["#eef3fb", "#cfe0f5", "#9cc3ec", "#5b9bdd", "#2383e2", "#0f6fc4"],
        "mapArea": "#f7f6f3",
        "genderM": "#2383e2", "genderF": "#e2554b",
        "grid": "rgba(55,53,47,.08)", "axis": "#6f6f6b", "tooltipBg": "rgba(255,255,255,.96)",
    },
    "neubrutalism": {
        "label_cn": "Neubrutalism 撞色", "label_en": "Neubrutalism", "mode": "light",
        "vibe": "粗硬描边 · 撞色块 · 活泼",
        "bg": "#ffe8c2",
        "text": "#111111", "text2": "#444444",
        "surface": "#fff7e6",
        "border": "2px solid #111111",
        "radius": "14px", "blur": "none",
        "shadow": "6px 6px 0 #111111",
        "grad": "#ff5d8f",
        "accent": "#ff5d8f", "tabBg": "#ff5d8f", "tabColor": "#111111",
        "palette": ["#ff5d8f", "#5dd0ff", "#ffd23f", "#7be08a", "#b08cff", "#ff8c42", "#4ecdc4"],
        "mcolor": {"2026-05": "#ff5d8f", "2026-06": "#5dd0ff", "2026-07": "#ffd23f"},
        "mapVisualMap": ["#fff3d6", "#ffdf9e", "#ffc15e", "#f79a1f", "#d9740b"],
        "mapArea": "#ffe8c2",
        "genderM": "#ff5d8f", "genderF": "#5dd0ff",
        "grid": "rgba(17,17,17,.15)", "axis": "#444444", "tooltipBg": "rgba(255,255,255,.97)",
    },
    "tokyo-night": {
        "label_cn": "Tokyo Night", "label_en": "Tokyo Night", "mode": "dark",
        "vibe": "雾紫蓝粉 · IDE 配色",
        "bg": "#1a1b26",
        "text": "#c0caf5", "text2": "#c3cbef",
        "surface": "rgba(255,255,255,.04)",
        "border": "1px solid #2a2e3f",
        "radius": "12px", "blur": "none",
        "shadow": "0 8px 24px rgba(0,0,0,.35)",
        "grad": "linear-gradient(92deg,#bb9af7,#7aa2f7)",
        "accent": "#7aa2f7", "tabBg": "linear-gradient(135deg,rgba(122,162,247,.32),rgba(187,154,247,.16))",
        "tabColor": "#fff",
        "palette": ["#7aa2f7", "#bb9af7", "#f7768e", "#9ece6a", "#e0af68", "#7dcfff", "#2ac3de"],
        "mcolor": {"2026-05": "#7aa2f7", "2026-06": "#bb9af7", "2026-07": "#f7768e"},
        "mapVisualMap": ["#2f4f8c", "#3f6fc9", "#5a8fe6", "#7aa2f7", "#b0c8ff"],
        "mapArea": "#1a1b26",
        "genderM": "#7aa2f7", "genderF": "#f7768e",
        "grid": "rgba(192,202,245,.08)", "axis": "#a2abd0", "tooltipBg": "rgba(26,27,38,.94)",
    },
    "nordic": {
        "label_cn": "Nordic / MUJI", "label_en": "Nordic MUJI", "mode": "light",
        "vibe": "米白 · 大地色 · 大量留白",
        "bg": "#f4f1ea",
        "text": "#4a4540", "text2": "#6e6961",
        "surface": "#fbfaf6",
        "border": "1px solid #ddd6c8",
        "radius": "14px", "blur": "none",
        "shadow": "0 2px 8px rgba(74,69,64,.06)",
        "grad": "#b08968",
        "accent": "#b08968", "tabBg": "#b08968", "tabColor": "#ffffff",
        "palette": ["#b08968", "#8a9a8b", "#c9a36b", "#6b8e9e", "#a26769", "#9caf88", "#d4b483"],
        "mcolor": {"2026-05": "#b08968", "2026-06": "#8a9a8b", "2026-07": "#c9a36b"},
        "mapVisualMap": ["#f4f1ea", "#e3dccb", "#d0c3a5", "#b08968", "#8a9a8b", "#6b8e9e"],
        "mapArea": "#f4f1ea",
        "genderM": "#b08968", "genderF": "#a26769",
        "grid": "rgba(74,69,64,.10)", "axis": "#8a847a", "tooltipBg": "rgba(244,241,234,.96)",
    },
    "cyberpunk": {
        "label_cn": "Cyberpunk 霓虹", "label_en": "Cyberpunk Neon", "mode": "dark",
        "vibe": "黑底 · 青/品红 · 网格光",
        "bg": "radial-gradient(1000px 700px at 10% -10%, rgba(0,240,255,.14), transparent 55%),"
              "radial-gradient(900px 700px at 95% 12%, rgba(255,43,214,.14), transparent 55%),#05010d",
        "text": "#aef6ff", "text2": "#9b8fb8",
        "surface": "rgba(255,255,255,.03)",
        "border": "1px solid #1a0a2e",
        "radius": "12px", "blur": "none",
        "shadow": "0 0 24px rgba(0,240,255,.10)",
        "grad": "linear-gradient(92deg,#00f0ff,#ff2bd6)",
        "accent": "#00f0ff", "tabBg": "linear-gradient(135deg,rgba(0,240,255,.30),rgba(255,43,214,.18))",
        "tabColor": "#fff",
        "palette": ["#00f0ff", "#ff2bd6", "#7a5cff", "#39ff14", "#ff6b00", "#faff00", "#ff00aa"],
        "mcolor": {"2026-05": "#00f0ff", "2026-06": "#ff2bd6", "2026-07": "#7a5cff"},
        "mapVisualMap": ["#1a4a6e", "#1f7fae", "#2fb8e6", "#5fd8ff", "#b8f0ff"],
        "mapArea": "#05010d",
        "genderM": "#00f0ff", "genderF": "#ff2bd6",
        "grid": "rgba(0,240,255,.12)", "axis": "#6b5b8a", "tooltipBg": "rgba(5,1,13,.94)",
    },
}

DEFAULT_THEME = "apple-glass"


def list_themes():
    """返回可选主题清单（用于 --list-themes 与智能体推荐）。"""
    return [{"id": k, "cn": v["label_cn"], "en": v["label_en"],
             "mode": v["mode"], "vibe": v["vibe"]} for k, v in THEMES.items()]


def get_theme(tid):
    return THEMES.get(tid)


def _mcolor(t):
    """月度强调色：显式提供则用之，否则取 palette 前 3 色。"""
    if t.get("mcolor"):
        return t["mcolor"]
    p = t["palette"]
    return {"2026-05": p[0], "2026-06": p[1 % len(p)], "2026-07": p[2 % len(p)]}


def expand(tid):
    """展开主题为月度对比看板（build_multimonth.py）所需的注入片段。

    返回 dict:
      css    -> :root{...} CSS 变量字符串
      js     -> const THEME = {...} 常量字符串
      meta   -> {id,label_cn,...}
    """
    if tid not in THEMES:
        tid = DEFAULT_THEME
    t = THEMES[tid]
    css = (
        ":root{"
        "--bg:%s;"
        "--text:%s;--text2:%s;"
        "--surface:%s;--border:%s;--radius:%s;"
        "--blur:%s;--shadow:%s;"
        "--grad:%s;--accent:%s;"
        "--tab-bg:%s;--tab-color:%s;"
        "--tooltip-bg:%s;--grid:%s;--axis:%s}"
    ) % (
        t["bg"], t["text"], t["text2"], t["surface"], t["border"], t["radius"],
        t["blur"], t["shadow"], t["grad"], t["accent"],
        t["tabBg"], t["tabColor"], t["tooltipBg"], t["grid"], t["axis"],
    )
    js = (
        "const THEME={"
        "palette:%s,"
        "mcolor:%s,"
        "mapVisualMap:%s,mapArea:'%s',"
        "genderM:'%s',genderF:'%s',"
        "grid:'%s',axis:'%s',text:'%s',tooltipBg:'%s'};"
    ) % (
        json.dumps(t["palette"]), json.dumps(_mcolor(t)),
        json.dumps(t["mapVisualMap"]), t["mapArea"],
        t["genderM"], t["genderF"],
        t["grid"], t["axis"], t["text"], t["tooltipBg"],
    )
    return {"css": css, "js": js, "meta": {"id": tid, "label_cn": t["label_cn"],
                                          "label_en": t["label_en"], "mode": t["mode"],
                                          "vibe": t["vibe"]}}


def window_js(tid):
    """给 skill 通用引擎（template.html）注入 window.THEME，供图表回退取色。"""
    e = expand(tid)
    return "window.THEME={palette:%s,mcolor:%s,accent:'%s',text:'%s',text2:'%s',grid:'%s',axis:'%s',tooltipBg:'%s',mapVisualMap:%s,mapArea:'%s'};" % (
        json.dumps(THEMES[tid]["palette"]),
        json.dumps(_mcolor(THEMES[tid])),
        THEMES[tid]["accent"], THEMES[tid]["text"], THEMES[tid]["text2"],
        THEMES[tid]["grid"], THEMES[tid]["axis"], THEMES[tid]["tooltipBg"],
        json.dumps(THEMES[tid]["mapVisualMap"]), THEMES[tid]["mapArea"],
    )


def override_css(tid):
    """给 skill 通用引擎（template.html）注入的页面 chrome 覆盖样式（!important）。"""
    if tid not in THEMES:
        tid = DEFAULT_THEME
    t = THEMES[tid]
    aT = _hexa(t["accent"], 0.14)
    aT2 = _hexa(t["accent"], 0.30)
    return (
        "body{background:%s!important;color:%s!important}"
        ".hd{background:%s!important;border-color:%s!important;border-radius:%s!important}"
        ".card{background:%s!important;border-color:%s!important;border-radius:%s!important}"
        ".kpi{background:%s!important;border-color:%s!important;border-radius:%s!important}"
        ".kpi .v{color:%s!important}"
        ".btnrow .b.on{background:%s!important;border-color:%s!important;color:%s!important}"
        ".chip{background:%s!important;border-color:%s!important;color:%s!important}"
        "table th{background:%s!important;color:%s!important}"
        "table td{color:%s!important}"
        ".lockcard{background:%s!important;border-color:%s!important}"
        ".lockcard h2,.lockcard .sub{color:%s!important}"
    ) % (
        t["bg"], t["text"],
        t["surface"], t["border"], t["radius"],
        t["surface"], t["border"], t["radius"],
        t["surface"], t["border"], t["radius"],
        t["accent"],
        t["tabBg"], aT2, t["tabColor"],
        aT, aT2, t["accent"],
        t["bg"], t["text2"],
        t["text"],
        t["surface"], t["border"],
        t["text"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        for x in list_themes():
            print("%-14s %s / %s  [%s] %s" % (x["id"], x["cn"], x["en"], x["mode"], x["vibe"]))
    else:
        print("themes:", ", ".join(THEMES.keys()))

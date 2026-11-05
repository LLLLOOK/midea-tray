# -*- coding: utf-8 -*-
"""生成美居同款线风 SVG 图标集: icons/<name>.svg(灰) + icons/<name>_on.svg(蓝)。
24x24 视窗, 1.6px 圆头描边, 与面板浅色主题配套。"""
from pathlib import Path

GRAY = "#8C949C"
BLUE = "#26AAFF"
OUT = Path(__file__).resolve().parent / "icons"

# 雪花: 一条贯穿臂 + 两端 V 形分叉, 绕中心转 3 次得到 6 臂
_ARM = ('<path d="M12 2.6V21.4"/>'
        '<path d="M12 6.2 9.2 3.4"/><path d="M12 6.2 14.8 3.4"/>'
        '<path d="M12 17.8 9.2 20.6"/><path d="M12 17.8 14.8 20.6"/>')
_SNOW = "".join('<g transform="rotate(%d 12 12)">%s</g>' % (a, _ARM)
                for a in (0, 60, 120))

# 风扇: 一片逗号形扇叶, 绕中心转 3 次
_BLADE = ('<path d="M12 12C10.8 7.6 12.6 4.6 15.8 4.8'
          'c1.8.8 1.2 3.6-1 5-1.2.8-2.2 1.6-2.8 2.2z"/>')
_FAN = "".join('<g transform="rotate(%d 12 12)">%s</g>' % (a, _BLADE)
               for a in (0, 120, 240))

# (名字, 路径数据列表, 需要填充的圆/形状列表)
ICONS = {
    # 模式: 六臂雪花(带分叉 + 中心实点)
    "snow": ([], [("raw", _SNOW), ("circle", 12, 12, 1.15)]),
    # 风速: 三叶风扇(中心留空)
    "fan": ([], [("raw", _FAN)]),
    # 防直吹: 人形 + 头顶三道风线
    "shield": ([
        "M4.5 19v-1.6a3.75 3.75 0 0 1 7.5 0V19",
        "M14.6 4.7c1.3-1.4 2.2.4 3.5-1",
        "M15.2 8.1c1.3-1.4 2.2.4 3.5-1",
        "M15.8 11.5c1.3-1.4 2.2.4 3.5-1",
    ], [("circle_o", 8.25, 8.6, 2.6)]),
    # 上下摆风: 中间上下箭头 + 两侧包住的短弧
    "updown": ([
        "M12 3.5v6.2", "M9.7 5.8 12 3.5l2.3 2.3",
        "M12 20.5v-6.2", "M9.7 18.2 12 20.5l2.3-2.3",
        "M7.9 7.8C6.3 10.4 6.3 13.6 7.9 16.2",
        "M16.1 7.8c1.6 2.6 1.6 5.8 0 8.4",
    ], []),
    # 左右摆风: 上方双斜弧 + 下方弧形横向双箭头
    "leftright": ([
        "M11.4 5.6C8.7 6.7 6.7 8.7 6 11.4",
        "M12.6 5.6c2.7 1.1 4.7 3.1 5.4 5.8",
        "M6 17.2C9.4 15.6 14.6 15.6 18 17.2",
        "M6 17.2 8.8 15.8", "M6 17.2 8.8 19.2",
        "M18 17.2 15.2 15.8", "M18 17.2 15.2 19.2",
    ], []),
    # 出风方向: 斜向箭头 + 左下三点 + 右下虚线弧
    "wind": ([
        "M6.4 17.6 14.4 9.6",
        "M14.4 9.6 9.8 10.4", "M14.4 9.6 13.6 14.2",
        "M17.4 14.9c2.2 2.2 2.2 4.6 0 6.8",
    ], [("circle", 5.6, 15.4, 0.6), ("circle", 4.9, 18.6, 0.6),
        ("circle", 6.9, 21.4, 0.6), ("circle", 18.1, 13.6, 0.6)]),
    # 电辅热: 三竖加热丝 + 一道横杆
    "auxheat": ([
        "M7.4 4.6v15.2", "M12 4.6v15.2", "M16.6 4.6v15.2",
        "M4.6 10.2h14.8",
    ], []),
    # 智控温: 温度计 + 右上指示三角
    "thermo": ([
        "M10.2 15.6V7.8a1.8 1.8 0 0 1 3.6 0v7.8",
        "M17.9 5 19.9 7 17.5 7.6Z",
    ], [("circle_o", 12, 17.1, 3.2)]),
    # 强冷: 回旋箭头(箭头在左下) + 内部两道风线
    "turbo": ([
        "M18.2 7.4A7.4 7.4 0 1 0 7 17.6",
        "M7 13.5v4.2h4.2",
        "M11 10.4c2-1.2 4.4-.8 5.4.9",
        "M10.4 13.8c2-1.2 4.2-.8 5.2.9",
    ], []),
    # 省电: 叶子 + 贯穿闪电
    "leaf": ([
        "M5.6 18.4C5.6 10.4 10.2 5.6 18.4 5.6 18.4 14 13.8 18.4 5.6 18.4Z",
        "M15.2 8.2 11.8 13.4h3.2l-3.4 5",
    ], []),
    # 智能光感: 眼睛
    "eye": ([
        "M2.8 12S6.3 6 12 6s9.2 6 9.2 6-3.5 6-9.2 6S2.8 12 2.8 12z",
        "M12 9.2a2.8 2.8 0 1 1 0 5.6 2.8 2.8 0 0 1 0-5.6z",
    ], []),
    # 电源符号(底部开机钮)
    "power": ([
        "M12 3.2v7.6",
        "M6.8 6.8a7.3 7.3 0 1 0 10.4 0",
    ], []),
    # 定时: 时钟
    "timer": ([
        "M12 8.8V12l2.4 2",
        "M9.4 3.2h5.2",
    ], [("circle_o", 12, 13, 7.4)]),
    # 标题栏返回
    "back": (["M14.5 5 8 12l6.5 7"], []),
    # 列表行右箭头
    "chevron": (["M9.5 6.5l5.5 5.5-5.5 5.5"], []),
    # 电量统计
    "energy": (["M13 3 6.5 13h4.4L10 21l6.6-10.5h-4.5L13 3z"], []),
    # 智清洁: 星点闪光
    "clean": ([
        "M12 4.5l1.3 3.4 3.4 1.3-3.4 1.3L12 14l-1.3-3.5L7.3 9.2l3.4-1.3L12 4.5z",
        "M18 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7.7-1.8z",
    ], []),
    # 滤网洁净度: 表盘
    "gauge": ([
        "M12 8.8V12l2.6 1.8",
    ], [("circle_o", 12, 12, 8.2)]),
    # 故障检测: 盾牌
    "alert": ([
        "M12 3.5l7 2.6v5.2c0 4.6-3 7.8-7 9.2-4-1.4-7-4.6-7-9.2V6.1l7-2.6z",
        "M12 8.8v4",
    ], [("circle", 12, 15.6, 0.9)]),
    # 睡眠管家: 月亮
    "moon": (["M19 14.6A7.6 7.6 0 0 1 9.4 5a7.6 7.6 0 1 0 9.6 9.6z"], []),
    # AI 智能服务: 机器人
    "ai": ([
        "M12 3.6v3",
        "M9.2 11.6v1.8", "M14.8 11.6v1.8",
        "M7 7h10a2.4 2.4 0 0 1 2.4 2.4v5.2A2.4 2.4 0 0 1 17 17H7a2.4 2.4 0 0 1-2.4-2.4V9.4A2.4 2.4 0 0 1 7 7z",
    ], [("circle", 12, 2.9, 0.9)]),
    # 自定义: 调节杆
    "custom": ([
        "M4 8h8.2", "M17.8 8H20",
        "M4 16h2.2", "M10 16h10",
    ], [("circle_o", 15, 8, 2), ("circle_o", 8, 16, 2)]),
    # 智能场景: 叠层方块
    "scene": ([
        "M4.5 4.5h8v8h-8z",
        "M11.5 11.5h8v8h-8z",
    ], []),
}


def svg(name, color, paths, shapes):
    """注意: QtSvg 不继承 <svg> 根上的样式属性, 颜色必须写在每个元素上。"""
    body = []
    stroke = 'stroke="%s" stroke-width="1.6" stroke-linecap="round" ' \
             'stroke-linejoin="round" fill="none"' % color
    for p in paths:
        body.append('<path d="%s" %s/>' % (p, stroke))
    for s in shapes:
        if s[0] == "circle":
            _, cx, cy, r = s
            body.append('<circle cx="%s" cy="%s" r="%s" fill="%s" '
                        'stroke="none"/>' % (cx, cy, r, color))
        elif s[0] == "circle_o":
            _, cx, cy, r = s
            body.append('<circle cx="%s" cy="%s" r="%s" %s/>' % (cx, cy, r, stroke))
        elif s[0] == "rect_o":
            _, x, y, w, h, rx = s
            body.append('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" %s/>'
                        % (x, y, w, h, rx, stroke))
        elif s[0] == "raw":
            body.append(s[1].replace('<path ', '<path %s ' % stroke))
        elif s[0] == "path":
            body.append('<path d="%s" %s/>' % (s[1], stroke))
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
            '%s</svg>' % "".join(body))


def main():
    OUT.mkdir(exist_ok=True)
    for name, (paths, shapes) in ICONS.items():
        (OUT / ("%s.svg" % name)).write_text(svg(name, GRAY, paths, shapes),
                                             encoding="utf-8")
        (OUT / ("%s_on.svg" % name)).write_text(svg(name, BLUE, paths, shapes),
                                                encoding="utf-8")
    # 蓝色电源钮上的白色电源符号
    paths, shapes = ICONS["power"]
    (OUT / "power_white.svg").write_text(
        svg("power", "#FFFFFF", paths, shapes), encoding="utf-8")
    # 标题栏黑色电源符号
    (OUT / "power_black.svg").write_text(
        svg("power", "#1A1C1E", paths, shapes), encoding="utf-8")
    print("生成 %d 个图标 x2 色 + power_white -> %s" % (len(ICONS), OUT))


if __name__ == "__main__":
    main()

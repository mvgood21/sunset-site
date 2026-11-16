"""Inline SVG pieces used by tools/build.py: UI icons, step/use-case illustrations, logo lockups.

Icons follow the brand's icon style (Material Symbols Rounded feel: 24 grid, 2 px round strokes).
Illustrations use only the brand's two primitives — circles and horizontal bands — and the
'lines end at the boundary' rule. No locks, shields or code rain (brand guide 6.3).
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ICON = {
    'no-server': '<rect x="4" y="4" width="16" height="6" rx="2"/><rect x="4" y="14" width="16" height="6" rx="2"/><path d="M7.5 7h.01M7.5 17h.01"/><path d="M3 3l18 18"/>',
    'nametag': '<rect x="3" y="5.5" width="18" height="13" rx="3"/><circle cx="8.5" cy="12" r="2.2"/><path d="M13 10.5h4.5M13 13.5h3"/>',
    'room-wifi': '<path d="M3.5 10 12 3.5 20.5 10v9a1.5 1.5 0 0 1-1.5 1.5H5A1.5 1.5 0 0 1 3.5 19z"/><path d="M8.2 13.3a5.4 5.4 0 0 1 7.6 0M10.1 15.5a2.7 2.7 0 0 1 3.8 0"/><path d="M12 17.8h.01"/>',
    'sunmark': '<path d="M6 13.5a6 6 0 0 1 12 0z" fill="currentColor" stroke="none"/><path d="M3 16.5h18"/>',
    'check': '<circle cx="12" cy="12" r="9"/><path d="M8 12.3l2.7 2.7L16 9.7"/>',
    'alert': '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5.5"/><path d="M12 16.4h.01"/>',
    'phone': '<rect x="6.5" y="2.5" width="11" height="19" rx="2.5"/><path d="M10.5 18.5h3"/>',
    'mail': '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M3.5 6.5 12 13l8.5-6.5"/>',
    'arrow-down': '<path d="M12 5v14M6 13l6 6 6-6"/>',
    'arrow-right': '<path d="M5 12h14M13 6l6 6-6 6"/>',
    'play': '<path d="M8 5.5v13l10.5-6.5z" fill="currentColor" stroke="none"/>',
    'hash': '<path d="M9.5 4 7.5 20M16.5 4l-2 16M4.5 9h15.5M4 15h15.5"/>',
    'trash': '<path d="M4 7h16M10 7V4.5h4V7M6.5 7l1 13h9l1-13"/>',
    'block': '<circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/>',
    'eye-off': '<path d="M3 3l18 18"/><path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c5.5 0 9 5.5 9 7 0 .7-.8 2.2-2.2 3.7M6.6 6.6C4.4 8 3 10.9 3 12c0 1.5 3.5 7 9 7 1.9 0 3.6-.6 5-1.5"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/>',
    'users': '<circle cx="9" cy="8" r="3.2"/><path d="M3 19.5c.6-3.3 3-5 6-5s5.4 1.7 6 5"/><path d="M15.5 4.9a3.2 3.2 0 0 1 0 6.2M17.5 14.7c1.8.6 3.1 2.2 3.5 4.8"/>',
    'key': '<circle cx="8" cy="15" r="4"/><path d="M11 12l8.5-8.5M16.5 6.5l2.5 2.5M14 9l2 2"/>',
    'bell-off': '<path d="M3 3l18 18"/><path d="M8.6 4.4A6 6 0 0 1 18 9.5c0 3.2.8 5.1 1.6 6.3M16 17.5H4.5c1-1.2 1.5-3.4 1.5-8 0-.8.1-1.5.4-2.2"/><path d="M10 20.5a2.3 2.3 0 0 0 4 0"/>',
    'wifi-off': '<path d="M3 3l18 18"/><path d="M8.5 16.2a5 5 0 0 1 7 0M5.2 12.9a9.7 9.7 0 0 1 4.2-2.3M14.6 10.6a9.7 9.7 0 0 1 4.2 2.3M2 9.4a14.5 14.5 0 0 1 4.3-2.6M10.4 5.6A14.6 14.6 0 0 1 22 9.4"/><path d="M12 19.6h.01"/>',
    'database': '<ellipse cx="12" cy="6" rx="7.5" ry="3"/><path d="M4.5 6v12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/>',
}


def icon(name, cls='', label=None):
    body = _ICON[name]
    aria = f' role="img" aria-label="{label}"' if label else ' aria-hidden="true"'
    c = f' class="{cls}"' if cls else ''
    return (f'<svg{c} viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round" focusable="false"{aria}>{body}</svg>')


# --- logo -----------------------------------------------------------------------------------------
_lockups = {}


def lockup(lang, uid):
    """Horizontal lockup, inline. Wordmark ink follows currentColor (twilight 800 on light, white on dark);
    the 'ㅗ' sun stays coral and the symbol keeps the sun gradient."""
    if lang not in _lockups:
        with open(os.path.join(ROOT, 'assets', 'brand', f'lockup-horizontal-{lang}-color.svg'), encoding='utf-8') as f:
            _lockups[lang] = f.read()
    s = _lockups[lang]
    s = re.sub(r'<title>.*?</title>', '', s)
    s = s.replace('fill="#2E2560"', 'class="wm"')
    s = s.replace('id="sun"', f'id="sun-{uid}"').replace('url(#sun)', f'url(#sun-{uid})')
    s = re.sub(r' width="[\d.]+" height="[\d.]+"', '', s, count=1)
    return s.replace('<svg ', '<svg aria-hidden="true" focusable="false" ', 1)


# --- illustrations (decorative, aria-hidden) ----------------------------------------------------
def _sun_defs(uid):
    return (f'<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#FFC45E"/><stop offset=".55" stop-color="#FF7547"/><stop offset="1" stop-color="#EC4A6E"/>'
            f'</linearGradient><radialGradient id="r{uid}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FF7547" stop-opacity=".35"/>'
            f'<stop offset="1" stop-color="#FF7547" stop-opacity="0"/></radialGradient></defs>')


def _phone(x, y, w=58, h=104, inner=''):
    return (f'<g transform="translate({x} {y})"><rect width="{w}" height="{h}" rx="12" fill="#1F1942" stroke="#8274C2" stroke-opacity=".55" stroke-width="1.5"/>'
            f'<rect x="21" y="6" width="16" height="4" rx="2" fill="#8274C2" fill-opacity=".5"/>{inner}</g>')


def _horizon(y, w=320):
    return (f'<rect x="0" y="{y}" width="{w}" height="4" fill="#FFC45E"/>'
            f'<rect x="0" y="{y + 9}" width="{w}" height="3" fill="#FF7547" fill-opacity=".6"/>'
            f'<rect x="0" y="{y + 16}" width="{w}" height="2.5" fill="#EC4A6E" fill-opacity=".4"/>')


def _mini_sun(cx, cy, r, uid):
    return f'<path d="M{cx - r} {cy} a{r} {r} 0 0 1 {2 * r} 0z" fill="url(#g{uid})"/>'


def art(name):
    uid = name
    if name == 'step1':  # same Wi-Fi: one router, two phones under it
        router = ('<g transform="translate(130 44)"><rect width="60" height="24" rx="8" fill="#3B3077" stroke="#A498D6" stroke-opacity=".6" stroke-width="1.5"/>'
                  '<circle cx="14" cy="12" r="2.5" fill="#5FD3AE"/><circle cx="24" cy="12" r="2.5" fill="#FFC45E"/>'
                  '<path d="M44 0V-12M52 0V-9" stroke="#A498D6" stroke-width="3" stroke-linecap="round"/></g>')
        arcs = '<path d="M140 30a28 28 0 0 1 40 0M148 22a17 17 0 0 1 24 0" fill="none" stroke="#FFC45E" stroke-width="3" stroke-linecap="round" opacity=".9" transform="translate(0 -6)"/>'
        links = '<path d="M145 70 98 104M175 70l47 34" stroke="#FFC45E" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>'
        body = (_sun_defs(uid) + f'<ellipse cx="160" cy="176" rx="170" ry="60" fill="url(#r{uid})"/>' + arcs + router + links
                + _phone(52, 96, inner=_mini_sun(29, 66, 14, uid) + '<rect x="12" y="68" width="34" height="2.5" fill="#FFC45E"/>')
                + _phone(210, 96, inner=_mini_sun(29, 66, 14, uid) + '<rect x="12" y="68" width="34" height="2.5" fill="#FFC45E"/>')
                + _horizon(182))
    elif name == 'step2':  # see each other: each phone lists the other
        def row(y, on):
            sun = '<path d="M41 {0}a5 5 0 0 1 10 0z" fill="#FFC45E"/><rect x="39" y="{0}" width="14" height="1.6" fill="#FFC45E"/>'.format(y + 3) if on else ''
            return (f'<circle cx="16" cy="{y}" r="6.5" fill="#C7BFE8" fill-opacity="{0.95 if on else 0.35}"/>'
                    f'<rect x="27" y="{y - 4}" width="{10 if on else 20}" height="3" rx="1.5" fill="#F5F2FA" fill-opacity="{0.9 if on else 0.3}"/>' + sun)
        inner = row(32, True) + row(52, False) + row(72, False)
        link = '<path d="M118 98h84" stroke="#FFC45E" stroke-width="2" stroke-dasharray="2 7" stroke-linecap="round"/><circle cx="160" cy="98" r="5" fill="#FFC45E"/>'
        body = (_sun_defs(uid) + f'<ellipse cx="160" cy="176" rx="170" ry="60" fill="url(#r{uid})"/>' + link
                + _phone(56, 46, w=62, h=112, inner=inner) + _phone(202, 46, w=62, h=112, inner=inner) + _horizon(182))
    elif name == 'step3':  # invite and accept: the bubble (sun) rises between two phones
        sym = ('<g transform="translate(160 86) scale(.36)"><path d="M-99.87,5 A100,100 0 1 1 99.87,5 Z M-98.87,15 H98.87 A100,100 0 0 1 94.22,33.5 H-94.22 A100,100 0 0 1 -98.87,15 Z '
               'M-90.75,42 H90.75 A100,100 0 0 1 82.51,56.5 H-82.51 A100,100 0 0 1 -90.75,42 Z M-76.84,64 H76.84 A100,100 0 0 1 13.92,99.03 C-27.67,104.87 -66,107 -96,107.5 Q-80.5,94.5 -76.84,64 Z" '
               f'fill="url(#s{uid})"/></g>')
        defs = (f'<defs><linearGradient id="s{uid}" gradientUnits="userSpaceOnUse" x1="0" y1="-100" x2="0" y2="102">'
                '<stop offset="0" stop-color="#FFC45E"/><stop offset=".55" stop-color="#FF7547"/><stop offset="1" stop-color="#EC4A6E"/></linearGradient>'
                f'<radialGradient id="r{uid}" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="#FF7547" stop-opacity=".4"/><stop offset="1" stop-color="#FF7547" stop-opacity="0"/></radialGradient></defs>')
        accept = ('<g transform="translate(130 140)"><rect width="60" height="22" rx="11" fill="#FF7547"/>'
                  '<path d="M22 11.5l5 5 10-10" fill="none" stroke="#17132E" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></g>')
        body = (defs + '<ellipse cx="160" cy="96" rx="120" ry="80" fill="url(#rstep3)"/>'
                + _phone(30, 60, w=54, h=98) + _phone(236, 60, w=54, h=98) + sym + accept + _horizon(182))
    elif name == 'office':  # a window at golden hour, two phones on one desk
        sky = (f'<defs><linearGradient id="sky{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#2E2560"/>'
               f'<stop offset=".55" stop-color="#6B3A78"/><stop offset="1" stop-color="#F0806A"/></linearGradient>'
               f'<linearGradient id="g{uid}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#FFC45E"/><stop offset="1" stop-color="#FF7547"/></linearGradient>'
               f'<clipPath id="c{uid}"><rect x="56" y="34" width="288" height="150" rx="14"/></clipPath></defs>')
        window = (f'<g clip-path="url(#c{uid})"><rect x="56" y="34" width="288" height="150" fill="url(#sky{uid})"/>'
                  f'<path d="M154 150a46 46 0 0 1 92 0z" fill="url(#g{uid})"/>'
                  '<rect x="56" y="150" width="288" height="5" fill="#FFC45E"/><rect x="56" y="162" width="288" height="4" fill="#FF7547" fill-opacity=".7"/>'
                  '<rect x="56" y="172" width="288" height="3.5" fill="#EC4A6E" fill-opacity=".5"/></g>'
                  '<rect x="56" y="34" width="288" height="150" rx="14" fill="none" stroke="#A498D6" stroke-opacity=".5" stroke-width="2"/>'
                  '<path d="M200 34v150" stroke="#A498D6" stroke-opacity=".35" stroke-width="2"/>')
        desk = '<rect x="20" y="228" width="360" height="8" rx="4" fill="#4E408F"/><path d="M174 199h52" stroke="#FFC45E" stroke-width="2" stroke-dasharray="2 6" stroke-linecap="round"/>'

        def stand(x, mine):
            fill = '#FF7547' if mine else '#C7BFE8'
            bub = (f'<rect x="{x + (16 if mine else 8)}" y="182" width="26" height="12" rx="6" fill="{fill}"/>'
                   f'<rect x="{x + 8}" y="200" width="{22 if mine else 30}" height="5" rx="2.5" fill="#F5F2FA" fill-opacity=".35"/>')
            return (f'<rect x="{x}" y="170" width="50" height="58" rx="9" fill="#1F1942" stroke="#A498D6" stroke-opacity=".7" stroke-width="2"/>' + bub)
        body = sky + window + desk + stand(118, False) + stand(232, True)
        return f'<svg viewBox="0 0 400 300" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid slice">{body}</svg>'
    else:
        raise KeyError(name)
    return f'<svg viewBox="0 0 320 200" aria-hidden="true" focusable="false" preserveAspectRatio="xMidYMid slice">{body}</svg>'

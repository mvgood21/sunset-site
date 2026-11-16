"""Subset Pretendard into the exact glyphs the built pages paint, per weight.

    python tools/fonts.py        # after tools/build.py; then run tools/build.py again to fold fonts.css into app.css

How
  1. serve the site locally and ask headless Chrome (tools/cdp.mjs glyphs) which characters each page paints
     in the site face, grouped by computed font-weight;
  2. per weight, write up to three WOFF2 files with fontTools:
       latin  ASCII + the punctuation in use           (every page needs it; /en/ pages need only this)
       ko-a   Hangul painted on the home pages          (unicode-range = all Hangul)
       ko-b   Hangul painted only on policy/help pages  (unicode-range = exactly those code points,
              declared last so it is checked first; the home page never matches it, so never downloads it)
  3. write assets/fonts/fonts.css (@font-face rules) and manifest.json (files, sizes, preloads).

Licence: Pretendard is SIL OFL 1.1 with Reserved Font Name "Pretendard". A subset is a Modified Version,
so the subsets are renamed "SunsetTalk Sans" in the name and CFF tables; copyright and licence entries
are kept and the full licence ships as assets/fonts/OFL.txt.
"""
import functools
import hashlib
import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'site.json'), encoding='utf-8'))
BRAND = os.path.normpath(os.path.join(ROOT, CFG['brand_source']))
OUT = os.path.join(ROOT, 'assets', 'fonts')
WEIGHTS = {'400': 'Regular', '600': 'SemiBold', '700': 'Bold', '800': 'ExtraBold'}
HOME = ['/', '/en/']
OTHER = ['/privacy/', '/en/privacy/', '/support/', '/en/support/', '/404.html']
BASE_LATIN = ''.join(chr(c) for c in range(0x20, 0x7F)) + '·–—‘’“”…›‹→←↑↓×±©®™°'
FAMILY = 'Sunset Sans'          # CSS family name used by site.css
INTERNAL = 'SunsetTalk Sans'    # name inside the font files (OFL RFN: not "Pretendard")


def is_ko(ch):
    c = ord(ch)
    return (0x1100 <= c <= 0x11FF or 0x3000 <= c <= 0x303F or 0x3130 <= c <= 0x318F
            or 0xA960 <= c <= 0xA97F or 0xAC00 <= c <= 0xD7AF or 0xD7B0 <= c <= 0xD7FF or 0xFF00 <= c <= 0xFFEF)


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    handler = functools.partial(Quiet, directory=ROOT)
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', 0), handler)
    httpd.handle_error = lambda *a: None  # Chrome closes keep-alive sockets abruptly; not an error
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{httpd.server_address[1]}'


def collect(base):
    jobs = [{'kind': 'glyphs', 'url': base + p} for p in HOME + OTHER]
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(jobs, f)
        jf = f.name
    try:
        r = subprocess.run(['node', os.path.join(ROOT, 'tools', 'cdp.mjs'), 'jobs', jf],
                           capture_output=True, text=True, encoding='utf-8', check=True)
    finally:
        os.unlink(jf)
    res = json.loads(r.stdout)
    home, other = {}, {}
    for job in res:
        if 'error' in job:
            raise SystemExit('glyph collection failed: ' + job['error'])
        path = job['url'][len(base):]
        tgt = home if path in HOME else other
        for w, chars in job['weights'].items():
            if w not in WEIGHTS:
                raise SystemExit(f'{path}: text painted at font-weight {w}, which has no face (use 400/600/700/800)')
            tgt.setdefault(w, set()).update(chars)
    return home, other


def ranges(cps):
    cps = sorted(set(cps))
    out, start, prev = [], None, None
    for c in cps:
        if start is None:
            start = prev = c
        elif c == prev + 1:
            prev = c
        else:
            out.append((start, prev))
            start = prev = c
    if start is not None:
        out.append((start, prev))
    return ','.join(f'U+{a:X}' if a == b else f'U+{a:X}-{b:X}' for a, b in out)


def rename(font, style):
    ps = f'{INTERNAL.replace(" ", "")}-{style}'
    full = f'{INTERNAL} {style}'
    name = font['name']
    for rec in list(name.names):
        if rec.nameID in (1, 16):
            rec.string = INTERNAL
        elif rec.nameID == 4:
            rec.string = full
        elif rec.nameID == 6:
            rec.string = ps
        elif rec.nameID == 3:
            rec.string = f'{ps};subset'
        elif rec.nameID == 17:
            rec.string = style
    if 'CFF ' in font:
        cff = font['CFF '].cff
        cff.fontNames = [ps]
        td = cff.topDictIndex[0]
        td.FullName = full
        td.FamilyName = INTERNAL


def make(weight, text, part):
    style = WEIGHTS[weight]
    src = os.path.join(BRAND, 'fonts', f'Pretendard-{style}.otf')
    opts = subset.Options()
    opts.flavor = 'woff2'
    opts.layout_features = ['kern', 'liga', 'calt', 'ccmp', 'locl', 'mark', 'mkmk', 'tnum']
    opts.name_IDs = ['*']
    opts.name_languages = ['*']
    opts.hinting = False
    opts.desubroutinize = True
    opts.notdef_outline = True
    font = subset.load_font(src, opts)
    sub = subset.Subsetter(opts)
    sub.populate(text=text)
    sub.subset(font)
    rename(font, style)
    tmp = os.path.join(OUT, '_tmp.woff2')
    subset.save_font(font, tmp, opts)
    data = open(tmp, 'rb').read()
    os.unlink(tmp)
    fname = f'st-{weight}-{part}.{hashlib.sha1(data).hexdigest()[:8]}.woff2'
    with open(os.path.join(OUT, fname), 'wb') as f:
        f.write(data)
    return fname, len(data)


def main():
    httpd, base = serve()
    try:
        home, other = collect(base)
    finally:
        httpd.shutdown()
    for f in os.listdir(OUT):
        if f.startswith('st-') and f.endswith('.woff2'):
            os.unlink(os.path.join(OUT, f))
    faces, files, total = [], {}, 0
    preload = {'ko': [], 'en': []}
    for w in WEIGHTS:
        h, o = home.get(w, set()), other.get(w, set())
        latin = {c for c in h | o if not is_ko(c) and c.strip()} | set(BASE_LATIN)
        ko_a = {c for c in h if is_ko(c)}
        ko_b = {c for c in o if is_ko(c)} - ko_a
        for part, chars, urange in (('latin', latin, None), ('ko-a', ko_a, 'U+1100-11FF,U+3000-303F,U+3130-318F,U+A960-A97F,U+AC00-D7AF,U+D7B0-D7FF,U+FF00-FFEF'), ('ko-b', ko_b, None)):
            if not chars:
                continue
            fname, size = make(w, ''.join(sorted(chars)), part)
            total += size
            files[fname] = {'weight': w, 'part': part, 'glyphs': len(chars), 'bytes': size}
            rng = urange or ranges(ord(c) for c in chars)
            faces.append(f'@font-face{{font-family:"{FAMILY}";font-style:normal;font-weight:{w};font-display:swap;'
                         f'src:url(/assets/fonts/{fname}) format("woff2");unicode-range:{rng}}}')
            if w == '800' and part == 'ko-a':
                preload['ko'].append(fname)
            if w == '800' and part == 'latin':
                preload['en'].append(fname)
    css = '/* generated by tools/fonts.py — Pretendard (SIL OFL 1.1) subsets renamed SunsetTalk Sans; see /assets/fonts/OFL.txt */\n' + '\n'.join(faces) + '\n'
    open(os.path.join(OUT, 'fonts.css'), 'w', encoding='utf-8', newline='\n').write(css)
    json.dump({'files': files, 'preload': preload, 'total_bytes': total}, open(os.path.join(OUT, 'manifest.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    for f, m in sorted(files.items(), key=lambda kv: (kv[1]['weight'], kv[1]['part'])):
        print(f"{m['weight']} {m['part']:6} {m['glyphs']:5} glyphs {m['bytes'] / 1024:7.1f} KB  {f}")
    print(f'total {total / 1024:.1f} KB in {len(files)} files')


if __name__ == '__main__':
    sys.exit(main())

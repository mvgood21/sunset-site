"""Derive the site's static assets from the brand kit (beach-of-sunset/brand).

    python tools/brand_assets.py            # everything
    python tools/brand_assets.py og icons   # only some steps: copy icons motion og hero

Needs Pillow; `motion` needs ffmpeg on PATH; `hero` needs Chrome (via tools/cdp.mjs) and node 22.
Run once, or again when the brand kit changes. Outputs are committed; the brand kit is not.

Steps
  copy   SVG marks into assets/brand/, Pretendard OFL text into assets/fonts/
  icons  favicon.svg/.ico, apple-touch-icon, PWA icons (any + maskable)
  motion assets/motion/rise.mp4, set.mp4 (+ .webp posters) — the brand reveal/disconnect clips with
         holds added so the loop breathes, scaled to 720 px
  og     assets/og/og-ko.png, og-en.png (1200x630)
  hero   assets/screens/hero.png + hero-en.png — a brand-styled *placeholder* chat screen. Replace both
         with real device captures (same file names) before launch; build.py re-encodes them to .webp.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'site.json'), encoding='utf-8'))
BRAND = os.path.normpath(os.path.join(ROOT, CFG['brand_source']))
A = os.path.join(ROOT, 'assets')

TWI_TOP, TWI_BOT = (0x2E, 0x25, 0x60), (0x17, 0x13, 0x2E)
SUN = [((0xFF, 0xC4, 0x5E), 0.0), ((0xFF, 0x75, 0x47), 0.55), ((0xEC, 0x4A, 0x6E), 1.0)]


def out(*p):
    path = os.path.join(A, *p)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def brand(*p):
    return os.path.join(BRAND, *p)


# ---------------------------------------------------------------- copy
def step_copy():
    for name in ['symbol-color.svg', 'symbol-small-color.svg', 'symbol-twilight.svg',
                 'lockup-horizontal-ko-color.svg', 'lockup-horizontal-en-color.svg']:
        shutil.copyfile(brand('logo', 'svg', name), out('brand', name))
    shutil.copyfile(brand('fonts', 'Pretendard-LICENSE.txt'), out('fonts', 'OFL.txt'))
    print('copy: brand svgs + OFL')


# ---------------------------------------------------------------- icons
def step_icons():
    shutil.copyfile(brand('logo', 'svg', 'symbol-small-color.svg'), os.path.join(ROOT, 'favicon.svg'))
    s16 = Image.open(brand('logo', 'png', 'symbol-small-color-16.png')).convert('RGBA')
    s32 = Image.open(brand('logo', 'png', 'symbol-small-color-32.png')).convert('RGBA')
    s48 = Image.open(brand('logo', 'png', 'symbol-color-64.png')).convert('RGBA').resize((48, 48), Image.LANCZOS)

    def square(img, n):
        # brand PNGs are not exactly square (the tail makes the symbol taller): centre on a square canvas
        c = Image.new('RGBA', (n, n), (0, 0, 0, 0))
        im = img.copy()
        im.thumbnail((n, n), Image.LANCZOS)
        c.paste(im, ((n - im.width) // 2, (n - im.height) // 2), im)
        return c
    ico = [square(s16, 16), square(s32, 32), square(s48, 48)]
    ico[2].save(os.path.join(ROOT, 'favicon.ico'), sizes=[(16, 16), (32, 32), (48, 48)], append_images=ico[:2])
    tile = Image.open(brand('app-icon', 'ios', 'icon-1024.png')).convert('RGB')
    tile.resize((180, 180), Image.LANCZOS).save(out('icons', 'apple-touch-icon.png'), optimize=True)
    tile.resize((192, 192), Image.LANCZOS).save(out('icons', 'icon-192.png'), optimize=True)
    tile.resize((512, 512), Image.LANCZOS).save(out('icons', 'icon-512.png'), optimize=True)
    # maskable: Android adaptive layers (symbol inside the 66/108 safe zone), upscaled 432 -> 512
    bg = Image.open(brand('app-icon', 'android', 'ic_launcher_background-432.png')).convert('RGBA')
    fg = Image.open(brand('app-icon', 'android', 'ic_launcher_foreground-432.png')).convert('RGBA')
    Image.alpha_composite(bg, fg).convert('RGB').resize((512, 512), Image.LANCZOS).save(out('icons', 'icon-maskable-512.png'), optimize=True)
    print('icons: favicon.svg/.ico, apple-touch, 192/512, maskable')


# ---------------------------------------------------------------- motion
def ff(*args):
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args], check=True)


def step_motion():
    rise_src = brand('motion', 'logo-reveal.mp4')
    set_src = brand('motion', 'disconnect.mp4')
    enc = ['-c:v', 'libx264', '-preset', 'veryslow', '-crf', '27', '-pix_fmt', 'yuv420p',
           '-movflags', '+faststart', '-an', '-tune', 'animation']
    ff('-i', rise_src, '-vf', 'scale=720:720:flags=lanczos,tpad=start_mode=clone:start_duration=0.4:stop_mode=clone:stop_duration=2.4', *enc, out('motion', 'rise.mp4'))
    ff('-i', set_src, '-vf', 'scale=720:720:flags=lanczos,tpad=start_mode=clone:start_duration=1.4:stop_mode=clone:stop_duration=1.6', *enc, out('motion', 'set.mp4'))
    tmp = tempfile.mkdtemp()
    try:
        ff('-sseof', '-0.05', '-i', rise_src, '-frames:v', '1', os.path.join(tmp, 'rise.png'))
        ff('-ss', '0.62', '-i', set_src, '-frames:v', '1', os.path.join(tmp, 'set.png'))
        for n in ('rise', 'set'):
            Image.open(os.path.join(tmp, n + '.png')).convert('RGB').resize((720, 720), Image.LANCZOS) \
                .save(out('motion', n + '-poster.webp'), quality=82, method=6)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('motion: rise/set mp4 + posters')


# ---------------------------------------------------------------- og
def vgrad(w, h, stops):
    """Vertical gradient image from [(rgb, pos)]."""
    img = Image.new('RGB', (1, h))
    px = img.load()
    for y in range(h):
        t = y / max(1, h - 1)
        for i in range(len(stops) - 1):
            (c0, p0), (c1, p1) = stops[i], stops[i + 1]
            if p0 <= t <= p1:
                k = (t - p0) / (p1 - p0) if p1 > p0 else 0
                px[0, y] = tuple(round(c0[j] + (c1[j] - c0[j]) * k) for j in range(3))
                break
    return img.resize((w, h))


def font(weight, size):
    return ImageFont.truetype(brand('fonts', f'Pretendard-{weight}.otf'), size)


def step_og():
    W, H = 1200, 630
    copy = {
        'ko': ('대화는 그 공간에', '두고 가세요.', '같은 Wi-Fi 전용 채팅 · 서버 없이, 가입 없이', 'lockup-horizontal-ko-reverse-192.png'),
        'en': ('Conversations that', 'stay in the room.', 'Same Wi-Fi only · No servers · No sign-up', 'lockup-horizontal-en-reverse-192.png'),
    }
    for lang, (l1, l2, sub, lock) in copy.items():
        img = vgrad(W, H, [(TWI_TOP, 0), (TWI_BOT, 1)]).convert('RGBA')
        # sun on the horizon at the right, with glow underneath
        cx, hy, R = 930, 470, 210
        glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.ellipse((cx - 420, hy - 260, cx + 420, hy + 260), fill=(255, 117, 71, 80))
        glow = glow.filter(ImageFilter.GaussianBlur(110))
        img = Image.alpha_composite(img, glow)
        sun = vgrad(2 * R, 2 * R, SUN).convert('RGBA')
        mask = Image.new('L', (2 * R * 4, 2 * R * 4), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, 2 * R * 4 - 1, 2 * R * 4 - 1), fill=255)
        mask = mask.resize((2 * R, 2 * R), Image.LANCZOS)
        mask = mask.crop((0, 0, 2 * R, R))  # top half only: the sun sits on the horizon
        img.paste(sun.crop((0, 0, 2 * R, R)), (cx - R, hy - R), mask)
        d = ImageDraw.Draw(img)
        # horizon + two waves: lines end at the canvas edge
        d.rectangle((0, hy, W, hy + 10), fill=(255, 196, 94))
        d.rectangle((0, hy + 34, W, hy + 42), fill=(255, 117, 71, 255))
        d.rectangle((0, hy + 62, W, hy + 69), fill=(236, 74, 110, 255))
        lk = Image.open(brand('logo', 'png', lock)).convert('RGBA')
        lk.thumbnail((360, 64), Image.LANCZOS)
        img.alpha_composite(lk, (80, 70))
        size = 76 if lang == 'ko' else 70
        f = font('ExtraBold', size)
        d.text((80, 190), l1, font=f, fill=(255, 255, 255))
        d.text((80, 190 + int(size * 1.22)), l2, font=f, fill=(255, 255, 255))
        d.text((80, 190 + int(size * 2.44) + 22), sub, font=font('Medium', 30), fill=(0xC7, 0xBF, 0xE8))
        img.convert('RGB').save(out('og', f'og-{lang}.png'), optimize=True)
    print('og: og-ko.png, og-en.png')


# ---------------------------------------------------------------- hero placeholder (rendered by Chrome)
HERO_HTML = r"""<!doctype html><html lang="{lang}"><meta charset="utf-8"><style>
@font-face{{font-family:P;src:url("{fonts}/Pretendard-Regular.otf");font-weight:400}}
@font-face{{font-family:P;src:url("{fonts}/Pretendard-SemiBold.otf");font-weight:600}}
@font-face{{font-family:P;src:url("{fonts}/Pretendard-Bold.otf");font-weight:700}}
*{{box-sizing:border-box}}html,body{{margin:0}}
body{{width:390px;height:844px;background:#FFFAF6;font-family:P,sans-serif;color:#1E1A22;display:flex;flex-direction:column;overflow:hidden;word-break:keep-all}}
.status{{height:50px;display:flex;align-items:flex-end;justify-content:space-between;padding:0 30px 8px;font-weight:600;font-size:15px}}
.status .r{{display:flex;gap:6px;align-items:center}}.status i{{display:block;background:#1E1A22;border-radius:2px}}
.bar{{display:flex;align-items:center;gap:12px;padding:10px 16px 12px;border-bottom:1px solid #E7DDD5;background:#FFFFFF}}
.bar .back{{width:24px;height:24px}}
.av{{width:40px;height:40px;border-radius:50%;background:#F4ECE5;display:grid;place-items:center;font-size:22px}}
.who b{{display:block;font-size:17px;font-weight:700}}
.who span{{display:flex;align-items:center;gap:6px;font-size:12.5px;color:#17775F;font-weight:600}}
.who span:before{{content:"";width:12px;height:6px;border-radius:12px 12px 0 0;background:#17775F;margin-bottom:2px}}
.list{{flex:1;padding:14px 16px 8px;display:flex;flex-direction:column;justify-content:flex-end;gap:8px}}
.day{{align-self:center;font-size:12px;color:#5C5257;background:#F4ECE5;border-radius:999px;padding:5px 12px;margin:2px 0 10px;font-weight:600}}
.m{{max-width:78%;padding:10px 14px;font-size:16px;line-height:23px;border-radius:20px}}
.t{{align-self:flex-start;background:#F4ECE5;border-bottom-left-radius:6px}}
.y{{align-self:flex-end;background:#E65A2C;color:#17132E;border-bottom-right-radius:6px}}
.meta{{align-self:flex-end;font-size:12px;color:#5C5257;margin:-2px 2px 6px;font-weight:500}}
.verify{{margin:6px 0 10px;padding:12px 14px;border-radius:16px;background:#DDF3EB;color:#17775F;font-size:13.5px;line-height:19px;font-weight:600}}
.input{{display:flex;gap:10px;align-items:center;padding:10px 12px 30px;background:#FFFFFF;border-top:1px solid #E7DDD5}}
.field{{flex:1;height:44px;border-radius:22px;background:#F4ECE5;color:#857A76;display:flex;align-items:center;padding:0 16px;font-size:15.5px}}
.send{{width:44px;height:44px;border-radius:50%;background:#E65A2C;display:grid;place-items:center}}
</style><body>
<div class="status"><span>5:42</span><span class="r"><i style="width:17px;height:11px"></i><i style="width:15px;height:11px;border-radius:3px"></i><i style="width:25px;height:12px;border-radius:4px"></i></span></div>
<div class="bar"><svg class="back" viewBox="0 0 24 24" fill="none" stroke="#1E1A22" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>
<div class="av">🌿</div><div class="who"><b>{name}</b><span>{status}</span></div></div>
<div class="list">
<div class="day">{day}</div>
<div class="verify">{verify}</div>
<div class="m t">{m0}</div>
<div class="m y">{m00}</div>
<div class="meta">{meta0}</div>
<div class="m t">{m1}</div>
<div class="m y">{m2}</div>
<div class="m t">{m3}</div>
<div class="m y">{m4}</div>
<div class="meta">{meta}</div>
</div>
<div class="input"><div class="field">{ph}</div><div class="send"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#17132E" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M5 12l7-7 7 7"/></svg></div></div>
</body></html>"""

HERO_COPY = {
    'ko': dict(name='지우', status='같은 Wi-Fi · 암호화됨', day='오늘 · 같은 Wi-Fi로 연결됨',
               verify='지우님과 지문을 확인했어요. 지금 연결된 상대가 맞아요.',
               m0='리뷰 자료 공유 폴더에 올렸어요', m00='확인했어요, 고마워요', meta0='오후 4:18',
               m1='회의 끝나고 3층 회의실 비어 있대요', m2='좋아요, 5분 뒤에 갈게요',
               m3='자료는 제 노트북으로 띄울게요', m4='네, 저는 지난주 숫자만 다시 볼게요',
               meta='오후 5:42 · 두 폰에만 저장됨', ph='메시지 입력'),
    'en': dict(name='Jiwoo', status='Same Wi-Fi · Encrypted', day='Today · Connected on the same Wi-Fi',
               verify='You checked fingerprints with Jiwoo. You are talking to the right person.',
               m0='Review notes are in the shared folder', m00='Got them, thanks', meta0='4:18 PM',
               m1='Meeting room on 3 is free after this', m2="Great, I'll be there in 5",
               m3="I'll put the deck up from my laptop", m4="Perfect. I'll recheck last week's numbers",
               meta='5:42 PM · Stored on your two phones only', ph='Message'),
}


def step_hero():
    fonts = 'file:///' + brand('fonts').replace('\\', '/')
    tmp = tempfile.mkdtemp()
    jobs = []
    try:
        for lang, c in HERO_COPY.items():
            html = os.path.join(tmp, f'hero-{lang}.html')
            with open(html, 'w', encoding='utf-8') as f:
                f.write(HERO_HTML.format(lang=lang, fonts=fonts, **c))
            name = 'hero.png' if lang == 'ko' else 'hero-en.png'
            jobs.append({'kind': 'render', 'url': 'file:///' + html.replace('\\', '/'), 'out': out('screens', name),
                         'w': 390, 'h': 844, 'scale': 2})
        jf = os.path.join(tmp, 'jobs.json')
        json.dump(jobs, open(jf, 'w'))
        r = subprocess.run(['node', os.path.join(ROOT, 'tools', 'cdp.mjs'), 'jobs', jf], capture_output=True, text=True, check=True)
        for res in json.loads(r.stdout):
            if 'error' in res:
                raise SystemExit(res['error'])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print('hero: placeholder screens/hero.png, hero-en.png (replace with real captures)')


STEPS = {'copy': step_copy, 'icons': step_icons, 'motion': step_motion, 'og': step_og, 'hero': step_hero}

if __name__ == '__main__':
    todo = sys.argv[1:] or list(STEPS)
    for s in todo:
        STEPS[s]()

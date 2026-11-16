"""Build the static site from src/ fragments + site.json.  Python 3.10+ standard library (Pillow optional).

    python tools/build.py            # write every page, sitemap.xml, robots.txt, site.webmanifest, assets/app.css
    python tools/build.py --check    # exit 1 if a rebuild would change any file (run before committing)

Source of truth
  site.json        the one config: base URL, pre-launch noindex switch, store URLs + UTM, placeholder flag
  src/<lang>/*.html  page bodies (what goes inside <main>), with a <!--meta ... --> header and {{tokens}}
  assets/site.css  hand-written styles; assets/fonts/fonts.css (from tools/fonts.py) is prepended into app.css
Everything at the site root (index.html, en/, privacy/, support/, 404.html, sitemap.xml ...) is generated.
"""
import hashlib
import html
import json
import os
import re
import sys
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parts  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'site.json'), encoding='utf-8'))
BASE = CFG['base_url'].rstrip('/')
EMAIL = CFG['contact_email']

# key, lang, source fragment, output file, url path, counterpart key
PAGES = [
    ('home', 'ko', 'src/ko/index.html', 'index.html', '/'),
    ('home', 'en', 'src/en/index.html', 'en/index.html', '/en/'),
    ('privacy', 'ko', 'src/ko/privacy.html', 'privacy/index.html', '/privacy/'),
    ('privacy', 'en', 'src/en/privacy.html', 'en/privacy/index.html', '/en/privacy/'),
    ('support', 'ko', 'src/ko/support.html', 'support/index.html', '/support/'),
    ('support', 'en', 'src/en/support.html', 'en/support/index.html', '/en/support/'),
    ('404', 'ko', 'src/404.html', '404.html', '/404.html'),
]
URL = {(k, l): u for k, l, _s, _o, u in PAGES}

T = {
    'ko': {
        'name': '선셋톡', 'skip': '본문으로 건너뛰기', 'home': '선셋톡 홈',
        'nav': [('/#how', '작동 방식'), ('/#limits', '한계'), ('/#security', '보안'), ('/support/', '도움말')],
        'lang_label': 'English', 'lang_code': 'en', 'nav_label': '주요 메뉴',
        'stores_label': '앱 받기', 'soon': '출시 예정', 'android': 'Android', 'ios': 'iPhone',
        'notify': '출시 소식을 메일로 받기', 'notify_subject': '선셋톡 출시 알림 신청',
        'notify_body': '선셋톡이 출시되면 이 주소로 알려 주세요.',
        'footer_tag': '같은 Wi-Fi 안에서만 열리는 대화. 서버 없이, 가입 없이.',
        'f_privacy': '개인정보처리방침', 'f_support': '도움말·문의', 'f_mail': '메일 보내기',
        'f_made': 'SugarMount가 만듭니다', 'f_nocookie': '이 사이트는 쿠키와 분석 도구를 쓰지 않아요.',
        'shot_note': '예시 화면', 'shot_alt': '선셋톡 대화 화면 예시: 같은 Wi-Fi로 연결된 지우님과 회의실 이야기를 주고받고, 시각 옆에 두 폰에만 저장됨이라고 표시됨',
        'play': '애니메이션 재생', 'pause': '애니메이션 정지', 'play_text': '재생', 'pause_text': '정지',
        'og_locale': 'ko_KR', 'crumb_home': '홈',
    },
    'en': {
        'name': 'Sunset Talk', 'skip': 'Skip to content', 'home': 'Sunset Talk home',
        'nav': [('/en/#how', 'How it works'), ('/en/#limits', 'Limits'), ('/en/#security', 'Security'), ('/en/support/', 'Help')],
        'lang_label': '한국어', 'lang_code': 'ko', 'nav_label': 'Main menu',
        'stores_label': 'Get the app', 'soon': 'Coming soon', 'android': 'Android', 'ios': 'iPhone',
        'notify': 'Get launch news by email', 'notify_subject': 'Sunset Talk launch notice',
        'notify_body': 'Please let me know at this address when Sunset Talk launches.',
        'footer_tag': 'A chat that only opens on the same Wi-Fi. No servers, no sign-up.',
        'f_privacy': 'Privacy policy', 'f_support': 'Help & contact', 'f_mail': 'Email us',
        'f_made': 'Made by SugarMount', 'f_nocookie': 'This site uses no cookies and no analytics.',
        'shot_note': 'Sample screen', 'shot_alt': 'Sample Sunset Talk chat: messages with Jiwoo on the same Wi-Fi about a meeting room, with a note that history is stored on the two phones only',
        'play': 'Play animation', 'pause': 'Pause animation', 'play_text': 'Play', 'pause_text': 'Pause',
        'og_locale': 'en_US', 'crumb_home': 'Home',
    },
}


# ------------------------------------------------------------------ helpers
def read(rel):
    with open(os.path.join(ROOT, rel), encoding='utf-8') as f:
        return f.read()


def esc(s):
    return html.escape(s, quote=True)


def parse_fragment(text):
    m = re.match(r'\s*<!--meta\n(.*?)\n-->\n', text, re.S)
    meta = {}
    if m:
        for line in m.group(1).splitlines():
            if ':' in line:
                k, v = line.split(':', 1)
                meta[k.strip()] = v.strip()
        text = text[m.end():]
    return meta, text


def stores_live():
    s = CFG['stores']
    return bool(s.get('play_url') or s.get('appstore_url'))


def store_url(kind, placement):
    s, u = CFG['stores'], CFG['utm']
    if kind == 'play' and s.get('play_url'):
        ref = f"utm_source={u['source']}&utm_medium={u['medium']}&utm_campaign={placement}"
        url = s['play_url']
        return url + ('&' if '?' in url else '?') + 'referrer=' + quote(ref, safe='')
    if kind == 'appstore' and s.get('appstore_url'):
        url = s['appstore_url']
        q = []
        if s.get('appstore_provider_token'):
            q.append('pt=' + quote(s['appstore_provider_token']))
        q.append('ct=' + quote(f"{u['source']}-{placement}"))
        q.append('mt=8')
        return url + ('&' if '?' in url else '?') + '&'.join(q)
    return ''


def stores(lang, placement):
    t = T[lang]
    items = []
    for kind, top, name in (('play', t['android'], 'Google Play'), ('appstore', t['ios'], 'App Store')):
        url = store_url(kind, placement)
        inner = (f'{parts.icon("phone")}<span><span class="s-top">{top}</span>'
                 f'<span class="s-name">{name}</span></span>')
        if url:
            raw = CFG['stores']['play_url' if kind == 'play' else 'appstore_url']
            pt = CFG['stores'].get('appstore_provider_token', '') if kind == 'appstore' else ''
            items.append(f'<li><a class="store" href="{esc(url)}" rel="noopener" data-store="{kind}" data-base="{esc(raw)}" '
                         f'data-placement="{placement}" data-utm-source="{esc(CFG["utm"]["source"])}" data-utm-medium="{esc(CFG["utm"]["medium"])}"' + (f' data-pt="{esc(pt)}"' if pt else '') + f'>{inner}</a></li>')
        else:
            items.append(f'<li><span class="store soon" aria-disabled="true">{inner}'
                         f'<span class="tag">{t["soon"]}</span></span></li>')
    return f'<ul class="stores" aria-label="{t["stores_label"]}">' + ''.join(items) + '</ul>'


def notify(lang):
    if stores_live() or not CFG.get('notify_mailto'):
        return ''
    t = T[lang]
    href = f'mailto:{EMAIL}?subject={quote(t["notify_subject"])}&body={quote(t["notify_body"])}'
    return f'<p class="cta-note"><a class="inline" href="{esc(href)}">{t["notify"]}</a></p>'


def picture(lang):
    t = T[lang]
    base = 'hero' if lang == 'ko' else 'hero-en'
    png = os.path.join(ROOT, 'assets', 'screens', base + '.png')
    w, h = 780, 1688
    try:
        from PIL import Image
        with Image.open(png) as im:
            w, h = im.size
    except Exception:
        pass
    note = f'<span class="shot-note">{t["shot_note"]}</span>' if CFG.get('hero_is_placeholder') else ''
    webp = f'<source srcset="/assets/screens/{base}.webp" type="image/webp">' if os.path.exists(png[:-4] + '.webp') else ''
    return (f'<div class="phone">{note}<div class="screen"><picture>{webp}'
            f'<img src="/assets/screens/{base}.png" width="{w}" height="{h}" alt="{esc(t["shot_alt"])}" fetchpriority="high"></picture></div></div>')


def reel(lang, which):
    t = T[lang]
    return (f'<video data-src="/assets/motion/{which}.mp4" poster="/assets/motion/{which}-poster.webp" muted loop playsinline '
            f'preload="none" width="720" height="720" aria-hidden="true" tabindex="-1"></video>'
            f'<button class="play" type="button" aria-pressed="false" data-play="{t["play"]}" data-pause="{t["pause"]}" '
            f'data-play-text="{t["play_text"]}" data-pause-text="{t["pause_text"]}" aria-label="{t["play"]}">'
            f'{parts.icon("play")}<span>{t["play_text"]}</span></button>')


def toc(body):
    items = re.findall(r'<h2 id="([^"]+)"[^>]*>(.*?)</h2>', body, re.S)
    lis = ''.join(f'<li><a href="#{i}">{re.sub(r"<[^>]+>", "", txt)}</a></li>' for i, txt in items)
    return lis


def mailto(subject=None):
    href = f'mailto:{EMAIL}' + (f'?subject={quote(subject)}' if subject else '')
    return f'<a href="{esc(href)}">{EMAIL}</a>'


def tokens(body, lang):
    def rep(m):
        name, _, arg = m.group(1).partition(':')
        if name == 'stores':
            return stores(lang, arg or 'page')
        if name == 'notify':
            return notify(lang)
        if name == 'hero':
            return picture(lang)
        if name == 'reel':
            return reel(lang, arg)
        if name == 'icon':
            return parts.icon(arg)
        if name == 'art':
            return parts.art(arg)
        if name == 'email':
            return mailto(arg or None)
        if name == 'effective':
            return CFG['privacy_effective'][lang]
        if name == 'effective_iso':
            return CFG['privacy_effective']['date']
        if name == 'toc':
            return toc(body)
        raise KeyError('unknown token ' + m.group(0))
    return re.sub(r'\{\{([a-z_]+(?::[^}]*)?)\}\}', rep, body)


# ------------------------------------------------------------------ chrome
def header(key, lang, on_twilight):
    t = T[lang]
    other = 'en' if lang == 'ko' else 'ko'
    other_url = URL.get((key, other), URL[('home', other)])
    home = URL[('home', lang)]
    nav = ''.join(f'<a class="nav-sec" href="{h}">{label}</a>' for h, label in t['nav'])
    lang_inner = t['lang_label'] if other == 'en' else f'<span class="sys">{t["lang_label"]}</span>'
    cls = 'site-header on-twilight' if on_twilight else 'site-header'
    return (f'<header class="{cls}"><div class="wrap">'
            f'<a class="logo" href="{home}" aria-label="{t["home"]}">{parts.lockup(lang, "h")}</a>'
            f'<nav class="nav" aria-label="{t["nav_label"]}">{nav}'
            f'<a class="lang" href="{other_url}" hreflang="{other}" lang="{other}">{lang_inner}</a></nav>'
            f'</div></header>')


def footer(lang):
    t = T[lang]
    p = CFG['publisher']
    priv = URL[('privacy', lang)]
    sup = URL[('support', lang)]
    return (f'<footer class="site-footer"><div class="wrap">'
            f'<div class="footer-grid"><div class="footer-brand">'
            f'<a class="logo" href="{URL[("home", lang)]}" aria-label="{t["home"]}">{parts.lockup(lang, "f")}</a>'
            f'<p>{t["footer_tag"]}</p></div>'
            f'<ul class="footer-links"><li><a href="{priv}">{t["f_privacy"]}</a></li><li><a href="{sup}">{t["f_support"]}</a></li>'
            f'<li><a href="mailto:{EMAIL}">{t["f_mail"]}</a></li></ul></div>'
            f'<div class="footer-meta"><span>© 2026 <a href="{p["url"]}">{p["name"]}</a> · {t["f_made"]}</span>'
            f'<span>{t["f_nocookie"]}</span></div>'
            f'</div></footer>')


def jsonld(key, lang, meta, url):
    t = T[lang]
    pub = {'@type': 'Organization', '@id': CFG['publisher']['url'] + '#org', 'name': CFG['publisher']['name'],
           'url': CFG['publisher']['url'], 'email': EMAIL}
    site = {'@type': 'WebSite', '@id': BASE + '/#site', 'url': BASE + '/', 'name': '선셋톡 · Sunset Talk',
            'inLanguage': ['ko', 'en'], 'publisher': {'@id': pub['@id']}}
    graph = [pub, site]
    if key == 'home':
        app = {
            '@type': 'MobileApplication', '@id': BASE + '/#app', 'name': t['name'],
            'alternateName': 'Sunset Talk' if lang == 'ko' else '선셋톡',
            'description': meta['description'], 'url': url, 'inLanguage': lang,
            'image': BASE + f'/assets/og/og-{lang}.png', 'operatingSystem': 'Android, iOS',
            'applicationCategory': 'CommunicationApplication',
            'offers': {'@type': 'Offer', 'price': '0', 'priceCurrency': 'KRW' if lang == 'ko' else 'USD'},
            'publisher': {'@id': pub['@id']}, 'author': {'@id': pub['@id']},
        }
        dl = [store_url('play', 'jsonld'), store_url('appstore', 'jsonld')]
        dl = [d for d in dl if d]
        if dl:
            app['downloadUrl'] = dl if len(dl) > 1 else dl[0]
        graph.append(app)
    elif key != '404':
        graph.append({'@type': 'WebPage', '@id': url + '#page', 'url': url, 'name': meta['title'],
                      'description': meta['description'], 'inLanguage': lang, 'isPartOf': {'@id': site['@id']},
                      'breadcrumb': {'@type': 'BreadcrumbList', 'itemListElement': [
                          {'@type': 'ListItem', 'position': 1, 'name': t['crumb_home'], 'item': BASE + URL[('home', lang)]},
                          {'@type': 'ListItem', 'position': 2, 'name': meta.get('crumb', meta['title']), 'item': url}]}})
    data = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, separators=(',', ':'))
    return f'<script type="application/ld+json">{data}</script>'


def head(key, lang, meta, css_href, preload):
    url = BASE + URL[(key, lang)]
    t = T[lang]
    out = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">',
        f'<title>{esc(meta["title"])}</title>',
        f'<meta name="description" content="{esc(meta["description"])}">',
    ]
    if CFG.get('prelaunch_noindex') or key == '404':
        out.append('<meta name="robots" content="noindex">')
    if key != '404':
        out.append(f'<link rel="canonical" href="{url}">')
        for l in ('ko', 'en'):
            out.append(f'<link rel="alternate" hreflang="{l}" href="{BASE + URL[(key, l)]}">')
        out.append(f'<link rel="alternate" hreflang="x-default" href="{BASE + URL[(key, "ko")]}">')
    out += [
        '<meta name="color-scheme" content="light dark">',
        '<meta name="theme-color" content="#2E2560">' if key == 'home' else
        '<meta name="theme-color" media="(prefers-color-scheme: light)" content="#FBF4EE">'
        '<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#171425">',
        '<link rel="icon" href="/favicon.ico" sizes="48x48">',
        '<link rel="icon" href="/favicon.svg" type="image/svg+xml">',
        '<link rel="apple-touch-icon" href="/assets/icons/apple-touch-icon.png">',
        '<link rel="manifest" href="/site.webmanifest">',
    ]
    for p in preload:
        out.append(f'<link rel="preload" href="{p}" as="font" type="font/woff2" crossorigin>')
    out.append(f'<link rel="stylesheet" href="{css_href}">')
    og_img = BASE + f'/assets/og/og-{lang}.png'
    og_title = meta.get('og_title', meta['title'])
    if key != '404':
        out += [
            '<meta property="og:type" content="website">',
            f'<meta property="og:site_name" content="{"선셋톡" if lang == "ko" else "Sunset Talk"}">',
            f'<meta property="og:title" content="{esc(og_title)}">',
            f'<meta property="og:description" content="{esc(meta["description"])}">',
            f'<meta property="og:url" content="{url}">',
            f'<meta property="og:image" content="{og_img}">',
            '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">',
            f'<meta property="og:image:alt" content="{esc(meta.get("og_alt", og_title))}">',
            f'<meta property="og:locale" content="{t["og_locale"]}">',
            f'<meta property="og:locale:alternate" content="{T["en" if lang == "ko" else "ko"]["og_locale"]}">',
            '<meta name="twitter:card" content="summary_large_image">',
            f'<meta name="twitter:title" content="{esc(og_title)}">',
            f'<meta name="twitter:description" content="{esc(meta["description"])}">',
            f'<meta name="twitter:image" content="{og_img}">',
        ]
    out.append(jsonld(key, lang, meta, url))
    out.append("<script>document.documentElement.className='js'</script>")
    out.append(f'<script src="/assets/site.js?v={asset_hash("assets/site.js")}" defer></script>')
    return '\n'.join(out)


def asset_hash(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return '0'
    return hashlib.sha1(open(p, 'rb').read()).hexdigest()[:10]


# ------------------------------------------------------------------ css + fonts
def app_css():
    fonts = os.path.join(ROOT, 'assets', 'fonts', 'fonts.css')
    css = (open(fonts, encoding='utf-8').read() + '\n' if os.path.exists(fonts) else '') + read('assets/site.css')
    # light minify: drop comments and redundant whitespace (no build-time dependency)
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    css = re.sub(r'\s*\n\s*', '\n', css)
    css = re.sub(r'\n+', '\n', css).strip() + '\n'
    return css


def preloads(key, lang):
    """Hero headline weight, so the largest text paints in the brand face first."""
    manifest = os.path.join(ROOT, 'assets', 'fonts', 'manifest.json')
    if key != 'home' or not os.path.exists(manifest):
        return []
    m = json.load(open(manifest, encoding='utf-8'))
    want = m.get('preload', {}).get(lang, [])
    return [f'/assets/fonts/{f}' for f in want]


# ------------------------------------------------------------------ pages + extras
def render_page(key, lang, src, css_href):
    meta, body = parse_fragment(read(src))
    body = tokens(body, lang)
    home = key == 'home'
    gen = f'<!-- generated by tools/build.py from {src} and site.json: edit those, not this file -->'
    nl = '\n'
    return nl.join([
        '<!doctype html>', gen, f'<html lang="{lang}">', '<head>', head(key, lang, meta, css_href, preloads(key, lang)), '</head>',
        f'<body class="{"home" if home else "page"}">', f'<a class="skip" href="#main">{T[lang]["skip"]}</a>',
        header(key, lang, home), '<main id="main">', body.strip(), '</main>', footer(lang), '</body>', '</html>', ''])


def sitemap():
    rows = []
    for key, lang, _s, _o, u in PAGES:
        if key == '404':
            continue
        alts = ''.join(f'<xhtml:link rel="alternate" hreflang="{l}" href="{BASE + URL[(key, l)]}"/>' for l in ('ko', 'en'))
        alts += f'<xhtml:link rel="alternate" hreflang="x-default" href="{BASE + URL[(key, "ko")]}"/>'
        rows.append(f'<url><loc>{BASE + u}</loc>{alts}</url>')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + '\n'.join(rows) + '\n</urlset>\n')


def robots():
    lines = ['# generated by tools/build.py', 'User-agent: *', 'Allow: /', 'Disallow: /src/', 'Disallow: /tools/']
    if not CFG.get('prelaunch_noindex'):
        lines.append(f'Sitemap: {BASE}/sitemap.xml')
    else:
        lines.append('# pre-launch: every page carries noindex (site.json prelaunch_noindex). Crawling stays allowed so')
        lines.append('# crawlers can see that tag; the Sitemap line returns when the switch is turned off.')
    return '\n'.join(lines) + '\n'


def manifest():
    return json.dumps({
        'name': '선셋톡 · Sunset Talk', 'short_name': '선셋톡', 'lang': 'ko', 'dir': 'ltr',
        'description': '같은 Wi-Fi 안에서만 열리는 대화. 서버 없이, 가입 없이.',
        'start_url': '/', 'scope': '/', 'display': 'browser',
        'background_color': '#FFFAF6', 'theme_color': '#2E2560',
        'icons': [
            {'src': '/assets/icons/icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': '/assets/icons/icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
            {'src': '/assets/icons/icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }, ensure_ascii=False, indent=2) + '\n'


def hero_webp():
    """Re-encode the hero screenshots to WebP when the PNG is newer (drop in a real capture, rebuild)."""
    try:
        from PIL import Image
    except ImportError:
        return
    for base in ('hero', 'hero-en'):
        png = os.path.join(ROOT, 'assets', 'screens', base + '.png')
        webp = png[:-4] + '.webp'
        if os.path.exists(png) and (not os.path.exists(webp) or os.path.getmtime(webp) < os.path.getmtime(png)):
            with Image.open(png) as im:
                im = im.convert('RGB')
                if im.width > 780:
                    im = im.resize((780, round(im.height * 780 / im.width)), Image.LANCZOS)
                im.save(webp, quality=80, method=6)


def outputs():
    files = {}
    css = app_css()
    files['assets/app.css'] = css
    css_href = '/assets/app.css?v=' + hashlib.sha1(css.encode()).hexdigest()[:10]
    for key, lang, src, out, _u in PAGES:
        files[out] = render_page(key, lang, src, css_href)
    files['sitemap.xml'] = sitemap()
    files['robots.txt'] = robots()
    files['site.webmanifest'] = manifest()
    return files


def main():
    check = '--check' in sys.argv
    if not check:
        hero_webp()
    changed = []
    for rel, content in outputs().items():
        path = os.path.join(ROOT, rel)
        old = open(path, encoding='utf-8').read() if os.path.exists(path) else None
        if old != content:
            changed.append(rel)
            if not check:
                os.makedirs(os.path.dirname(path) or ROOT, exist_ok=True)
                with open(path, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(content)
    mode = 'noindex (pre-launch)' if CFG.get('prelaunch_noindex') else 'indexable'
    stores_state = 'live' if stores_live() else 'coming soon'
    if check:
        print(('stale: ' + ', '.join(changed)) if changed else 'up to date')
        sys.exit(1 if changed else 0)
    print(f'built {len(changed)} changed file(s) · {mode} · stores {stores_state}')


if __name__ == '__main__':
    main()

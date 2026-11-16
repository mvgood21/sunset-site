"""Static checks for the built site. Python standard library only.

    python tools/check.py          # exit 1 on any error; warnings and info are printed but don't fail

Errors
  - broken internal links/resources (href, src, srcset, poster, data-src, CSS url()) and missing #anchors
  - <img> without alt; inline <svg>/<video> that is neither aria-hidden nor labelled; <button> without a name
  - banned claims (docs/marketing/01a_positioning_onepager.md "쓰지 않는 말" + 01_market_analysis.md 5.2 + brand voice),
    in visible text, <title>, meta description, OG/Twitter text, alt and aria-label, in both languages.
    Text inside [data-claim-ok] (honest-limit and expert sections) may *name* a limit such as forward secrecy;
    those hits are listed as info, not errors.
  - "free / no ads / #1 / best" in <title> or og:title (store metadata rule, applied to the site too)
  - any external resource (script, stylesheet, font, image, media, iframe, preload): the site makes no third-party requests
  - head basics: one <h1>, <title>, description, lang, canonical + hreflang ko/en/x-default (except 404),
    og:image file exists, JSON-LD parses, robots noindex matches site.json
Info
  - external links (<a href>) by host, so they can be reviewed
"""
import json
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(ROOT, 'site.json'), encoding='utf-8'))
BASE = CFG['base_url'].rstrip('/')
SKIP_DIRS = {'.git', '.review', 'src', 'tools', 'node_modules', '__pycache__'}

# (pattern, note). Korean patterns are plain regexes; English ones are case-insensitive with word boundaries.
BANNED_KO = [
    (r'익명', 'Apple 1.2: anonymous chat'), (r'랜덤', 'Apple 1.2: random chat'), (r'모르는 사람과', 'Apple 1.2'),
    (r'낯선 사람', 'Apple 1.2 / brand voice'), (r'매칭|인연|설렘|만남', 'dating vocabulary (brand voice)'),
    (r'해킹\s*불가|뚫을 수 없', 'unverifiable security claim'), (r'완벽', 'unverifiable ("perfect")'), (r'절대', 'brand voice: no "절대"'),
    (r'군사급|군용', 'military-grade'), (r'추적\s*불가|흔적', 'untraceable / no trace'), (r'사라지는 메시지', 'disappearing messages'),
    (r'전방향\s*비밀성', 'forward secrecy (only as a stated limit)'), (r'Signal\s*수준|시그널\s*수준|Signal 프로토콜', 'Signal comparison'),
    (r'어디서나|언제든', 'anywhere / anytime'), (r'기내|비행기|캠핑|크루즈', 'places it does not work'),
    (r'공공\s*(와이파이|Wi-Fi)\s*(OK|가능|지원)|공용\s*(와이파이|Wi-Fi)\s*(OK|가능|지원)', 'public Wi-Fi works claim'),
    (r'블루투스|Bluetooth|Wi-Fi\s*Direct|와이파이\s*다이렉트|메시(?!지)', 'transport not used in stage 1'),
    (r'카톡|카카오|텔레그램|왓츠앱|WhatsApp|라인 메신저', 'other brands / replacement claim'),
    (r'수집\s*0|수집 제로', '"0 data collected" framing (Play)'), (r'개발자도\s*절대', '"even the developer can never" framing'),
]
BANNED_EN = [
    (r'anonymous', 'Apple 1.2'), (r'random chat|chat with random', 'Apple 1.2'), (r'strangers?', 'Apple 1.2 / brand voice'),
    (r'unhackable|hack-?proof|can\'t be hacked', 'unverifiable'), (r'perfect(ly)? (security|secure|private)', 'unverifiable'),
    (r'military[- ]grade', 'cliché'), (r'untraceable|no trace|leaves? no trace', 'untraceable'),
    (r'disappearing messages', 'not a feature'), (r'forward secrecy', 'forward secrecy (only as a stated limit)'),
    (r'signal[- ]level|signal protocol', 'Signal comparison'), (r'anywhere|any ?time', 'anywhere / anytime'),
    (r'in-?flight|on (a|the) plane|airplane|camping|cruise', 'places it does not work'),
    (r'bluetooth|wi-?fi direct|mesh', 'transport not used in stage 1'),
    (r'kakao(talk)?|telegram|whatsapp|imessage', 'other brands'), (r'dating|match(ing|es)? with', 'dating vocabulary'),
    (r'zero data collect', '"0 data collected" framing (Play)'),
]
TITLE_BANNED = r'무료|광고\s*없음|#1|best|free|no ads|1위'


class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []          # (tag, claim_ok, hidden)
        self.text = []           # (text, claim_ok)
        self.refs = []           # (attr, url, tag)
        self.ids = set()
        self.imgs_no_alt = []
        self.unlabelled = []
        self.h1 = 0
        self.title = ''
        self.in_title = False
        self.meta = {}
        self.links = []
        self.jsonld = []
        self.in_jsonld = False
        self.lang = None
        self.buttons = []

    def claim_ok(self):
        return any(c for _t, c, _h in self.stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'html':
            self.lang = a.get('lang')
        if 'id' in a:
            self.ids.add(a['id'])
        ok = 'data-claim-ok' in a or self.claim_ok()
        void = tag in ('meta', 'link', 'img', 'source', 'br', 'hr', 'input', 'path', 'rect', 'circle', 'ellipse', 'stop')
        if not void:
            self.stack.append((tag, ok, False))
        if tag == 'h1':
            self.h1 += 1
        if tag == 'title':
            self.in_title = True
        if tag == 'meta':
            k = a.get('name') or a.get('property')
            if k:
                self.meta[k] = a.get('content', '')
                if k in ('description', 'og:title', 'og:description', 'twitter:title', 'twitter:description', 'og:image:alt'):
                    self.text.append((a.get('content', ''), False))
        if tag == 'link':
            self.links.append(a)
        if tag == 'script' and a.get('type') == 'application/ld+json':
            self.in_jsonld = True
        for attr in ('href', 'src', 'poster', 'data-src'):
            if a.get(attr):
                self.refs.append((attr, a[attr], tag, a))
        if a.get('srcset'):
            for part in a['srcset'].split(','):
                self.refs.append(('srcset', part.strip().split(' ')[0], tag, a))
        for attr in ('alt', 'aria-label'):
            if a.get(attr):
                self.text.append((a[attr], ok))
        if tag == 'img' and 'alt' not in a:
            self.imgs_no_alt.append(a.get('src'))
        if tag in ('svg', 'video') and a.get('aria-hidden') != 'true' and not a.get('aria-label') and not a.get('aria-labelledby'):
            if not any(t == 'svg' for t, _c, _h in self.stack[:-1]):
                self.unlabelled.append(tag)
        if tag == 'button':
            self.buttons.append(a)

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'script':
            self.in_jsonld = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_jsonld:
            self.jsonld.append(data)
            return
        if self.stack and self.stack[-1][0] in ('script', 'style'):
            return
        if data.strip():
            self.text.append((data, self.claim_ok()))


def site_pages():
    out = []
    for dp, dns, fns in os.walk(ROOT):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for f in fns:
            if f.endswith('.html'):
                out.append(os.path.relpath(os.path.join(dp, f), ROOT).replace('\\', '/'))
    return sorted(out)


def resolve(url, page_rel):
    """Map a same-site URL to a file path; returns (path or None, fragment)."""
    sp = urlsplit(url)
    if sp.scheme in ('mailto', 'tel', 'data'):
        return 'skip', ''
    if sp.scheme in ('http', 'https'):
        if not url.startswith(BASE):
            return 'external', ''
        path = url[len(BASE):] or '/'
        sp = urlsplit(path)
    path = unquote(sp.path)
    if not path:
        target = page_rel
    elif path.startswith('/'):
        target = path.lstrip('/')
    else:
        target = os.path.normpath(os.path.join(os.path.dirname(page_rel), path)).replace('\\', '/')
    if target == '' or target.endswith('/'):
        target += 'index.html'
    return target, sp.fragment


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    errors, warns, info = [], [], []
    pages = site_pages()
    parsed = {}
    for rel in pages:
        p = Page()
        p.feed(open(os.path.join(ROOT, rel), encoding='utf-8').read())
        parsed[rel] = p
    ext_links = {}
    claim_ok_hits = []
    for rel, p in parsed.items():
        is404 = rel == '404.html'
        # head basics
        if not p.title.strip():
            errors.append(f'{rel}: empty <title>')
        if not p.meta.get('description'):
            errors.append(f'{rel}: no meta description')
        if p.h1 != 1:
            errors.append(f'{rel}: {p.h1} <h1> elements (want 1)')
        if p.lang not in ('ko', 'en'):
            errors.append(f'{rel}: <html lang> is {p.lang!r}')
        robots = p.meta.get('robots', '')
        want_noindex = CFG.get('prelaunch_noindex') or is404
        if want_noindex != ('noindex' in robots):
            errors.append(f'{rel}: robots meta {robots!r} does not match prelaunch_noindex={CFG.get("prelaunch_noindex")}')
        if not is404:
            canon = [l for l in p.links if l.get('rel') == 'canonical']
            alts = {l.get('hreflang') for l in p.links if l.get('rel') == 'alternate' and l.get('hreflang')}
            if len(canon) != 1:
                errors.append(f'{rel}: {len(canon)} canonical links')
            if alts != {'ko', 'en', 'x-default'}:
                errors.append(f'{rel}: hreflang set {sorted(alts)}')
            og = p.meta.get('og:image', '')
            tgt, _ = resolve(og, rel)
            if tgt in ('external', 'skip') or not os.path.exists(os.path.join(ROOT, tgt)):
                errors.append(f'{rel}: og:image {og} missing')
        for block in p.jsonld:
            try:
                json.loads(block)
            except ValueError as e:
                errors.append(f'{rel}: JSON-LD does not parse: {e}')
        # a11y basics
        for src in p.imgs_no_alt:
            errors.append(f'{rel}: <img src={src}> without alt')
        for tag in p.unlabelled:
            errors.append(f'{rel}: <{tag}> neither aria-hidden nor labelled')
        for b in p.buttons:
            if not (b.get('aria-label') or b.get('aria-labelledby')):
                warns.append(f'{rel}: <button> relies on inner text for its name ({b.get("class")})')
        # links and resources
        for attr, url, tag, a in p.refs:
            tgt, frag = resolve(url, rel)
            if tgt == 'skip':
                continue
            if tgt == 'external':
                is_resource = tag in ('script', 'img', 'source', 'video', 'audio', 'iframe') or \
                    (tag == 'link' and a.get('rel') in ('stylesheet', 'preload', 'icon', 'manifest', 'apple-touch-icon', 'modulepreload'))
                if is_resource:
                    errors.append(f'{rel}: external resource {url}')
                elif tag == 'a':
                    ext_links.setdefault(urlsplit(url).netloc, set()).add(url)
                continue
            if tag == 'link' and a.get('rel') in ('canonical', 'alternate'):
                pass
            if not os.path.exists(os.path.join(ROOT, tgt)):
                errors.append(f'{rel}: broken {attr}="{url}" ({tgt})')
            elif frag and tgt.endswith('.html'):
                target_ids = parsed[tgt].ids if tgt in parsed else set()
                if frag not in target_ids:
                    errors.append(f'{rel}: missing anchor #{frag} in {tgt}')
        # claims
        rules = BANNED_KO + [(r'(?i)\b(?:' + pat + r')\b', note) for pat, note in BANNED_EN]
        for text, ok in p.text:
            for pat, note in rules:
                for m in re.finditer(pat, text):
                    snippet = text[max(0, m.start() - 24): m.end() + 24].replace('\n', ' ').strip()
                    (claim_ok_hits if ok else errors).append(f'{rel}: "{m.group(0)}" ({note}) … {snippet} …')
        for t in (p.title, p.meta.get('og:title', '')):
            if re.search(TITLE_BANNED, t, re.I):
                errors.append(f'{rel}: store-style banned word in title: {t}')
    # CSS url() references
    for css in ('assets/app.css',):
        path = os.path.join(ROOT, css)
        if os.path.exists(path):
            for url in re.findall(r'url\(([^)]+)\)', open(path, encoding='utf-8').read()):
                url = url.strip('\'"')
                if url.startswith('data:'):
                    continue
                if url.startswith('http'):
                    errors.append(f'{css}: external url({url})')
                elif not os.path.exists(os.path.join(ROOT, url.lstrip('/'))):
                    errors.append(f'{css}: broken url({url})')
    # sitemap entries
    sm = os.path.join(ROOT, 'sitemap.xml')
    if os.path.exists(sm):
        for loc in re.findall(r'<loc>([^<]+)</loc>', open(sm, encoding='utf-8').read()):
            tgt, _ = resolve(loc, 'index.html')
            if not os.path.exists(os.path.join(ROOT, tgt)):
                errors.append(f'sitemap.xml: {loc} has no file')
    for host, urls in sorted(ext_links.items()):
        info.append(f'external link host {host}: {len(urls)} url(s): ' + ', '.join(sorted(urls)))
    print(f'checked {len(pages)} pages: {", ".join(pages)}')
    for line in info:
        print('info  ', line)
    for line in claim_ok_hits:
        print('ok    ', '[limit/expert context]', line)
    for line in warns:
        print('warn  ', line)
    for line in errors:
        print('ERROR ', line)
    print(f'{len(errors)} error(s), {len(warns)} warning(s), {len(claim_ok_hits)} limit-context mention(s)')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()

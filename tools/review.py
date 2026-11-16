"""Screenshots and a runtime audit of the built site in headless Chrome (tools/cdp.mjs).

    python tools/review.py                 # every page at 360x800 and 1440x900, light and dark -> .review/*.png
    python tools/review.py --audit-only    # only the audit (bytes per page, external requests, overflow, font fallback)
    python tools/review.py --pages / /en/  # limit pages

Output goes to .review/ (git-ignored). The audit fails (exit 1) on any external request, horizontal overflow,
missing glyph (text painted in a non-site font), failed request or script error.
"""
import argparse
import functools
import http.server
import json
import os
import socketserver
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEW = os.path.join(ROOT, '.review')
PAGES = ['/', '/en/', '/privacy/', '/en/privacy/', '/support/', '/en/support/', '/404.html']
SIZES = [(360, 800), (1440, 900)]


def serve():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            # GitHub Pages serves with caching; the audit disables cache itself
            super().end_headers()
    httpd = socketserver.ThreadingTCPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=ROOT))
    httpd.handle_error = lambda *a: None  # Chrome closes keep-alive sockets abruptly; not an error
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f'http://127.0.0.1:{httpd.server_address[1]}'


def run(jobs):
    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
        json.dump(jobs, f)
        jf = f.name
    try:
        r = subprocess.run(['node', os.path.join(ROOT, 'tools', 'cdp.mjs'), 'jobs', jf],
                           capture_output=True, text=True, encoding='utf-8')
        if r.returncode:
            sys.exit(r.stderr)
        return json.loads(r.stdout)
    finally:
        os.unlink(jf)


def slug(p):
    return {'/': 'home-ko', '/en/': 'home-en'}.get(p, p.strip('/').replace('/', '-').replace('.html', '') or 'home')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audit-only', action='store_true')
    ap.add_argument('--pages', nargs='*', default=PAGES)
    a = ap.parse_args()
    os.makedirs(REVIEW, exist_ok=True)
    httpd, base = serve()
    try:
        jobs = []
        if not a.audit_only:
            for p in a.pages:
                for w, h in SIZES:
                    for dark in (False, True):
                        jobs.append({'kind': 'shot', 'url': base + p, 'w': w, 'h': h, 'dark': dark,
                                     'out': os.path.join(REVIEW, f'{slug(p)}-{w}-{"dark" if dark else "light"}.png')})
        for p in a.pages:
            jobs.append({'kind': 'audit', 'url': base + p, 'w': 360, 'h': 800})
        jobs.append({'kind': 'audit', 'url': base + '/', 'w': 320, 'h': 640})
        jobs.append({'kind': 'audit', 'url': base + '/en/', 'w': 320, 'h': 640})
        res = run(jobs)
    finally:
        httpd.shutdown()
    bad = 0
    report = []
    for r in res:
        if 'error' in r:
            print('ERROR', r.get('url'), r['error'])
            bad += 1
            continue
        if r['kind'] != 'audit':
            continue
        path = r['url'][len(base):]
        by_type = {}
        for q in r['requests']:
            by_type[q['type']] = by_type.get(q['type'], 0) + (q['bytes'] or 0)
        problems = []
        if r['external']:
            problems.append('external: ' + ', '.join(r['external']))
        if r['layout']['scrollWidth'] > r['layout']['clientWidth']:
            problems.append(f"overflow {r['layout']['scrollWidth']}>{r['layout']['clientWidth']} {r['layout']['overflowing']}")
        if r['fallback']:
            problems.append('fallback fonts: ' + json.dumps(r['fallback'], ensure_ascii=False))
        failed = [q['url'] for q in r['requests'] if q.get('failed') or (q.get('status') or 200) >= 400]
        if failed:
            problems.append('failed: ' + ', '.join(failed))
        if r['errors']:
            problems.append('script errors: ' + '; '.join(r['errors']))
        bad += bool(problems)
        kb = {k: round(v / 1024, 1) for k, v in sorted(by_type.items())}
        line = f"{path:16} {r['w']}px  {r['totalBytes'] / 1024:7.1f} KB  {len(r['requests']):2} req  {kb}"
        print(line + ('' if not problems else '\n    ! ' + '\n    ! '.join(problems)))
        report.append({'path': path, 'w': r['w'], 'kb': round(r['totalBytes'] / 1024, 1), 'requests': r['requests'], 'problems': problems})
    json.dump(report, open(os.path.join(REVIEW, 'audit.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('screenshots + audit.json in .review/' if not a.audit_only else 'audit.json in .review/')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()

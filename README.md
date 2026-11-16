# sunset-site

선셋톡(Sunset Talk) 랜딩 — https://sunset.sugarmount21.com (GitHub Pages, `main` 루트. DNS: Cloudflare CNAME `sunset` → `mvgood21.github.io`, DNS only).

정적 파일만 서빙한다. 프레임워크·빌드 서버·외부 요청(분석, 추적, CDN, 외부 글꼴)이 없다. 사이트 전체의 스크립트는 `assets/site.js` 하나(4 KB)다.

## 구조

| 경로 | 무엇 | 누가 쓰나 |
|---|---|---|
| `site.json` | **유일한 설정**: noindex 스위치, 스토어 URL·UTM, 예시 화면 표시, 연락처, 방침 시행일 | 사람 |
| `src/ko/*.html`, `src/en/*.html`, `src/404.html` | 페이지 본문(`<main>` 안). 맨 위 `<!--meta ... -->`에 title/description, 본문에 `{{tokens}}` | 사람 |
| `assets/site.css`, `assets/site.js` | 스타일(브랜드 토큰), 스크립트 | 사람 |
| `index.html`, `en/`, `privacy/`, `en/privacy/`, `support/`, `en/support/`, `404.html`, `sitemap.xml`, `robots.txt`, `site.webmanifest`, `assets/app.css` | **생성물** — 직접 고치지 않는다 | `tools/build.py` |
| `assets/fonts/st-*.woff2`, `fonts.css`, `manifest.json` | 페이지가 실제로 그리는 글자만 담은 Pretendard 서브셋(이름은 OFL 규정대로 "SunsetTalk Sans") | `tools/fonts.py` |
| `assets/brand`, `assets/icons`, `favicon.*`, `assets/og`, `assets/motion`, `assets/screens/hero*.png` | 브랜드 키트에서 만든 자산 | `tools/brand_assets.py` |

토큰: `{{stores:hero}}` 스토어 버튼, `{{notify}}` 출시 알림 메일 링크, `{{hero}}` 휴대폰 목업, `{{reel:rise|set}}` 브랜드 모션, `{{icon:name}}`, `{{art:name}}`, `{{email:제목}}`, `{{effective}}`, `{{toc}}`.

## 명령

```bash
python tools/build.py              # 페이지·sitemap·robots·manifest·app.css 생성
python tools/fonts.py              # 문구가 바뀌면: 글리프 서브셋 다시 만들기 → 그다음 build.py 한 번 더
python tools/check.py              # 깨진 링크·앵커, alt, 금지 표현(ko/en), 외부 리소스, head 기본값
python tools/build.py --check      # 생성물이 최신인지(커밋 전)
python tools/review.py             # 360×800·1440×900 × 라이트·다크 스크린숏 → .review/ + 런타임 감사
python tools/brand_assets.py [copy icons motion og hero]   # 브랜드 키트(../beach-of-sunset/brand)가 바뀌었을 때
```

Git Bash에서 `review.py --pages /`처럼 `/`로 시작하는 인자를 줄 때는 `MSYS_NO_PATHCONV=1`을 앞에 붙인다.

필요한 것: Python 3.12(표준 라이브러리), Pillow, fontTools(+brotli, `fonts.py`만), node 22(헤드리스 Chrome 제어, `tools/cdp.mjs`), Chrome, ffmpeg(`brand_assets.py motion`만). 패키지 설치 없음.

문구를 고친 뒤 순서: `build.py` → `fonts.py` → `build.py` → `check.py` → `review.py`.

## 출시 때 바꿀 것

1. **검색 노출 켜기**: `site.json`의 `"prelaunch_noindex": true` → `false`. 모든 페이지의 `noindex`가 빠지고 `robots.txt`에 `Sitemap:` 줄이 생긴다(404는 계속 noindex).
2. **스토어 링크**: `site.json` `stores.play_url`(예: `https://play.google.com/store/apps/details?id=…`), `stores.appstore_url`(예: `https://apps.apple.com/app/id…`), 있으면 `appstore_provider_token`. 빌드하면 버튼이 "출시 예정"에서 링크로 바뀌고, 출시 알림 메일 링크는 사라지며, JSON-LD에 `downloadUrl`이 들어간다.
   - UTM 기본값: `utm_source=landing&utm_medium=website&utm_campaign=<hero|footer>`(Play는 `referrer=`에, App Store는 `ct=landing-hero`).
   - 방문자가 `?utm_source=…&utm_medium=…&utm_campaign=…`로 들어오면 `site.js`가 그 값을 스토어 링크로 그대로 넘긴다(쿠키·스토리지 없음, `[A-Za-z0-9._-]` 64자로 정제, 버튼 위치는 `utm_content`). App Store `ct`는 40자로 자른다.
   - 공식 스토어 배지를 쓰려면 각 사 가이드의 배지 이미지로 `tools/build.py` `stores()`를 바꾼다(지금은 상표 이미지 없이 텍스트 버튼).
3. **실제 화면**: `assets/screens/hero.png`(한국어 UI)와 `hero-en.png`(영어 UI)를 실기기 캡처로 교체(세로 9:19.5 근처, 폭 780 px 이상). 빌드가 `.webp`를 다시 만든다. 그다음 `site.json` `"hero_is_placeholder": false`로 "예시 화면" 표시를 끈다. 브랜드 규칙상 앱 화면은 실기기 캡처만 쓴다.
4. **개인정보처리방침 소유자 검토**: `src/ko/privacy.html`, `src/en/privacy.html` 상단 HTML 주석(DRAFT FOR OWNER REVIEW)의 6개 항목을 확인하고 주석을 지운다. 시행일은 `site.json` `privacy_effective`.
5. 도움말의 앱 화면 문구(`src/*/support.html` 상단 주석)를 출시 빌드와 맞춘다.

## 규칙

- 금지 표현은 `tools/check.py`(`BANNED_KO`, `BANNED_EN`)가 막는다. 한계·전문가 절처럼 한계를 *밝히는* 곳은 `data-claim-ok` 안에 둔다.
- "인터넷이 끊겨도 대화된다"는 실측 전이라 쓰지 않는다.
- 외부 리소스를 넣지 않는다(`check.py`와 `review.py`가 막는다). 외부 링크(`<a>`)는 괜찮다.
- `.review/`는 git 무시 대상이다.

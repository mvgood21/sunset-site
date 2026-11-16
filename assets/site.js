/* 선셋톡 site — the only script. No network calls, no storage, no tracking.
   1) brand motion clips load and play only while on screen; with reduced motion they stay as posters
      and a button lets the reader play them.  2) gentle reveal of cards on scroll. */
(function () {
  var d = document, root = d.documentElement;
  var mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  var reduced = !!(mq && mq.matches);
  if (reduced) root.classList.add('reduced');

  var vids = [].slice.call(d.querySelectorAll('video[data-src]'));
  var reveal = [].slice.call(d.querySelectorAll('.rv'));
  function load(v) { if (!v.getAttribute('src')) v.setAttribute('src', v.getAttribute('data-src')); }
  function play(v) { load(v); var p = v.play(); if (p && p.catch) p.catch(function () {}); }

  if ('IntersectionObserver' in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        var v = e.target;
        if (e.isIntersecting) { if (!reduced) play(v); }
        else if (!v.paused) v.pause();
      });
    }, { rootMargin: '120px 0px' });
    vids.forEach(function (v) { io.observe(v); });

    var ro = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add('in'); ro.unobserve(e.target); }
      });
    }, { rootMargin: '0px 0px -8% 0px' });
    reveal.forEach(function (el) { ro.observe(el); });
  } else {
    reveal.forEach(function (el) { el.classList.add('in'); });
    if (!reduced) vids.forEach(play);
  }

  // Store links: carry the visitor's incoming utm_source / utm_medium / utm_campaign through to the store.
  // URL parameters only (no cookies, no storage); values are reduced to [A-Za-z0-9._-] and 64 characters.
  // Without parameters the build-time defaults stay (utm_source from site.json, campaign = button placement).
  (function () {
    var links = [].slice.call(d.querySelectorAll('a.store[data-base]'));
    if (!links.length || !location.search) return;
    var q = {};
    location.search.slice(1).split('&').forEach(function (kv) {
      var i = kv.indexOf('='), k = i < 0 ? kv : kv.slice(0, i), v = i < 0 ? '' : kv.slice(i + 1);
      try { k = decodeURIComponent(k.replace(/\+/g, ' ')); v = decodeURIComponent(v.replace(/\+/g, ' ')); } catch (e) { return; }
      if (!(k in q)) q[k] = v;
    });
    function clean(v) { return (v || '').replace(/[^A-Za-z0-9._-]/g, '').slice(0, 64); }
    var src = clean(q.utm_source), med = clean(q.utm_medium), camp = clean(q.utm_campaign);
    if (!src && !med && !camp) return;
    links.forEach(function (a) {
      var base = a.getAttribute('data-base'), place = a.getAttribute('data-placement');
      var s = src || a.getAttribute('data-utm-source'), m = med || a.getAttribute('data-utm-medium');
      var sep = base.indexOf('?') < 0 ? '?' : '&', url;
      if (a.getAttribute('data-store') === 'play') {
        var ref = 'utm_source=' + s + '&utm_medium=' + m + '&utm_campaign=' + (camp || place) + (camp ? '&utm_content=' + place : '');
        url = base + sep + 'referrer=' + encodeURIComponent(ref);
      } else {
        var pt = a.getAttribute('data-pt');
        url = base + sep + (pt ? 'pt=' + encodeURIComponent(pt) + '&' : '') + 'ct=' + encodeURIComponent((s + '-' + (camp || place)).slice(0, 40)) + '&mt=8';
      }
      a.setAttribute('href', url);
    });
  })();

  d.addEventListener('click', function (ev) {
    var b = ev.target.closest ? ev.target.closest('.reel .play') : null;
    if (!b) return;
    var v = b.parentNode.querySelector('video');
    var on = v.paused;
    if (on) play(v); else v.pause();
    b.setAttribute('aria-pressed', on ? 'true' : 'false');
    b.setAttribute('aria-label', b.getAttribute(on ? 'data-pause' : 'data-play'));
    b.querySelector('span').textContent = b.getAttribute(on ? 'data-pause-text' : 'data-play-text');
  });
})();

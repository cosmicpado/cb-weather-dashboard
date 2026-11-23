/* 휴대폰 ⋯ 메뉴(2026-11-20) — 휴대폰 윗줄 오른쪽 ⋯ 단추 하나에 공지사항·의견 보내기·화면 색을 모았다.
   종합 현황·재해별 집중 감시·실시간 상황판 공용. 새 기능이 아니라 화면에 이미 있는 것을 불러 쓴다:
     공지사항 → 도움말.html#notice · 의견 보내기 → cbFeedback.open · 화면 색 → 그 화면의 화면 색 단추를 대신 누른다.
   ⋯ 단추는 화면마다 .hd-more 로 둔다(React 가 다시 그려도 되게 문서 전체에서 누름을 받는다).
   화면이 다르면 window.cbMoreCfg = {page, themeBtn(), isDark()} 로 알려 준다(상황실). 새 공지가 있으면 ⋯ 에 빨간 점. */
(function () {
  var PAGES = { main: '종합 현황', watch: '재해별 집중 감시' };
  function cfg() {
    var c = window.cbMoreCfg || {};
    return {
      page: c.page || PAGES[window.CB_PAGE] || document.title,
      themeBtn: c.themeBtn || function () { return document.querySelector('[aria-label="화면 색"]'); },
      isDark: c.isDark || function () { return document.documentElement.getAttribute('data-theme') === 'dark'; },
      extra: c.extra || function () { return []; }   // 화면만의 메뉴(상황실: 화면 켜 두기) — [{icon, text, fn}]
    };
  }
  function unseen() { try { return window.cbNotices ? window.cbNotices.unseen() : 0; } catch (e) { return 0; } }

  var menu = null;
  function close() {
    if (!menu) return;
    menu.remove(); menu = null;
    document.removeEventListener('keydown', onKey, true);
    var b = document.querySelectorAll('.hd-more'); for (var i = 0; i < b.length; i++) b[i].setAttribute('aria-expanded', 'false');
  }
  function onKey(e) { if (e.key === 'Escape') close(); }
  function item(icon, text, dot, fn) {
    var b = document.createElement('button'); b.type = 'button';
    b.style.cssText = 'display:flex;align-items:center;gap:10px;width:100%;border:0;background:transparent;padding:12px 14px;border-radius:10px;' +
      'font:700 16px "Pretendard Variable",Pretendard,system-ui,sans-serif;color:inherit;text-align:left;cursor:pointer;';
    b.innerHTML = '<span style="width:22px;text-align:center;font-size:18px">' + icon + '</span><span style="flex:1">' + text + '</span>' +
      (dot ? '<span style="width:9px;height:9px;border-radius:50%;background:#ef4444"></span>' : '');
    b.onclick = function () { close(); fn(); };
    return b;
  }
  function open(btn) {
    close();
    var c = cfg(), dark = c.isDark(), r = btn.getBoundingClientRect();
    menu = document.createElement('div'); menu.setAttribute('role', 'menu');
    menu.style.cssText = 'position:fixed;z-index:9950;top:' + Math.round(r.bottom + 8) + 'px;right:' + Math.max(8, Math.round(innerWidth - r.right)) + 'px;' +
      'min-width:210px;padding:6px;border-radius:14px;box-shadow:0 12px 32px -12px rgba(0,0,0,.45);' +
      (dark ? 'background:#151b26;color:#f2f5fa;border:1px solid #2a3446;' : 'background:#fff;color:#101828;border:1px solid #e4e8ef;');
    menu.appendChild(item('📢', '공지사항 · 도움말', unseen() > 0, function () { location.href = '도움말.html#notice'; }));
    menu.appendChild(item('💬', '의견 보내기', false, function () { if (window.cbFeedback) window.cbFeedback.open({ page: c.page }); }));
    menu.appendChild(item(dark ? '☀' : '☾', dark ? '밝게 보기' : '어둡게 보기', false, function () { var t = c.themeBtn(); if (t) t.click(); }));
    c.extra().forEach(function (x) { menu.appendChild(item(x.icon, x.text, false, x.fn)); });
    if (window.cbTour && window.cbTour.has()) menu.appendChild(item('🧭', '화면 안내 다시 보기', false, function () { window.cbTour.start(true); }));   // tour.js
    document.body.appendChild(menu);
    btn.setAttribute('aria-expanded', 'true');
    document.addEventListener('keydown', onKey, true);
  }
  document.addEventListener('click', function (e) {
    var b = e.target.closest && e.target.closest('.hd-more');
    if (b) { e.preventDefault(); if (menu) close(); else open(b); return; }
    if (menu && !menu.contains(e.target)) close();
  });
  window.addEventListener('scroll', close, { passive: true });
  window.addEventListener('resize', close);
  /* 새 공지 빨간 점 */
  function dot() { var n = unseen() > 0, b = document.querySelectorAll('.hd-more'); for (var i = 0; i < b.length; i++) b[i].classList.toggle('has-new', n); }
  setInterval(dot, 5000);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', dot); else dot();
})();

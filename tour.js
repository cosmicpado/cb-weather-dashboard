/* 화면 안내(2026-11-23) — 처음 연 사람에게 한 번만, 주요 부분을 차례로 비추며 설명한다.
   화면을 어둡게 하고 설명할 곳만 밝게 비춘 뒤 옆에 말풍선. [다음]·[건너뛰기], Esc 로 닫기, Enter·→ 로 다음, ← 로 앞.
   한 번 보면(끝까지 또는 건너뛰기) 이 브라우저에 기억해 다시 뜨지 않는다(localStorage cbTour_<안내 이름>).
   1분 동안 아무 조작이 없으면 저절로 닫는다 — 벽면 상황판처럼 사람이 없는 화면에 안내가 계속 덮여 있지 않게.
   다시 보기: PC '/' → guide · 휴대폰 ⋯ 메뉴 '화면 안내 다시 보기'(more-menu.js) · cbTour.start(true).
   안내 이름 = 화면(window.CB_PAGE: main 종합 현황 · wall 실시간 상황판) 또는 상황 이름(wallDemo 시연을 처음 켰을 때).
   새 안내는 TOURS 에 { pc:[…], m:[…] } 로 더한다(m = 휴대폰).
   단계 = { sel: 비출 곳(CSS 선택자, 없거나 안 보이면 가운데), title, text, key: '/' (그 키를 누르면 안내를 마치고 키 동작을 그대로) }
   글에서 `칠 글자`는 글자 상자로, ' / '는 키 모양으로 보인다. */
(function () {
  var VER = '1';
  var KEYCMD = { key: '/', title: '키보드 명령' };
  var TOURS = {
    main: {
      pc: [
        { sel: '.scope', title: '관서 고르기', text: '충북 전체 또는 관서를 고르면 그 관서의 날씨·특보·하천을 봅니다. 고른 관서는 이 PC에 기억됩니다.' },
        { sel: '.pgs', title: '화면 전환', text: '종합 현황 · 재해별 집중 감시(호우·대설·산불 때 관서 비교) · 실시간 상황판(큰 화면용)을 오갑니다.' },
        { sel: '.hd-tools', title: '공지 · 의견 · 알림', text: '공지사항·도움말 · 의견 보내기(불편한 점·틀린 값) · 알림 설정 · 화면 색(어둡게/밝게).' },
        { key: '/', title: KEYCMD.title, text: '키보드에서 / 를 눌러 보세요. 명령 칸이 열립니다.\n영어 명령을 치고 Enter — `wall` 상황판 · `help` 도움말 · `guide` 이 안내 다시 보기' }
      ],
      m: [
        { sel: '.scope', title: '관서 고르기', text: '충북 전체 또는 관서를 고르면 그 관서의 날씨·특보·하천을 봅니다. 고른 관서는 이 휴대폰에 기억됩니다.' },
        { sel: '.pgs', title: '아래 탭', text: '종합 · 집중감시 · 상황판 화면을 오갑니다.' },
        { sel: '.hd-more', title: '⋯ 더보기', text: '공지사항·도움말, 의견 보내기, 화면 색을 여기서 고릅니다. 이 안내도 여기서 다시 볼 수 있습니다.' }
      ]
    },
    wall: {
      pc: [
        { sel: '[data-rail]', title: '관서 순환', text: '관서가 14초마다 차례로 넘어갑니다. 아래 관서 칸을 누르면 그 관서로 바로 갑니다.' },
        { sel: '[data-ctl]', title: '멈춤 · 넘기기', text: '❚❚ 순환 멈춤/다시 · ‹ › 이전·다음 관서 · 화면 밝기를 바꿉니다.' },
        { sel: '[data-tally]', title: '충북 현황', text: '호우·대설·태풍 예비특보·주의보·경보가 걸린 충북 시·군 수입니다. 비상단계가 되면 왼쪽에 단계와 비상근무 칸이 나타납니다.' },
        { sel: '#wall-tools', title: '왼쪽 위 도구', text: '종합 현황으로 · 공지사항·도움말 · 알림 소리 · 배치 편집 · 의견 보내기.' },
        { key: '/', title: KEYCMD.title, text: '키보드에서 / 를 눌러 보세요. 명령 칸이 열립니다.\n영어 명령을 치고 Enter — `stage` 비상단계 지정 · `test` 시연 단추 · `guide` 이 안내 다시 보기' }
      ],
      m: [
        { sel: '#wall-msel .nm', title: '관서 고르기', text: '관서를 고르면 그 관서의 실시간 상황판을 봅니다.' },
        { sel: '#wall-urg', title: '충북 현황', text: '호우·대설·태풍 예비특보·주의보·경보가 걸린 충북 시·군 수와 재난문자 수입니다.' },
        { sel: '#wall-msel .hd-more', title: '⋯ 더보기', text: '공지사항·도움말, 의견 보내기, 화면 색, 화면 켜 두기. 이 안내도 여기서 다시 볼 수 있습니다.' },
        { sel: '.mpg', title: '아래 탭', text: '종합 · 집중감시 · 상황판 화면을 오갑니다.' }
      ]
    },
    wallDemo: {   // 시연을 처음 켰을 때(상황판 ▶ 시연)
      pc: [
        { sel: '[data-demobar]', title: '시연 중입니다', text: '가상 상황으로 화면이 어떻게 바뀌는지 봅니다. 실제 자료는 바뀌지 않고 이 화면에만 보입니다.' },
        { sel: '[data-demobar] [data-demo-steps]', title: '단계 고르기', text: '준비 · 1~3단계 · 계절(누를 때마다 한파 → 폭염 → 건조) · 지진. 단계마다 특보·재난문자·하천이 함께 바뀝니다.' },
        { sel: '[data-demobar] > a', title: '시연 끝내기', text: '\'시연 중\'을 누르면 실제 자료로 돌아갑니다. 켠 채 자리를 비우면 실제 상황으로 오해할 수 있습니다.' }
      ]
    }
  };
  var PAGE = window.CB_PAGE || '';
  function phone() { try { return window.matchMedia('(max-width:820px)').matches; } catch (e) { return false; } }
  function stepsOf(name) { var t = TOURS[name]; return t ? ((phone() && t.m) ? t.m : t.pc) : null; }
  function done(name) { try { return localStorage.getItem('cbTour_' + name) === VER; } catch (e) { return true; } }
  function remember(name) { try { localStorage.setItem('cbTour_' + name, VER); } catch (e) {} }

  /* 말풍선은 어두운 화면(상황판)에서도 읽히게 늘 흰 바탕. 글자 크기는 em — 큰 벽면 화면에선 화면 폭에 맞춰 커진다 */
  var css = document.createElement('style');
  css.textContent =
    '.cbtour{position:fixed;inset:0;z-index:2147482400}' +
    '.cbtour .hole{position:fixed;border-radius:12px;box-shadow:0 0 0 200vmax rgba(10,16,28,.6);transition:all .25s ease;pointer-events:none}' +
    '.cbtour .hole.none{left:50%!important;top:42%!important;width:0!important;height:0!important}' +
    '.cbtour .bub{position:fixed;font-size:clamp(14.5px,1.05vw,28px);width:min(24em,calc(100vw - 24px));box-sizing:border-box;background:#fff;color:#101828;' +
      'border:1px solid #e4e8ef;border-radius:14px;padding:1em 1.1em .85em;box-shadow:0 18px 44px -14px rgba(0,0,0,.55);' +
      'font-family:"Pretendard Variable",Pretendard,system-ui,sans-serif;transition:top .25s ease,left .25s ease}' +
    '.cbtour .n{font-size:.9em;font-weight:700;color:#5f6d85}' +
    '.cbtour h4{margin:.2em 0 .4em;font-size:1.17em;font-weight:800;color:#101828}' +
    '.cbtour p{margin:0;font-size:1em;line-height:1.6;color:#334155;white-space:pre-line}' +
    '.cbtour kbd{display:inline-flex;align-items:center;justify-content:center;min-width:1.8em;height:1.8em;padding:0 .4em;border-radius:7px;border:1px solid #c9d2df;border-bottom-width:3px;font:800 1em inherit;background:#f2f5fa;color:#101828;margin:0 2px;vertical-align:-.15em}' +
    '.cbtour code{font:800 .97em Consolas,ui-monospace,monospace;color:#1d4ed8;background:#f2f5fa;border:1px solid #e4e8ef;border-radius:6px;padding:0 .35em}' +
    '.cbtour .bar{display:flex;align-items:center;gap:.55em;margin-top:.85em}' +
    '.cbtour button{font:inherit;font-size:.97em;font-weight:800;border-radius:9px;padding:.45em 1em;cursor:pointer;border:1px solid #dde3ec;background:#fff;color:#334155}' +
    '.cbtour button.go{margin-left:auto;background:#1d4ed8;border-color:#1d4ed8;color:#fff}' +
    '.cbtour button:focus-visible{outline:2px solid #1d4ed8;outline-offset:2px}' +
    '.cbtour .dots{display:flex;gap:4px}.cbtour .dots i{width:.42em;height:.42em;border-radius:50%;background:#c9d2df}.cbtour .dots i.on{background:#1d4ed8}' +
    '@media (prefers-reduced-motion:reduce){.cbtour .hole,.cbtour .bub{transition:none}}';
  (document.head || document.documentElement).appendChild(css);

  var root = null, hole, bub, list, at = 0, cur = '', idle = 0;
  function close() {
    if (!root) return;
    root.remove(); root = null; remember(cur); clearTimeout(idle);
    document.removeEventListener('keydown', onKey, true);
    window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true);
  }
  function poke() { clearTimeout(idle); idle = setTimeout(close, 60000); }   // 1분 동안 조작이 없으면 닫는다
  function target() {
    var s = list[at];
    if (!s.sel) return null;
    var els = document.querySelectorAll(s.sel);
    for (var i = 0; i < els.length; i++) { var r = els[i].getBoundingClientRect(); if (r.width > 0 && r.height > 0) return els[i]; }
    return null;
  }
  function place() {
    if (!root) return;
    var el = target(), bw = bub.offsetWidth, bh = bub.offsetHeight, W = innerWidth, H = innerHeight, pad = 6;
    if (!el) {
      hole.classList.add('none');
      bub.style.left = Math.round((W - bw) / 2) + 'px'; bub.style.top = Math.round(H * 0.42 - bh / 2) + 'px'; return;
    }
    hole.classList.remove('none');
    var r = el.getBoundingClientRect();
    hole.style.left = (r.left - pad) + 'px'; hole.style.top = (r.top - pad) + 'px';
    hole.style.width = (r.width + pad * 2) + 'px'; hole.style.height = (r.height + pad * 2) + 'px';
    var below = r.bottom + pad + 12, above = r.top - pad - 12 - bh;
    var top = (below + bh <= H - 8) ? below : (above >= 8 ? above : Math.max(8, H - bh - 8));
    var left = Math.min(Math.max(8, r.left + r.width / 2 - bw / 2), W - bw - 8);
    bub.style.top = Math.round(top) + 'px'; bub.style.left = Math.round(left) + 'px';
  }
  function esc(t) { return String(t).replace(/[&<>]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]; }); }
  function show() {
    var s = list[at], last = at === list.length - 1;
    var text = esc(s.text).replace(/(^|\s)\/(\s|$)/g, '$1<kbd>/</kbd>$2').replace(/`([^`]+)`/g, '<code>$1</code>');
    bub.innerHTML = '<div class="n">' + (at + 1) + ' / ' + list.length + '</div><h4></h4><p>' + text + '</p>' +
      '<div class="bar"><div class="dots">' + list.map(function (x, i) { return '<i' + (i === at ? ' class="on"' : '') + '></i>'; }).join('') + '</div>' +
      (last ? '' : '<button type="button" class="skip">건너뛰기</button>') +
      '<button type="button" class="go">' + (last ? (s.key ? '끝내기' : '확인') : '다음') + '</button></div>';
    bub.querySelector('h4').textContent = s.title;
    bub.querySelector('.go').onclick = next;
    var sk = bub.querySelector('.skip'); if (sk) sk.onclick = close;
    setTimeout(function () { var g = bub && bub.querySelector('.go'); if (g) g.focus(); }, 250);   // 띄운 키(Enter)가 [다음]까지 누르지 않게 조금 늦게
    place(); poke();
  }
  function next() { if (at < list.length - 1) { at++; show(); } else close(); }
  function onKey(e) {
    var s = list[at]; poke();
    if (s.key && e.key === s.key) { close(); return; }               // 그 키 동작(명령 칸 열기)은 그대로 이어진다
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
    else if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); next(); }
    else if (e.key === 'ArrowLeft' && at > 0) { e.preventDefault(); e.stopPropagation(); at--; show(); }
    else if (!s.key) { e.stopPropagation(); }                           // 안내 중엔 다른 단축키가 끼어들지 않게
  }
  /* start(force, name) — name 을 빼면 이 화면 안내. force 면 본 적 있어도 다시 */
  function start(force, name) {
    name = name || PAGE;
    var l = stepsOf(name);
    if (!l || root || (!force && done(name))) return false;
    list = l; at = 0; cur = name;
    root = document.createElement('div'); root.className = 'cbtour'; root.setAttribute('role', 'dialog'); root.setAttribute('aria-label', '화면 안내');
    hole = document.createElement('div'); hole.className = 'hole';
    bub = document.createElement('div'); bub.className = 'bub';
    root.appendChild(hole); root.appendChild(bub); document.body.appendChild(root);
    root.addEventListener('pointerdown', poke);
    document.addEventListener('keydown', onKey, true);
    window.addEventListener('resize', place); window.addEventListener('scroll', place, true);
    show();
    return true;
  }
  window.cbTour = { start: start, has: function (name) { return !!TOURS[name || PAGE]; } };

  /* 처음 한 번 — 로딩 화면·명령 칸이 없을 때, 맨 위에서. 시연 주소(?demo=)·시험용 자동 브라우저(HeadlessChrome)·액자(iframe) 안에서는 띄우지 않는다 */
  var auto = TOURS[PAGE] && !done(PAGE) && window.top === window && !/HeadlessChrome/.test(navigator.userAgent) && !/[?&]demo=/.test(location.search);
  if (!auto) return;
  var tries = 0;
  (function wait() {
    if (++tries > 40) return;
    if (document.readyState === 'loading' || document.getElementById('cb-loading') || document.querySelector('.cbcmd') || (window.scrollY || 0) > 40) { setTimeout(wait, 500); return; }
    setTimeout(function () { start(false); }, 900);
  })();
})();

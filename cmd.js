/* 입력 명령(종합 현황·재해별 집중 감시 공용, 2026-11-20) — 실시간 상황판과 같은 명령.
   '/' 를 누르면 가운데 명령 칸, 또는 입력 칸이 아닌 곳에서 단어를 바로 친다(4초 안).
     main 종합 현황 · wall 실시간 상황판 · admin 관리자 화면 ·
     test 시연 단추 꺼내기/숨기기 · stage 비상단계 지정(상황판 지정 창으로) · help 도움말 · guide 처음 화면 안내 다시 보기
   관리자 화면·단계 지정은 원래대로 관리자 키·지정 번호가 있어야 한다.
   시연 단추는 평소 숨김(실시간 상황판과 같게) — test 로 꺼내면 이 브라우저에 기억(cbDemoShow).
   숨김은 <html class="no-demo"> 로 하고, 화면마다 CSS 가 시연 단추를 가린다(시연 중이면 끌 수 있게 그대로 보인다).
   화면은 <script> 앞에 window.CB_PAGE = 'main' | 'watch' 를 둔다. */
(function () {
  var KEY = 'cbDemoShow';
  var PAGE = window.CB_PAGE || '';
  function shown() { try { return localStorage.getItem(KEY) === '1'; } catch (e) { return false; } }
  document.documentElement.classList.toggle('no-demo', !shown());

  var css = document.createElement('style');
  css.textContent =
    '.cbcmd{position:fixed;inset:0;z-index:9800;display:flex;align-items:center;justify-content:center;background:rgba(16,24,40,.35)}' +
    '.cbcmd>div{background:var(--card,var(--surface,#fff));border:1px solid var(--line,var(--border,#e4e8ef));border-radius:16px;padding:18px;box-shadow:0 20px 60px rgba(16,24,40,.3);display:flex;flex-direction:column;gap:10px;align-items:center}' +
    '.cbcmd input{width:min(380px,80vw);text-align:center;font-weight:700;font-size:20px;font-family:inherit;padding:10px 14px;border-radius:12px;border:2px solid var(--brand,#1d4ed8);background:var(--card,var(--surface,#fff));color:var(--ink,#101828);outline:none}' +
    '.cbcmd small{font-size:13px;font-weight:700;color:var(--ink3,#5f6d85)}' +
    '.cbcmd .hint{display:grid;grid-template-columns:repeat(2,auto);gap:5px 18px;font-size:13.5px;color:var(--ink2,#334155)}' +
    '.cbcmd code{display:inline-block;min-width:52px;text-align:center;font:800 14px Consolas,ui-monospace,monospace;color:var(--brand,#1d4ed8);background:var(--ui-hover,#f2f5fa);border:1px solid var(--ui-line,#e4e8ef);border-radius:6px;padding:1px 6px;margin-right:6px}' +
    '.cbcmdt{position:fixed;left:50%;bottom:8vh;transform:translateX(-50%);z-index:9900;background:rgba(15,27,45,.92);color:#fff;font-weight:700;font-size:15px;font-family:inherit;padding:12px 22px;border-radius:12px;pointer-events:none}';
  (document.head || document.documentElement).appendChild(css);

  function toast(t) { var d = document.createElement('div'); d.className = 'cbcmdt'; d.textContent = t; document.body.appendChild(d); setTimeout(function () { d.remove(); }, 2200); }
  function go(t, url) { toast(t); setTimeout(function () { location.href = url; }, 400); }
  var CMDS = {
    main: function () { if (PAGE === 'main') toast('지금 종합 현황 화면입니다'); else go('종합 현황으로 이동합니다', '종합.html'); },
    wall: function () { go('실시간 상황판으로 이동합니다', '상황실.html'); },
    admin: function () { go('관리자 화면으로 이동합니다', '관리자.html'); },
    test: function () {
      var on = !shown(); try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) {}
      document.documentElement.classList.toggle('no-demo', !on);
      toast(on ? '시연 단추를 꺼냈습니다 — test 를 다시 치면 숨깁니다' : '시연 단추를 숨겼습니다');
    },
    stage: function () { go('비상단계 지정 창을 엽니다(실시간 상황판)', '상황실.html?cmd=stage'); },
    help: function () { go('도움말로 이동합니다', '도움말.html'); },
    guide: function () {   // 처음 화면 안내 다시 보기(tour.js). 명령 칸의 Enter 가 안내의 [다음]까지 누르지 않게 Enter 처리가 끝난 뒤 띄운다
      if (!(window.cbTour && window.cbTour.has())) { toast('이 화면에는 안내가 없습니다'); return; }
      setTimeout(function () { window.cbTour.start(true); }, 150);
    }
  };
  /* 명령 칸 아래 목록 — 칠 것(영어)은 글자 상자로, 설명(한글)은 옆에 */
  var HINT = [['main', '종합 현황'], ['wall', '실시간 상황판'], ['admin', '관리자 화면'], ['test', '시연 단추'], ['stage', '비상단계 지정'], ['help', '도움말'], ['guide', '화면 안내']];
  var box = null, typed = '', typedAt = 0;
  function close() { if (box) { box.remove(); box = null; } }
  function open() {
    if (box) return;
    box = document.createElement('div'); box.className = 'cbcmd';
    box.innerHTML = '<div><input placeholder="영어 명령 입력 후 Enter" autocomplete="off" spellcheck="false" aria-label="명령"><small>아래 영어 명령 중 하나를 치고 Enter</small><div class="hint">' +
      HINT.map(function (h) { return '<span><code>' + h[0] + '</code>' + h[1] + '</span>'; }).join('') + '</div></div>';
    document.body.appendChild(box);
    var inp = box.querySelector('input');
    box.addEventListener('mousedown', function (e) { if (e.target === box) close(); });
    inp.addEventListener('keydown', function (e) {
      e.stopPropagation();
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Enter') return;
      /* 한글 조합 중에 누른 Enter — 글자가 확정된 뒤(조합 끝) 실행한다. 명령은 영어지만 한글 자판으로 쳐도 Enter 를 두 번 눌러야 했다 */
      if (e.isComposing || e.keyCode === 229) { setTimeout(run, 30); return; }
      run();
    });
    function run() {
      if (!box) return;                                   // 이미 실행됨(브라우저에 따라 Enter 가 두 번 온다)
      var k = inp.value.trim().toLowerCase().replace(/^\//, ''); close();
      if (CMDS[k]) CMDS[k](); else if (k) toast('없는 명령입니다 — ' + HINT.map(function (h) { return h[0]; }).join(' · '));
    }
    setTimeout(function () { inp.focus(); }, 0);
  }
  document.addEventListener('keydown', function (e) {
    var t = e.target, tag = (t && t.tagName) || '';
    if (e.ctrlKey || e.altKey || e.metaKey || tag === 'INPUT' || tag === 'TEXTAREA' || (t && t.isContentEditable) || document.querySelector('.mbg')) return;
    /* '/' 는 관서 선택 칸(select)에 커서가 있어도 연다 — 관서를 고른 직후엔 커서가 그 칸에 남아 '/' 가 안 먹었다(2026-11-20) */
    if (e.key === '/') { e.preventDefault(); if (tag === 'SELECT') t.blur(); open(); return; }
    if (tag === 'SELECT') return;   // 글자는 선택 칸의 '첫 글자로 찾기'에 양보
    if (!/^[a-zA-Z]$/.test(e.key || '')) return;
    var now = Date.now(); if (now - typedAt > 4000) typed = ''; typedAt = now;
    typed = (typed + e.key.toLowerCase()).slice(-8);
    Object.keys(CMDS).some(function (k) { if (typed.slice(-k.length) === k) { typed = ''; CMDS[k](); return true; } });
  });
})();

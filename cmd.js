/* 입력 명령(종합 현황·재해별 집중 감시 공용, 2026-11-20) — 실시간 상황판과 같은 명령.
   '/' 를 누르면 가운데 명령 칸, 또는 입력 칸이 아닌 곳에서 단어를 바로 친다(4초 안).
     main 종합 현황 · watch 재해별 집중 감시 · wall 실시간 상황판 · admin 관리자 화면 ·
     test 시연 단추 꺼내기/숨기기 · stage 비상단계 지정(상황판 지정 창으로) · help 도움말
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
    '.cbcmd small{font-size:13px;font-weight:600;color:var(--ink3,#5f6d85);text-align:center;max-width:420px;line-height:1.5}' +
    '.cbcmdt{position:fixed;left:50%;bottom:8vh;transform:translateX(-50%);z-index:9900;background:rgba(15,27,45,.92);color:#fff;font-weight:700;font-size:15px;font-family:inherit;padding:12px 22px;border-radius:12px;pointer-events:none}';
  (document.head || document.documentElement).appendChild(css);

  function toast(t) { var d = document.createElement('div'); d.className = 'cbcmdt'; d.textContent = t; document.body.appendChild(d); setTimeout(function () { d.remove(); }, 2200); }
  function go(t, url) { toast(t); setTimeout(function () { location.href = url; }, 400); }
  var CMDS = {
    main: function () { if (PAGE === 'main') toast('지금 종합 현황 화면입니다'); else go('종합 현황으로 이동합니다', '종합.html'); },
    watch: function () { if (PAGE === 'watch') toast('지금 재해별 집중 감시 화면입니다'); else go('재해별 집중 감시로 이동합니다', '재해.html'); },
    wall: function () { go('실시간 상황판으로 이동합니다', '상황실.html'); },
    admin: function () { go('관리자 화면으로 이동합니다', '관리자.html'); },
    test: function () {
      var on = !shown(); try { localStorage.setItem(KEY, on ? '1' : '0'); } catch (e) {}
      document.documentElement.classList.toggle('no-demo', !on);
      toast(on ? '시연 단추를 꺼냈습니다 — test 를 다시 치면 숨깁니다' : '시연 단추를 숨겼습니다');
    },
    stage: function () { go('비상단계 지정 창을 엽니다(실시간 상황판)', '상황실.html?cmd=stage'); },
    help: function () { go('도움말로 이동합니다', '도움말.html'); }
  };
  var HINT = 'main 종합 현황 · watch 집중 감시 · wall 상황판 · admin 관리자 화면 · test 시연 단추 · stage 비상단계 지정 · help 도움말';
  var box = null, typed = '', typedAt = 0;
  function close() { if (box) { box.remove(); box = null; } }
  function open() {
    if (box) return;
    box = document.createElement('div'); box.className = 'cbcmd';
    box.innerHTML = '<div><input placeholder="명령 입력 후 Enter" autocomplete="off" spellcheck="false" aria-label="명령"><small></small></div>';
    box.querySelector('small').textContent = HINT;
    document.body.appendChild(box);
    var inp = box.querySelector('input');
    box.addEventListener('mousedown', function (e) { if (e.target === box) close(); });
    inp.addEventListener('keydown', function (e) {
      e.stopPropagation();
      if (e.key === 'Escape') { close(); return; }
      if (e.key !== 'Enter') return;
      var k = inp.value.trim().toLowerCase().replace(/^\//, ''); close();
      if (CMDS[k]) CMDS[k](); else if (k) toast('알 수 없는 명령 — main · watch · wall · admin · test · stage · help');
    });
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

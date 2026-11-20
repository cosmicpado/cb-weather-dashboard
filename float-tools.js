/* 오른쪽 아래 떠 있는 단추 묶음 — 종합 현황(종합)·재해별 집중 감시(재해)에서 쓴다.
   상황실 전광판은 따로(왼쪽 위 도구 막대)라 넣지 않는다.
     (빈 자리) — 다른 스크립트가 cbFab.slot('edit', 단추) 로 단추를 넣을 수 있다
     W   윈디 정보 크게 보기 — 지금은 숨김(SHOW_WINDY)
     ↑   맨 위로 — 조금 내려갔을 때만 보인다
   스크롤해도 화면 오른쪽 아래에 붙어 따라온다. 잠깐 뜨는 알림(새 공지 등)은 --cb-fab-w 만큼 왼쪽으로 비켜 뜬다. */
(function () {
  'use strict';
  if (window.cbFab) return;
  var box = null, slots = {}, topBtn = null;

  function el(t, css, txt) { var e = document.createElement(t); if (css) e.style.cssText = css; if (txt != null) e.textContent = txt; return e; }
  var BTN = 'width:44px;height:44px;border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0;' +
    'border:1px solid var(--border2,var(--line,#d3dbe9));background:var(--surface,var(--card,#fff));color:var(--ink,#0f1b2d);' +
    'box-shadow:0 4px 14px rgba(15,27,45,.18);font:800 17px/1 Pretendard,system-ui,sans-serif;transition:border-color .15s,transform .15s,opacity .2s;';
  function mkBtn(txt, tip, onClick) {
    var b = el('button', BTN, txt); b.type = 'button'; b.title = tip; b.setAttribute('aria-label', tip);
    b.onmouseenter = function () { b.style.borderColor = 'var(--brand,#2563eb)'; b.style.transform = 'translateY(-1px)'; };
    /* 원래 테두리 색으로 되돌린다 — '' 로 비우면 테두리 색이 글자색(검정·파랑)으로 남았다 */
    b.onmouseleave = function () { b.style.borderColor = 'var(--border2,var(--line,#d3dbe9))'; b.style.transform = ''; };
    b.onclick = onClick; return b;
  }

  function build() {
    if (box) return;
    box = el('div', 'position:fixed;right:16px;bottom:calc(16px + var(--cb-navh,0px));z-index:9300;display:flex;flex-direction:column;align-items:center;gap:8px;');
    box.id = 'cb-fab';
    /* 순서(위→아래): 배치 편집 자리 · (W) · ↑ */
    slots.edit = el('div', 'display:flex;flex-direction:column;align-items:center;gap:8px;');
    box.appendChild(slots.edit);
    /* W(윈디 크게 보기) 단추는 숨김(2026-11-20 — 오른쪽 카드 글자를 가렸다). 다시 쓰려면 SHOW_WINDY 를 true 로 */
    var SHOW_WINDY = false;
    if (SHOW_WINDY) {
      var w = mkBtn('W', '윈디 정보 — 바람 흐름·날씨 레이더·위성 크게 보기', function () { open(); });
      w.style.color = 'var(--brand,#2563eb)';
      box.appendChild(w);
    }
    topBtn = mkBtn('', '맨 위로', function () { try { window.scrollTo({ top: 0, behavior: 'smooth' }); } catch (e) { window.scrollTo(0, 0); } });
    topBtn.innerHTML = '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5"/><path d="M5 12l7-7 7 7"/></svg>';
    box.appendChild(topBtn);
    document.body.appendChild(box);
    document.documentElement.style.setProperty('--cb-fab-w', '60px');
    onScroll(); window.addEventListener('scroll', onScroll, { passive: true });
  }
  /* 맨 위에 있을 땐 ↑ 를 숨긴다(자리는 남겨 다른 단추가 들썩이지 않게) */
  function onScroll() { if (!topBtn) return; var on = (window.scrollY || document.documentElement.scrollTop || 0) > 240;
    topBtn.style.visibility = on ? 'visible' : 'hidden'; topBtn.style.opacity = on ? '1' : '0'; }

  /* ── 윈디 크게 보기 창 — 상황실(cbWindyOpen)과 같은 주소·층. 처음 층은 바람(비가 없으면 레이더는 멈춘 화면 같아서) ── */
  var LAYERS = [['wind', '🌬️ 바람'], ['radar', '📡 날씨 레이더'], ['satellite', '🛰️ 위성'], ['gust', '💨 돌풍'], ['rain', '🌧️ 비·눈 예보'], ['temp', '🌡️ 기온'], ['clouds', '☁️ 구름']];
  function url(overlay) {
    return 'https://embed.windy.com/embed.html?type=map&location=coordinates&metricRain=mm&metricTemp=%C2%B0C&metricWind=m%2Fs'
      + '&zoom=9&overlay=' + (overlay || 'wind') + '&product=ecmwf&level=surface&lat=36.75&lon=127.75&message=true';
  }
  var ov = null;
  function close() { if (ov) { ov.remove(); ov = null; document.removeEventListener('keydown', onKey, true); } }
  function onKey(e) { if (e.key === 'Escape') { e.stopPropagation(); close(); } }
  function open(layer) {
    close(); layer = layer || 'wind';
    ov = el('div', 'position:fixed;inset:0;z-index:9800;background:rgba(5,8,14,.55);display:flex;align-items:center;justify-content:center;padding:2vh 2vw;');
    ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-modal', 'true'); ov.setAttribute('aria-label', '윈디 정보');
    ov.addEventListener('mousedown', function (e) { if (e.target === ov) close(); });
    var card = el('div', 'width:min(1320px,96vw);height:min(900px,94vh);display:flex;flex-direction:column;gap:10px;box-sizing:border-box;padding:14px;border-radius:16px;' +
      'background:var(--surface,var(--card,#fff));color:var(--ink,#0f1b2d);border:1px solid var(--border2,var(--line,#d3dbe9));box-shadow:0 30px 80px rgba(0,0,0,.4);font-family:Pretendard,system-ui,sans-serif;');
    ov.appendChild(card);
    var hd = el('div', 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;');
    hd.appendChild(el('div', 'font-size:18px;font-weight:800;margin-right:6px;', '윈디 정보'));
    var frame = el('iframe', 'flex:1;min-height:0;width:100%;border:0;border-radius:12px;background:#0d1118;'); frame.title = 'Windy';
    var btns = [];
    function pick(k) { frame.src = url(k);
      btns.forEach(function (b) { var on = b.dataset.k === k;
        b.style.background = on ? 'var(--brand,#2563eb)' : 'transparent'; b.style.color = on ? '#fff' : 'var(--ink2,#4b5a74)';
        b.style.borderColor = on ? 'var(--brand,#2563eb)' : 'var(--border2,var(--line,#d3dbe9))'; }); }
    LAYERS.forEach(function (x) { var b = el('button', 'padding:6px 11px;border-radius:10px;border:1px solid;font:800 13.5px Pretendard,system-ui,sans-serif;cursor:pointer;', x[1]);
      b.type = 'button'; b.dataset.k = x[0]; b.onclick = function () { pick(x[0]); }; btns.push(b); hd.appendChild(b); });
    var x = el('button', 'margin-left:auto;width:36px;height:36px;border-radius:10px;border:1px solid var(--border2,var(--line,#d3dbe9));background:transparent;color:var(--ink,#0f1b2d);font-size:18px;cursor:pointer;', '✕');
    x.type = 'button'; x.setAttribute('aria-label', '닫기'); x.onclick = close; hd.appendChild(x);
    card.appendChild(hd); card.appendChild(frame);
    card.appendChild(el('div', 'font-size:13px;color:var(--ink3,#8593aa);', '날씨 레이더·위성은 관측, 나머지는 ECMWF 모델 예보 · 아래 ▶ 로 흐름 재생 · 닫기: ✕ · 바깥 누르기 · Esc'));
    pick(layer);
    document.body.appendChild(ov);
    document.addEventListener('keydown', onKey, true);
  }

  window.cbFab = {
    open: open,
    /* 다른 스크립트가 단추를 넣는 자리 — slot('edit', [단추…]) 로 그 자리를 통째로 바꾼다 */
    slot: function (name, nodes) { build(); var s = slots[name]; if (!s) return; s.innerHTML = '';
      (nodes || []).forEach(function (n) { if (n) s.appendChild(n); }); },
    btn: function (txt, tip, onClick) { return mkBtn(txt, tip, onClick); }
  };
  if (document.body) build(); else document.addEventListener('DOMContentLoaded', build);
})();

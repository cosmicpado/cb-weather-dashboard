/* 로딩 화면 — 실시간 자료를 받기 전에 화면 전체를 덮는다(종합·재해·상황실 공용).
   모양은 같고 색만 다르다 — PC 는 남색 바탕 + 금색 선·막대, 휴대폰은 밝은 바탕 + 빨간 선·막대.
   쓰는 법: cbLoadingScreen.show() / .sub('늦어질 때 안내') / .hide()
   부르는 곳: data-guard.js(종합·재해), 상황실.html(열자마자 + 자체 자료 재시도)
   깜빡임 막기 — 0.4초 안에 닫히면 아예 안 보인다(서서히 나타나기 전에 지움). 한번 보였으면 최소 0.8초는
   보여 주고 0.3초 동안 흐려지며 사라진다. 순식간에 번쩍 지나가 '무슨 화면이었지?' 하지 않게. */
(function () {
  var el = null, subEl = null, t0 = 0;
  var DELAY = 400, MIN = 800, FADE = 300;   // 나타나기까지 · 최소로 보여 줄 시간 · 사라지는 시간(ms)

  function phone() {
    try {
      if (window.matchMedia('(max-width: 820px)').matches) return true;
      return window.matchMedia('(pointer: coarse)').matches && Math.min(screen.width, screen.height) <= 820;
    } catch (e) { return false; }
  }

  function css() {
    if (document.getElementById('cb-loading-css')) return;
    var st = document.createElement('style'); st.id = 'cb-loading-css';
    st.textContent =
      '#cb-loading{animation:cbLoadIn .25s ease-out ' + DELAY + 'ms both;}' +
      '#cb-loading.out{animation:cbLoadOut ' + FADE + 'ms ease-in both;}' +
      '@keyframes cbLoadIn{from{opacity:0}to{opacity:1}}@keyframes cbLoadOut{from{opacity:1}to{opacity:0}}' +
      '#cb-loading{position:fixed;inset:0;z-index:2147483000;display:flex;flex-direction:column;align-items:center;justify-content:center;' +
        'gap:14px;text-align:center;padding:16px;font-family:"Pretendard Variable",Pretendard,"Malgun Gothic",system-ui,sans-serif;}' +
      '#cb-loading img{width:clamp(200px,14vw,560px);height:auto;}#cb-loading.m img{width:62vw;max-width:300px;}' +
      '#cb-loading .org{font-weight:800;font-size:clamp(22px,2.2vw,80px);letter-spacing:.2em;padding-left:.2em;}' +
      '#cb-loading .msg{font-size:clamp(14.5px,1.1vw,40px);font-weight:600;}' +
      '#cb-loading .sub{font-size:clamp(13px,.95vw,34px);font-weight:600;min-height:1.4em;}' +
      /* PC — 남색 + 금색 */
      '#cb-loading.pc{background:radial-gradient(ellipse at 50% 35%,#1d3a66 0%,#0c1c36 70%);}' +
      '#cb-loading.pc .org{color:#fff;}#cb-loading.pc .msg{color:#c9d4e6;}#cb-loading.pc .sub{color:#f5c400;}' +
      '#cb-loading.pc .line{background:#f5c400;}' +
      '#cb-loading.pc .bar{background:rgba(255,255,255,.12);}' +
      '#cb-loading.pc .bar i{background:linear-gradient(90deg,#f5c400,#ffdd55);}' +
      /* 휴대폰 — 밝은 흰색 */
      '#cb-loading.m{background:linear-gradient(180deg,#ffffff 0%,#eef2f8 100%);}' +
      '#cb-loading.m img{filter:drop-shadow(0 4px 10px rgba(19,41,75,.15));}' +
      '#cb-loading.m .org{color:#13294b;}#cb-loading.m .msg{color:#5b6b85;}#cb-loading.m .sub{color:#c8201b;}' +
      '#cb-loading.m .line{background:#c8201b;}' +
      '#cb-loading.m .bar{background:#e1e6ef;}' +
      '#cb-loading.m .bar i{background:linear-gradient(90deg,#c8201b,#ef4b3f);}' +
      /* 공통 — 제목 아래 짧은 선, 흐르는 진행 막대 */
      '#cb-loading .line{width:clamp(56px,3.5vw,140px);height:clamp(2px,.13vw,5px);margin:-4px 0 2px;}' +
      '#cb-loading .bar{width:clamp(240px,15vw,600px);max-width:62vw;height:clamp(4px,.25vw,9px);border-radius:4px;overflow:hidden;}' +
      '#cb-loading .bar i{display:block;width:40%;height:100%;border-radius:4px;animation:cbLoadBar 1.4s ease-in-out infinite;}' +
      '@keyframes cbLoadBar{0%{transform:translateX(-100%)}100%{transform:translateX(250%)}}';
    (document.head || document.documentElement).appendChild(st);
  }

  function node(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  window.cbLoadingScreen = {
    show: function () {
      if (el || !document.body) return;
      css();
      var m = phone();
      el = node('div', m ? 'm' : 'pc'); el.id = 'cb-loading'; el.setAttribute('role', 'status');
      var logo = node('img'); logo.src = 'images/logo-cbfire.png'; logo.alt = '';
      el.appendChild(logo);
      el.appendChild(node('div', 'org', '충청북도 소방본부'));
      el.appendChild(node('div', 'line'));
      el.appendChild(node('div', 'msg', '실시간 자료를 불러오는 중입니다'));
      var bar = node('div', 'bar'); bar.appendChild(node('i')); el.appendChild(bar);
      subEl = node('div', 'sub', ''); el.appendChild(subEl);
      document.body.appendChild(el);
      t0 = Date.now();
    },
    sub: function (text) { if (subEl) subEl.textContent = text || ''; },
    hide: function () {
      if (!el) return;
      var e = el, shownFor = Date.now() - t0 - DELAY;
      el = null; subEl = null;
      if (shownFor < 0) { e.remove(); return; }                 // 아직 나타나기 전 — 그냥 지운다(안 보임)
      setTimeout(function () {                                     // 최소 시간을 채운 뒤 흐려지며 사라짐
        e.classList.add('out');
        setTimeout(function () { e.remove(); }, FADE + 50);
      }, Math.max(0, MIN - shownFor));
    },
    shown: function () { return !!el; }
  };
})();

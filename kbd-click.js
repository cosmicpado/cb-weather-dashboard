/* 키보드로 누르기 — 마우스로만 눌리던 칸(카드·목록 줄·그림)을 Tab 으로 옮겨 가며 Enter·스페이스로 누를 수 있게 한다.
   웹 접근성(WCAG 2.1.1 키보드) — 키보드만 쓰는 사람·화면 읽기 프로그램 사용자도 모든 기능을 쓸 수 있어야 한다.
   · 찾는 칸: 화면이 window.CB_KBD_SEL 로 알려 준 것(종합의 .ref·.chip 등) + 손가락 모양 마우스(cursor:pointer)가 적힌 칸
     (재해·상황실은 칸마다 style 에 cursor:pointer 를 적는다). 원래 누를 수 있는 단추·링크·입력칸은 건드리지 않는다.
   · 찾은 칸에 tabindex="0" role="button" 을 붙이고, Enter·스페이스를 누르면 마우스로 누른 것과 같게 click 을 보낸다.
   · 키보드로 옮겨 왔을 때만(:focus-visible) 파란 테두리를 보인다 — 마우스로 누를 때 모양은 그대로다.
   · 화면이 다시 그려져도(새 칸이 생겨도) 0.3초 뒤 다시 찾는다. */
(function () {
  if (window.cbKbdClick) return;
  var NATIVE = 'a[href],button,input,select,textarea,summary,iframe,[contenteditable="true"]';
  function sel() {
    return (window.CB_KBD_SEL ? window.CB_KBD_SEL + ',' : '') +
      '[style*="cursor: pointer"],[style*="cursor:pointer"],a:not([href])[onclick],a:not([href])[title]';
  }
  function scan() {
    var list;
    try { list = document.querySelectorAll(sel()); } catch (e) { return; }
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (el.hasAttribute('data-kbd') || el.matches(NATIVE) || el.closest('svg')) continue;
      if (el.closest(NATIVE)) continue;                 // 단추 안의 글자 칸 등 — 바깥 단추가 이미 키보드로 된다
      el.setAttribute('data-kbd', '1');
      if (!el.hasAttribute('tabindex')) el.setAttribute('tabindex', '0');
      if (!el.hasAttribute('role')) el.setAttribute('role', 'button');
    }
  }
  document.addEventListener('keydown', function (e) {
    var el = e.target;
    if (!el || !el.getAttribute || el.getAttribute('data-kbd') !== '1') return;
    if (e.key === 'Enter' || e.key === ' ' || e.key === 'Spacebar') {
      e.preventDefault();                               // 스페이스로 화면이 내려가지 않게
      el.click();
    }
  });
  var css = document.createElement('style');
  css.textContent = '[data-kbd]:focus{outline:none}[data-kbd]:focus-visible{outline:3px solid #3b82f6;outline-offset:2px;border-radius:8px}';
  (document.head || document.documentElement).appendChild(css);
  var t = 0;
  function later() { clearTimeout(t); t = setTimeout(scan, 300); }
  function start() {
    scan();
    new MutationObserver(later).observe(document.body, { childList: true, subtree: true });
  }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  window.cbKbdClick = { scan: scan };
})();

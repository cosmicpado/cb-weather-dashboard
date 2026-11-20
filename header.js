/* 휴대폰 윗줄 접기(2026-11-20) — 종합 현황·재해별 집중 감시 공용.
   아래로 내리면 이름 줄을 접고 [로고 · 충북 전체 | 관서 · 자료 시각] 한 줄만 위에 남긴다(<html class="hd-slim">).
   모양은 ui.css. 접히면 화면 높이가 줄어 위치가 조금 바뀌므로, 펼치는 기준(40px)을 접는 기준(160px)보다 훨씬 위에 둬서
   경계에서 접혔다 펴졌다 떨지 않게 한다. PC 는 접지 않는다(윗줄 전체 고정). */
(function () {
  var mq = window.matchMedia ? window.matchMedia('(max-width:820px)') : null;
  var de = document.documentElement, on = false, raf = 0;
  function update() {
    raf = 0;
    var y = window.scrollY || de.scrollTop || 0;
    var want = !!(mq && mq.matches) && (on ? y > 40 : y > 160);
    if (want !== on) { on = want; de.classList.toggle('hd-slim', on); }
  }
  function soon() { if (!raf) raf = requestAnimationFrame(update); }
  window.addEventListener('scroll', soon, { passive: true });
  if (mq) { if (mq.addEventListener) mq.addEventListener('change', soon); else if (mq.addListener) mq.addListener(soon); }
  update();
})();

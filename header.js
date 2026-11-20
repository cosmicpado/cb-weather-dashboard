/* 휴대폰 윗줄 접기(2026-11-20) — 종합 현황·재해별 집중 감시 공용.
   아래로 내리면 이름 줄을 접고 [로고 · 전체 | 관서 · 13:28 기준] 한 줄만 위에 남긴다(<html class="hd-slim">).
   모양은 ui.css. 펼치는 기준(40px)을 접는 기준(160px)보다 훨씬 위에 둬서 경계에서 접혔다 펴졌다 떨지 않게 한다.
   접히거나 펴지면 윗줄 높이가 바뀌어 본문이 한 번에 튀었다(뚝 끊기는 느낌) — 바뀐 만큼 스크롤을 맞춰 본문은 제자리에 두고,
   윗줄 안 글자만 살짝 페이드한다. PC 는 접지 않는다(윗줄 전체 고정). */
(function () {
  var mq = window.matchMedia ? window.matchMedia('(max-width:820px)') : null;
  var de = document.documentElement, on = false, raf = 0, animT = 0;
  function set(v) {
    var bar = document.querySelector('.hd-bar'), a = bar && bar.nextElementSibling;
    var t0 = a ? a.getBoundingClientRect().top : 0;
    on = v; de.classList.toggle('hd-slim', on);
    if (a) { var d = a.getBoundingClientRect().top - t0; if (Math.abs(d) > 1) window.scrollBy(0, d); }   // 본문 제자리
    de.classList.add('hd-anim'); clearTimeout(animT); animT = setTimeout(function () { de.classList.remove('hd-anim'); }, 260);
  }
  function update() {
    raf = 0;
    var y = window.scrollY || de.scrollTop || 0;
    var want = !!(mq && mq.matches) && (on ? y > 40 : y > 160);
    if (want !== on) set(want);
  }
  function soon() { if (!raf) raf = requestAnimationFrame(update); }
  window.addEventListener('scroll', soon, { passive: true });
  if (mq) { if (mq.addEventListener) mq.addEventListener('change', soon); else if (mq.addListener) mq.addListener(soon); }
  update();
})();

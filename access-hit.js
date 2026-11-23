/* 접속 통계 알림(2026-11-23) — 화면이 실제로 3초 넘게 보였을 때만 서버에 "봤음"을 알린다(/api/hit).
   서버가 화면 파일을 내줄 때 세면 메일 보안 검사처럼 주소만 열어 보고 닫는 접속까지 사람으로 잡혔다.
   탭이 뒤에 숨어 있는 동안은 시간을 세지 않는다. 켜 둔 채 날이 바뀌면 다음 날 한 번 더 알린다(늘 켜 둔 상황판 PC).
   쓰는 법: <script src="access-hit.js" data-page="종합.html"></script> — data-page 는 실제 파일 이름. */
(function () {
  if (window.__cbHit) return;                      // 화면 틀이 스크립트를 다시 돌려도 한 번만
  window.__cbHit = true;
  var me = document.currentScript, page = me && me.getAttribute('data-page');
  if (!page || !/^https?:$/.test(location.protocol) || !window.fetch) return;
  var shown = 0, last = Date.now(), sentDay = '';
  function day() { var d = new Date(); return d.getFullYear() + '-' + (d.getMonth() + 1) + '-' + d.getDate(); }
  function send() {
    sentDay = day();
    fetch('api/hit', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ page: page }),
      credentials: 'same-origin', keepalive: true, cache: 'no-store' }).catch(function () {});
  }
  function tick() {
    var now = Date.now(), vis = document.visibilityState !== 'hidden';
    if (vis) shown += now - last;
    last = now;
    if (!sentDay && shown >= 3000) send();
    else if (sentDay && vis && sentDay !== day()) send();      // 켜 둔 채 날이 바뀜
  }
  document.addEventListener('visibilitychange', function () { last = Date.now(); });
  setInterval(tick, 1000);
})();

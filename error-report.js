/* 화면 오류 기록(2026-11-20) — 직원 PC·휴대폰에서 스크립트 오류가 나면 서버(.data/client_errors.jsonl)에 남긴다.
   관리자가 나중에 보고 고칠 수 있게. 같은 오류는 이 화면에서 한 번만, 한 화면에서 최대 10건까지만 보낸다.
   파일로 연 화면(file://)·서버가 없는 곳에서는 아무것도 하지 않는다. 각 화면 <head> 앞쪽에서 불러 둔다. */
(function () {
  if (!/^https?:$/.test(location.protocol) || !window.fetch) return;
  var sent = {}, n = 0;
  var page = decodeURIComponent(location.pathname.split('/').pop() || '') || location.pathname;
  function send(msg, src, line, stack) {
    msg = String(msg || '').slice(0, 300);
    if (!msg || n >= 10) return;
    if (/^Script error\.?$/.test(msg)) return;            // 다른 주소의 스크립트(지도·윈디 등) — 내용을 알 수 없다
    var key = msg + '|' + (src || '') + '|' + (line || '');
    if (sent[key]) return; sent[key] = 1; n++;
    try {
      fetch('api/feedback', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Requested-With': 'cbweather' },
        body: JSON.stringify({ action: 'client_error', page: page, msg: msg, src: String(src || '').slice(0, 160), line: String(line || ''), stack: String(stack || '').slice(0, 1200) }),
        keepalive: true }).catch(function () {});
    } catch (e) {}
  }
  window.addEventListener('error', function (e) {
    if (!e || (e.target && e.target !== window && e.target.tagName)) return;   // 그림·스크립트 파일 못 받은 것(자원 오류)은 빼고 스크립트 오류만
    send(e.message, e.filename, e.lineno ? e.lineno + ':' + (e.colno || 0) : '', e.error && e.error.stack);
  });
  window.addEventListener('unhandledrejection', function (e) {
    var r = e && e.reason;
    if (r && /Failed to fetch|NetworkError|Load failed|aborted/i.test(String(r.message || r))) return;   // 잠깐 끊긴 연결은 오류가 아니다
    send('Promise: ' + (r && (r.message || r)), '', '', r && r.stack);
  });
})();

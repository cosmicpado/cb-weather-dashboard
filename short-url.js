/* 짧은 주소(2026-11-12) — 주소창에 한글 파일 이름 대신 짧은 주소를 보여 준다.
     /지도.html → /   ·  /상황실.html → /room  ·  /재해.html → /watch
     /관리자.html → /admin  ·  /도움말.html → /help  ·  /쉬운.html → /easy
   서버(서버.bat 의 tools/live_local.py · Rocky nginx)가 짧은 주소를 같은 화면으로 내준다.
   화면끼리의 링크는 파일 이름 그대로 두고, 화면이 열린 뒤 주소창만 바꾼다(새로 불러오지 않음).
   ⚠ 바꾸기 전에 서버에 그 짧은 주소가 실제로 열리는지 물어본다 — 아직 짧은 주소를 모르는 서버면
     그대로 둬서, 새로고침했을 때 '찾을 수 없음'이 나지 않게. 파일로 연 화면(file://)도 그대로 둔다. */
(function () {
  var MAP = { '지도.html': '/', '상황실.html': '/room', '재해.html': '/watch',
              '관리자.html': '/admin', '도움말.html': '/help', '쉬운.html': '/easy' };
  window.CB_SHORT_URL = MAP;
  if (!/^https?:$/.test(location.protocol) || !window.fetch || !history.replaceState) return;
  var name = location.pathname.split('/').pop();
  try { name = decodeURIComponent(name); } catch (e) {}
  var short = MAP[name];
  if (!short) return;
  var dir = location.pathname.slice(0, location.pathname.lastIndexOf('/'));   // 하위 폴더에 놓인 경우도
  var target = (dir + short).replace(/\/\/+/g, '/') || '/';
  fetch(target, { method: 'HEAD', cache: 'no-store' }).then(function (r) {
    if (!r.ok) return;
    var now = location.pathname.split('/').pop();
    try { now = decodeURIComponent(now); } catch (e) {}
    if (now !== name) return;                                                  // 그 사이 다른 화면으로 갔으면 손대지 않는다
    try { history.replaceState(history.state, '', target + location.search + location.hash); } catch (e) {}
  }).catch(function () {});
})();

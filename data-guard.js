/* 화면 필수 파일 확인 — <script src="data.js"> 바로 다음에 넣는다(loading-screen.js 를 먼저 읽을 것).
   접속 순간 파일 몇 개를 못 받으면(https 첫 접속 끊김 등) 화면이 빈 값으로 채워지거나
   관서 선택에 '충청북도'만 뜨고 지도가 빈다. 필수 파일 중 하나라도 빠지면 화면 전체를 '불러오는 중'으로 가리고,
   5초마다 빠진 파일을 다시 받아 모두 되면 화면을 새로 연다.
   (상황실.html 은 화면 안에서 자료를 다시 넣을 수 있어 자체 가림막을 쓴다 — 이 파일은 지도·재해·쉬운 화면용) */
(function () {
  /* [전역 이름, 파일] — 이 화면이 그 파일을 쓰는 경우에만 본다 */
  var NEED = [['DASHBOARD_DATA', 'data.js'], ['REGION_CONF', 'region.js'], ['MAPGEO', 'map-geo.js']];
  function uses(file) {
    var s = document.getElementsByTagName('script');
    for (var i = 0; i < s.length; i++) if ((s[i].getAttribute('src') || '').split('?')[0] === file) return true;
    return false;
  }
  function missing() {
    return NEED.filter(function (n) { return !window[n[0]] && uses(n[1]); }).map(function (n) { return n[1]; });
  }
  var tries = 0, timer = null;
  /* 가림 화면 모양은 loading-screen.js(공용) */
  function show() { if (window.cbLoadingScreen) window.cbLoadingScreen.show(); }
  function retry(files) {
    Promise.all(files.map(function (f) {
      return fetch(f + '?_t=' + Date.now(), { cache: 'no-store' }).then(function (r) { return r.ok ? r.text() : ''; })
        .then(function (t) { return t.length > 50 && t.lastIndexOf('}') > 0; }).catch(function () { return false; });
    })).then(function (ok) { if (ok.every(Boolean)) location.reload(); });
  }
  function start() {
    var m = missing(); if (!m.length || timer) return;
    show();
    timer = setInterval(function () {
      show(); tries++;
      if (tries >= 8 && window.cbLoadingScreen) window.cbLoadingScreen.sub('연결이 늦어지고 있습니다 — 자동으로 다시 시도하는 중 (' + tries + '초)');
      if (tries % 5 === 1) retry(m);
    }, 1000);
  }
  /* 지금(data.js 직후) 한 번 보고, 뒤에 오는 파일(지도 등)까지 다 읽혔을 때를 위해 처음 10초 동안 0.5초마다 다시 본다
     (화면 틀이 문서를 다시 그려 DOMContentLoaded 를 놓치는 화면이 있어 이벤트 대신 시간으로 본다) */
  if (!window.DASHBOARD_DATA && document.body) start();
  var n = 0, early = setInterval(function () {
    if (++n > 20 || timer) { clearInterval(early); return; }
    if (document.readyState !== 'loading' && document.body) start();
  }, 500);
})();
